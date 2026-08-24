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


ATTENDEES_RE = re.compile(r"Attendees:\s*(\d+)")
DURATION_LABEL_RE = re.compile(r"Duration:\s*(\d+hr\s+\d+min)")
TOTAL_ATTENDANCE_RE = re.compile(r"Total attendance:\s*(\d+hr\s+\d+min)")
DATE_REF_RE = re.compile(r"(\d{1,2}\s+\w{3}\s+\d{4})\s+(\d{4}/\d+)")


def _parse_archive_page(html):
    """
    Parses one archive listing page into a list of incident summaries.

    Rewritten against real, verified HTML fetched directly from the
    live site (not a reconstruction) after an earlier version failed
    on literally every entry (285/285) in a real pipeline run. The
    root cause: that version flattened the whole page to plain text
    and looked for a single line containing both the date and incident
    reference together — but the real markup separates them with an
    <i> icon tag:

        <i class="fa-regular fa-calendar"></i>16 Aug 2026
        <i class="fa-solid fa-hashtag"></i>2026/31

    which get_text() splits onto two separate lines, so that line
    never existed. This version doesn't flatten anything — it works
    directly against the DOM, using the real, stable structure
    confirmed from a live fetch: every entry is a `div.blog-item`
    with four direct-child divs in a fixed order (date/ref, title,
    narrative snippet, stats) followed by the "Read more" link, all
    consistent across 16 real entries checked before writing this.
    """
    soup = BeautifulSoup(html, "html.parser")
    entries = []

    for item in soup.select("div.blog-item"):
        col = item.select_one(".col-sm")
        if not col:
            continue

        children = col.find_all("div", recursive=False)
        if len(children) < 4:
            continue  # not a genuine incident entry — skip rather than guess

        date_div, title_div, _narrative_div, stats_div = children[:4]
        read_more = col.select_one("a.stretched-link")

        entries.append({
            "date_text": date_div.get_text(" ", strip=True),
            "title": title_div.get_text(strip=True) or None,
            "stats_text": stats_div.get_text(" ", strip=True),
            "article_url": read_more.get("href", "") if read_more else None,
        })

    return entries


def _parse_entry_fields(entry):
    """Extracts the structured fields from one entry dict produced by
    _parse_archive_page — operates on the already-isolated per-entry
    text, not a flattened whole-page block, so there's no risk of one
    entry's regex match bleeding into another's."""
    date_match = DATE_REF_RE.search(entry["date_text"])
    date_raw = date_match.group(1) if date_match else None
    incident_ref = date_match.group(2) if date_match else None

    attendees_match = ATTENDEES_RE.search(entry["stats_text"])
    attendees = attendees_match.group(1) if attendees_match else None

    duration_match = DURATION_LABEL_RE.search(entry["stats_text"])
    duration_raw = duration_match.group(1) if duration_match else None

    total_match = TOTAL_ATTENDANCE_RE.search(entry["stats_text"])
    total_attendance_raw = total_match.group(1) if total_match else None

    return {
        "date_raw": date_raw,
        "incident_ref": incident_ref,
        "title": entry["title"],
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
            fields = _parse_entry_fields(entry)
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