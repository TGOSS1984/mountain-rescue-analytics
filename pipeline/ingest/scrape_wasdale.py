"""
scrape_wasdale.py

Wasdale MRT publish their whole year's incidents as one long page
(wmrt.org.uk/report-page/) rather than a paginated archive with separate
detail pages like Edale. Each entry follows a consistent shape:

    "16. Slight Side, Scafell - Limited Callout - 16:09 Sat 21st Feb 2026"

...followed by one or more narrative paragraphs, then a blank line before
the next numbered entry. That's different enough from the WordPress
archive/detail pattern that it gets its own small scraper rather than
being forced through scrape_team_incidents.py's generic logic.

The header line is genuinely useful beyond just what Edale gives us:
Wasdale state a callout type directly (Alert / Limited Callout / Full
Callout), which is a real severity signal from the source — not an
inferred one — so it's kept as its own field in cleaning rather than
being folded into the keyword-guessed `outcome` column used for teams
that don't provide this.

Writes to pipeline/data/raw/wasdale_incidents_raw.json in the same
general shape as the Edale output (source_team_id, source_method,
title_raw, content_text, link) so the rest of the pipeline doesn't need
to know or care which scraper produced a given row.
"""

import json
import re
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {
    "User-Agent": "mountain-rescue-analytics-portfolio-project "
                  "(personal, non-commercial data analysis; contact via GitHub)"
}

# Matches: "16. Slight Side, Scafell - Limited Callout - 16:09 Sat 21st Feb 2026"
# Captured groups: number, location, callout_type, rest-of-line (time + date)
ENTRY_HEADER_RE = re.compile(
    r"^(\d+)\.\s+(.+?)\s+-\s+(Alert|Limited Callout|Full Callout)\s+-\s+(.+)$"
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def _get(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp


def _extract_entries(page_text):
    """
    Splits the report page's plain text into individual incident blocks.
    Expects page_text already stripped of nav/header/footer chrome —
    see note in scrape() about isolating the main content region first.
    """
    lines = [l.strip() for l in page_text.split("\n") if l.strip()]
    entries = []
    current = None

    for line in lines:
        header_match = ENTRY_HEADER_RE.match(line)
        if header_match:
            if current:
                entries.append(current)
            num, location, callout_type, time_date = header_match.groups()
            current = {
                "incident_number": num,
                "location_text": location.strip(),
                "callout_type": callout_type,
                "time_date_raw": time_date.strip(),
                "narrative_lines": [],
            }
        elif current:
            current["narrative_lines"].append(line)

    if current:
        entries.append(current)

    return entries


def scrape():
    """
    NOTE: this parses the already-fetched page text (see main() below).
    A production run should isolate the main content region (e.g. the
    <main> or article container) before splitting into lines, to avoid
    picking up nav links or footer text that happen to start with a
    digit and a period. The regex is specific enough (requires the
    " - Alert/Limited Callout/Full Callout - " marker) that this is a
    low-risk edge case, but worth a spot-check against the live page
    rather than assuming.
    """
    resp = _get("https://www.wmrt.org.uk/report-page/")
    entries = _extract_entries(resp.text)

    incidents = []
    for e in entries:
        incidents.append({
            "source_team_id": "wasdale",
            "source_method": "html_scrape_single_page",
            "wp_id": None,
            "title_raw": f"{e['incident_number']}. {e['location_text']}",
            "content_html": None,
            "content_text": (
                f"Incident {e['incident_number']} - {e['location_text']} - "
                f"{e['callout_type']} - {e['time_date_raw']}\n"
                + "\n".join(e["narrative_lines"])
            ),
            "callout_type_stated": e["callout_type"],  # passed through, not re-inferred later
            "date_published": None,
            "link": "https://www.wmrt.org.uk/report-page/",
        })

    return incidents


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("[wasdale] fetching single-page incident report…")
    incidents = scrape()
    print(f"[wasdale] extracted {len(incidents)} incidents")

    out_path = RAW_DIR / "wasdale_incidents_raw.json"
    out_path.write_text(json.dumps(incidents, indent=2, ensure_ascii=False))
    print(f"[wasdale] wrote {out_path}")


if __name__ == "__main__":
    main()