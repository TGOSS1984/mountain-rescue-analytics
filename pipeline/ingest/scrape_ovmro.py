"""
scrape_ovmro.py

Ogwen Valley Mountain Rescue Organisation publish two incident views:
a map (ogwen-rescue.org.uk/incident-maps/) that loads its data via
client-side JavaScript — genuinely not fetchable with a plain HTTP
request — and a details page (ogwen-rescue.org.uk/incident-details/)
that renders the full table server-side. The details page is what this
scraper uses: same underlying data, no JavaScript problem, and it's
actually richer than the map — each row includes incident number,
location, date, an operation duration, casualty count, and team members
attended, on top of the narrative.

That duration + team-size data is genuinely new compared to Edale and
Wasdale, and worth keeping as its own columns rather than folding into
the narrative text — it opens up questions like "do longer operations
correlate with worse weather" that the other two sources can't answer
on their own.

Row shape in the source (one table, one row per incident):
    **134** Tryfan      16/08/2026     Duration: 03:40       12 members attended
    <narrative in the adjacent column>

    **120** Afon Conwy, Fairy Glen/Ffos Noddum   22/07/2026   Duration: 01:45
    1 person      20 members attended
    <narrative>

The casualty count ("N person"/"N people") is only present on some rows
— left null when absent, not assumed to be zero, since "not stated"
and "zero casualties" aren't the same claim.
"""

import json
import re
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {
    "User-Agent": "mountain-rescue-analytics-portfolio-project "
                  "(personal, non-commercial data analysis; contact via GitHub)"
}

ENTRY_RE = re.compile(
    r"\*\*(\d+)\*\*\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+Duration:\s+(\d{2}:\d{2})"
    r"(?:\s+(\d+)\s+persons?)?\s+(\d+)\s+members?\s+attended"
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def _get(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp


def _parse_table(page_markdown_or_html):
    """
    Splits the details table into rows. This was developed against the
    page's rendered markdown-style table (pipe-delimited Details |
    Description columns); if fetching raw HTML instead, parse the
    <table> rows with BeautifulSoup and pass each row's two cell texts
    through the same ENTRY_RE against the first cell — the regex itself
    doesn't care which route got you the text.
    """
    rows = []
    for line in page_markdown_or_html.split("\n"):
        if "**" not in line or "|" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        # table rows here look like: | Details... | Description... |
        cells = [c for c in cells if c]
        if len(cells) < 2:
            continue

        details_cell, description_cell = cells[0], cells[1]
        match = ENTRY_RE.search(details_cell)
        if not match:
            continue

        num, location, date_raw, duration, casualties, members = match.groups()
        rows.append({
            "incident_number": num,
            "location_text": location.strip(),
            "date_raw": date_raw,          # DD/MM/YYYY
            "duration_raw": duration,      # HH:MM elapsed, not a clock time
            "casualties_count": casualties,
            "team_members_attended": members,
            "narrative": description_cell.strip(),
        })

    return rows


def scrape():
    resp = _get("https://ogwen-rescue.org.uk/incident-details/")
    return _parse_table(resp.text)


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("[ovmro] fetching incident details page…")
    rows = scrape()
    print(f"[ovmro] extracted {len(rows)} incidents")

    incidents = []
    for r in rows:
        incidents.append({
            "source_team_id": "ovmro",
            "source_method": "html_scrape_rendered_table",
            "wp_id": None,
            "title_raw": f"{r['incident_number']} {r['location_text']}",
            "content_html": None,
            "content_text": r["narrative"],
            "location_text_stated": r["location_text"],
            "date_raw_ddmmyyyy": r["date_raw"],
            "duration_raw": r["duration_raw"],
            "casualties_count": r["casualties_count"],
            "team_members_attended": r["team_members_attended"],
            "date_published": None,
            "link": "https://ogwen-rescue.org.uk/incident-details/",
        })

    out_path = RAW_DIR / "ovmro_incidents_raw.json"
    out_path.write_text(json.dumps(incidents, indent=2, ensure_ascii=False))
    print(f"[ovmro] wrote {out_path}")


if __name__ == "__main__":
    main()