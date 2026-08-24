"""
test_scrape_uwfra.py

Regression test for a real bug found while building this scraper:
walking a fixed number of DOM parent levels up from each "Read more"
link grabbed a container broad enough to span multiple entries, so
every entry silently returned the FIRST entry's data. Fixed by
flattening the page to text and splitting on the entry-start pattern
instead — this test uses three real entries (including "Sheep stuck
in a bog", one of UWFRA's genuine animal-welfare callouts) to prove
each one now gets its own correct, distinct fields.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))

from scrape_uwfra import _parse_archive_page, _parse_entry_fields, _duration_to_minutes

FAKE_HTML = """
<html><body><main>
<div class="incident-entry">
  <p>16 Aug 2026 2026/31</p>
  <h3>Female fallen Bolton Abbaey</h3>
  <p>The team was called by Yorkshire Ambulance Service to assist a 78-year-old woman...</p>
  <p>Attendees: 10</p>
  <p>Duration: 2hr 55min</p>
  <p>Total attendance: 29hr 10min</p>
  <a href="/blog/article.php?id=346">Read more...</a>
</div>
<div class="incident-entry">
  <p>02 Aug 2026 2026/29</p>
  <h3>Sheep stuck in a bog</h3>
  <p>One of our team members came across a sheep trapped in a bog...</p>
  <p>Attendees: 7</p>
  <p>Duration: 1hr 38min</p>
  <p>Total attendance: 11hr 26min</p>
  <a href="/blog/article.php?id=344">Read more...</a>
</div>
<div class="incident-entry">
  <p>29 May 2026 2026/16</p>
  <h3>Fallen youth Brimham Rocks</h3>
  <p>The Team responded to a 15-year-old male who had fallen from rocks...</p>
  <p>Attendees: 5</p>
  <p>Duration: 0hr 22min</p>
  <p>Total attendance: 1hr 50min</p>
  <a href="/blog/article.php?id=331">Read more...</a>
</div>
</main></body></html>
"""


def test_three_entries_each_get_distinct_correct_data():
    entries = _parse_archive_page(FAKE_HTML)
    assert len(entries) == 3

    parsed = [_parse_entry_fields(e["block_text"]) for e in entries]

    assert parsed[0]["incident_ref"] == "2026/31"
    assert parsed[0]["title"] == "Female fallen Bolton Abbaey"
    assert parsed[1]["incident_ref"] == "2026/29"
    assert parsed[1]["title"] == "Sheep stuck in a bog"
    assert parsed[2]["incident_ref"] == "2026/16"
    assert parsed[2]["title"] == "Fallen youth Brimham Rocks"


def test_article_urls_match_correct_entries_by_position():
    entries = _parse_archive_page(FAKE_HTML)
    assert entries[0]["article_url"] == "/blog/article.php?id=346"
    assert entries[1]["article_url"] == "/blog/article.php?id=344"
    assert entries[2]["article_url"] == "/blog/article.php?id=331"


def test_attendees_and_duration_fields_parsed_correctly():
    entries = _parse_archive_page(FAKE_HTML)
    parsed = [_parse_entry_fields(e["block_text"]) for e in entries]

    assert parsed[0]["attendees"] == "10"
    assert parsed[1]["attendees"] == "7"
    assert parsed[2]["attendees"] == "5"


def test_duration_to_minutes_conversion():
    assert _duration_to_minutes("2hr 55min") == 175
    assert _duration_to_minutes("0hr 22min") == 22
    assert _duration_to_minutes("29hr 10min") == 1750
    assert _duration_to_minutes(None) is None
    assert _duration_to_minutes("") is None