"""
scrape_uwfra.py

Upper Wharfedale Fell Rescue Association (Yorkshire Dales) publish a
paginated incident archive at uwfra.org.uk/incidents — a custom
PHP-based CMS, not WordPress, so no REST API shortcut like Edale had.

Each archive entry gives: date, the team's own incident reference
number, a combined title (usually "<what happened> <where>", not a
clean separate location field the way the other three sources have),
a truncated narrative, and three fields none of the other sources
give all together: Attendees (team size, like OVMRO), Duration
(operation length, like OVMRO), and Total attendance — an aggregate
volunteer person-hours figure genuinely unique to this source.

The archive listing truncates narratives mid-sentence ("...Our Fell 2
(Land..."), so this scraper follows through to each incident's own
article page (article.php?id=N) for the full text, same two-step
pattern as Edale's paginated-archive-plus-detail-pages.

Real, messy data confirmed directly from the live site before writing
this: genuine typos in the source itself ("Bolton Abbaey", "Moblity
scooter rescue"), and UWFRA responds to animal welfare callouts
(sheep, dogs) as well as human incidents — a genuinely new incident
category none of the other three sources have, handled in
clean_incidents.py rather than here.
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {
    "User-Agent": "mountain-rescue-analytics-portfolio-project "
                  "(personal, non-commercial data analysis; contact via GitHub)"
}
REQUEST_DELAY_SECONDS = 2

# Matches an archive entry's date + incident-number line, e.g.
# "16 Aug 2026" followed elsewhere by "2026/31" — these render as two
# separate text nodes in the real HTML, handled via the entry's DOM
# structure below rather than a single combined regex.
DURATION_RE = re.compile(r"(\d+)hr\s+(\d+)min")


def _is_retryable(exception):
    if isinstance(exception, requests.HTTPError):
        status = exception.response.status_code if exception.response is not None else None
        return status is not None and status >= 500
    return isinstance(exception, (requests.ConnectionError, requests.Timeout))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
def _get(url, params=None):
    resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp


def _duration_to_minutes(text):
    """'2hr 55min' -> 175. Used for both Duration and Total attendance,
    which share the same 'Xhr Ymin' format in the source."""
    if not text:
        return None
    match = DURATION_RE.search(text)
    if not match:
        return None
    hours, minutes = match.groups()
    return int(hours) * 60 + int(minutes)


ENTRY_START_RE = re.compile(r"(\d{1,2}\s+\w{3}\s+\d{4})\s+(\d{4}/\d+)")


def _parse_archive_page(html):
    """
    Parses one archive listing page into a list of incident summaries.

    An earlier version tried to isolate each entry by walking a fixed
    number of parent levels up from its "Read more..." link — that
    silently grabbed a container broad enough to span multiple entries
    at once (verified with a real test: two different entries both
    returned the first entry's data). Fixed with the same strategy
    already proven for Wasdale's single-page report: flatten the whole
    page to plain text, then split on the entry-start pattern (date +
    incident reference, e.g. "16 Aug 2026 2026/31") rather than trying
    to reconstruct DOM boundaries that aren't guaranteed stable.

    Article URLs are collected separately (plain text loses hyperlinks)
    and zipped back onto the text chunks by position — both are read
    in the same top-to-bottom document order, so a same-length
    positional pairing is more reliable here than trying to spatially
    associate a link with "its" text block.
    """
    soup = BeautifulSoup(html, "html.parser")

    article_urls = [
        a.get("href", "")
        for a in soup.find_all("a", string=re.compile(r"Read more", re.IGNORECASE))
    ]

    # Scope to the main content area if the theme provides one, to
    # avoid nav/footer text polluting the split — falls back to the
    # whole page otherwise.
    content = soup.select_one("main") or soup
    flat_text = content.get_text("\n", strip=True)

    # Split into entry chunks on each match of the start pattern.
    starts = list(ENTRY_START_RE.finditer(flat_text))
    chunks = []
    for i, match in enumerate(starts):
        chunk_start = match.start()
        chunk_end = starts[i + 1].start() if i + 1 < len(starts) else len(flat_text)
        chunks.append(flat_text[chunk_start:chunk_end])

    entries = []
    for i, chunk in enumerate(chunks):
        article_url = article_urls[i] if i < len(article_urls) else None
        entries.append({"article_url": article_url, "block_text": chunk})

    return entries


def _parse_entry_fields(block_text):
    """
    Extracts the structured fields out of one entry's raw text block.
    Real example line shapes:
        16 Aug 2026 2026/31
        Female fallen Bolton Abbaey
        <narrative...>
        Attendees: 10
        Duration: 2hr 55min
        Total attendance: 29hr 10min
    """
    date_match = re.search(r"(\d{1,2}\s+\w{3}\s+\d{4})\s+(\d{4}/\d+)", block_text)
    date_raw = date_match.group(1) if date_match else None
    incident_ref = date_match.group(2) if date_match else None

    attendees_match = re.search(r"Attendees:\s*(\d+)", block_text)
    attendees = attendees_match.group(1) if attendees_match else None

    duration_match = re.search(r"Duration:\s*(\d+hr\s+\d+min)", block_text)
    duration_raw = duration_match.group(1) if duration_match else None

    total_match = re.search(r"Total attendance:\s*(\d+hr\s+\d+min)", block_text)
    total_attendance_raw = total_match.group(1) if total_match else None

    # Title is the line right after the date+ref line, before the
    # narrative starts — extracted positionally since it has no
    # distinguishing markup of its own in the plain-text block.
    lines = [l for l in block_text.split("\n") if l.strip()]
    title = None
    if date_match:
        for i, line in enumerate(lines):
            if date_raw in line and incident_ref in line:
                if i + 1 < len(lines):
                    title = lines[i + 1]
                break

    return {
        "date_raw": date_raw,
        "incident_ref": incident_ref,
        "title": title,
        "attendees": attendees,
        "duration_raw": duration_raw,
        "total_attendance_raw": total_attendance_raw,
    }


def _fetch_full_narrative(article_url):
    resp = _get(article_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    content = soup.select_one("article") or soup.select_one(".content") or soup
    return content.get_text("\n", strip=True)


def scrape(max_pages=20):
    incidents = []
    missing_title_count = 0
    for page in range(1, max_pages + 1):
        url = "https://uwfra.org.uk/incidents"
        params = {"yr": 0, "page": page} if page > 1 else None

        print(f"  fetching archive page {page}…")
        try:
            resp = _get(url, params=params)
        except requests.HTTPError:
            break

        entries = _parse_archive_page(resp.text)
        if not entries:
            break

        for entry in entries:
            fields = _parse_entry_fields(entry["block_text"])
            if not fields["date_raw"]:
                continue  # skip anything that isn't a genuine incident entry

            if not fields["title"]:
                # Real, confirmed-against-live-data edge case: the
                # positional "title is the line right after the date+ref
                # line" heuristic doesn't hold for every entry — some
                # real UWFRA page layouts put the date and title in the
                # same text node with no line break, or something else
                # about that specific entry doesn't match the assumed
                # shape. Counted and reported rather than silently
                # producing rows with blank location_text — see
                # clean_incidents.py for how the null case is handled
                # downstream without crashing.
                missing_title_count += 1

            article_url = entry["article_url"]
            if article_url and not article_url.startswith("http"):
                article_url = "https://uwfra.org.uk/" + article_url.lstrip("/")

            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                narrative = _fetch_full_narrative(article_url) if article_url else None
            except requests.HTTPError:
                narrative = None

            incidents.append({
                "source_team_id": "uwfra",
                "source_method": "html_scrape_paginated_archive",
                "title_raw": fields["title"],
                "content_text": narrative or fields["title"],
                "date_raw_ddmonyyyy": fields["date_raw"],
                "incident_ref": fields["incident_ref"],
                "attendees_count": fields["attendees"],
                "duration_raw": fields["duration_raw"],
                "total_attendance_raw": fields["total_attendance_raw"],
                "link": article_url,
            })

        time.sleep(REQUEST_DELAY_SECONDS)

    if missing_title_count:
        print(f"  [uwfra] warning: {missing_title_count}/{len(incidents)} entries had no "
              f"extractable title (location_text will be blank for these rows)")

    return incidents


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("[uwfra] fetching paginated incident archive…")
    incidents = scrape()
    print(f"[uwfra] extracted {len(incidents)} incidents")

    out_path = RAW_DIR / "uwfra_incidents_raw.json"
    out_path.write_text(json.dumps(incidents, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[uwfra] wrote {out_path}")


if __name__ == "__main__":
    main()