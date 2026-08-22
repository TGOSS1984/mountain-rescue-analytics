"""
scrape_team_incidents.py

Pulls raw incident posts from a team's public incident log and writes
them to pipeline/data/raw/{team_id}_incidents_raw.json — one JSON object
per incident, completely unprocessed. Cleaning happens later, in
pipeline/clean/. This script's only job is "get the words off the page
and onto disk," so that a scraping failure never means re-fetching pages
we've already been polite enough to request once.

Approach, in order of preference:
  1. WordPress REST API (if `rest_api_candidate` is set and responds) —
     structured JSON, no HTML parsing needed, far less brittle.
  2. HTML scraping of the paginated archive + individual incident pages,
     using BeautifulSoup, as a fallback for sites that block or don't
     expose the REST API.

Note: this was written and reviewed without live access to the target
sites (this environment's network is restricted to package registries).
Run it locally, and if the REST API path 404s or comes back empty, that's
expected on some setups — the HTML fallback should still work, but check
the CSS selectors in `_parse_archive_page` against the live page first,
since template changes are the most likely thing to break here.
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential

from sources import SOURCES

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {
    "User-Agent": "mountain-rescue-analytics-portfolio-project "
                  "(personal, non-commercial data analysis; contact via GitHub)"
}
REQUEST_DELAY_SECONDS = 2  # be a polite scraper — these are volunteer-run charity sites


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=20))
def _get(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp


def try_rest_api(source):
    """Attempt the WordPress REST API path. Returns a list of raw dicts, or None."""
    candidate = source.get("rest_api_candidate")
    if not candidate:
        return None

    incidents = []
    page = 1
    while True:
        url = f"{candidate}?per_page=100&page={page}"
        try:
            resp = _get(url)
        except requests.HTTPError:
            break  # e.g. 400 on page-too-high, or API not enabled — either way, stop

        batch = resp.json()
        if not batch:
            break

        for post in batch:
            incidents.append({
                "source_team_id": source["team_id"],
                "source_method": "rest_api",
                "wp_id": post.get("id"),
                "title_raw": post.get("title", {}).get("rendered"),
                "content_html": post.get("content", {}).get("rendered"),
                "date_published": post.get("date"),
                "link": post.get("link"),
            })

        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return incidents or None


def _parse_archive_page(html, source):
    """
    Fallback HTML parser for a single archive listing page.
    Returns a list of {title, link} for that page's incident teasers.

    NOTE: selectors below match the structure observed on Edale MRT's
    archive at the time this was written (article/h3 teaser blocks with
    a "Read More »" link). Re-check against the live DOM before relying
    on this — template markup is the most fragile part of any scraper.
    """
    soup = BeautifulSoup(html, "html.parser")
    teasers = []
    for heading in soup.select("h2 a, h3 a"):
        link = heading.get("href", "")
        if source.get("post_link_pattern") and not re.search(source["post_link_pattern"], link):
            continue
        teasers.append({"title_raw": heading.get_text(strip=True), "link": link})
    return teasers


def _parse_incident_detail(html):
    """Pull the full body text from a single incident's detail page."""
    soup = BeautifulSoup(html, "html.parser")
    # Prefer a clearly-scoped content container if one exists; fall back to <article>.
    content = soup.select_one(".entry-content") or soup.select_one("article")
    return content.get_text("\n", strip=True) if content else soup.get_text("\n", strip=True)


def scrape_via_html(source, max_pages=50):
    incidents = []
    page = 1
    while page <= max_pages:
        url = source["archive_url"] if page == 1 else source["archive_url_template"].format(page=page)
        try:
            resp = _get(url)
        except requests.HTTPError:
            break

        teasers = _parse_archive_page(resp.text, source)
        if not teasers:
            break

        for teaser in teasers:
            time.sleep(REQUEST_DELAY_SECONDS)
            try:
                detail_resp = _get(teaser["link"])
            except requests.HTTPError:
                continue
            incidents.append({
                "source_team_id": source["team_id"],
                "source_method": "html_scrape",
                "wp_id": None,
                "title_raw": teaser["title_raw"],
                "content_html": None,
                "content_text": _parse_incident_detail(detail_resp.text),
                "date_published": None,  # extracted from body text in cleaning step
                "link": teaser["link"],
            })

        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return incidents


def scrape_source(source):
    print(f"[{source['team_id']}] trying REST API…")
    incidents = try_rest_api(source)

    if incidents is None:
        print(f"[{source['team_id']}] REST API unavailable — falling back to HTML scrape")
        incidents = scrape_via_html(source)

    print(f"[{source['team_id']}] collected {len(incidents)} raw incidents")
    return incidents


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        if source["team_id"] == "buxton":
            print(f"[{source['team_id']}] skipping — archive structure not yet confirmed, "
                  f"see docs/data-dictionary.md")
            continue

        if source["team_id"] == "wasdale":
            # Different site structure (one page, not paginated) — handled
            # by its own scraper rather than forcing it through the
            # generic WordPress-shaped logic above.
            import scrape_wasdale
            scrape_wasdale.main()
            continue

        if source["team_id"] == "ovmro":
            # Server-rendered details table, not the JS-loaded map page —
            # also handled by its own scraper. See scrape_ovmro.py.
            import scrape_ovmro
            scrape_ovmro.main()
            continue

        incidents = scrape_source(source)
        out_path = RAW_DIR / f"{source['team_id']}_incidents_raw.json"
        out_path.write_text(json.dumps(incidents, indent=2, ensure_ascii=False))
        print(f"[{source['team_id']}] wrote {out_path}")


if __name__ == "__main__":
    main()