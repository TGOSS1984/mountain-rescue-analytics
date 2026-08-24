"""
test_scrape_uwfra.py

Rewritten after a real pipeline run against the live site failed on
100% of entries (285/285) — the original version of this test suite
passed against a *fabricated* HTML fixture built from my own guess at
the page structure (itself reconstructed from a text-summarized page
fetch, not real markup), which meant "verified against real content"
wasn't actually true. The fixture below is a direct excerpt of real
HTML fetched from uwfra.org.uk/incidents, not a reconstruction.

Root cause of the original 100% failure: the date and incident
reference are separated by an <i> icon tag in the real markup —

    <i class="fa-regular fa-calendar"></i>16 Aug 2026
    <i class="fa-solid fa-hashtag"></i>2026/31

— which get_text() splits onto two separate lines. The original
parser flattened the whole page to text and searched for one line
containing both pieces together to then take "the next line" as the
title; since that line never existed, every entry's title stayed
None. The rewritten parser works against the DOM directly instead,
using the real, stable structure (a `div.blog-item` per entry, with
four direct-child divs in a fixed order) rather than flattening
anything to text.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))

from scrape_uwfra import _parse_archive_page, _parse_entry_fields, _duration_to_minutes

# Direct excerpt of real HTML fetched from uwfra.org.uk/incidents —
# not reconstructed. Includes a genuine real-data oddity worth
# preserving as a test case: "Attendees: 185" for a sheep rescue is
# almost certainly a data-entry error in the source itself, but this
# project doesn't silently "correct" published source data — it's
# captured exactly as stated, same as every other source's quirks.
REAL_HTML = """
<div class="blog-item position-relative">
  <div class="row g-2 g-sm-4">
    <div class="col-sm-3">
      <div class="ratio ratio-16x9"><img class="object-fit-cover" src="media/medium/x.jpg"></div>
    </div>
    <div class="col-sm">
      <div class="small text-body-secondary mb-2">
        <i class="fa-regular fa-calendar me-2"></i>16 Aug 2026          <i class="fa-solid fa-hashtag ms-4 me-2"></i>2026/31          </div>
      <div class="fs-5 fw-bold mb-2">Female fallen Bolton Abbaey</div>
      <div class="mb-2">&nbsp;The team was called by Yorkshire Ambulance Service to assist a 78-year-old woman...</div>
      <div class="d-md-flex flex-wrap small text-body-secondary mb-2">
        <div class="me-4 mb-1 text-nowrap"><i class="fa-regular fa-user-group fa-fw me-2"></i>Attendees: 10</div>
        <div class="me-4 mb-1 text-nowrap"><i class="fa-regular fa-clock fa-fw me-2"></i>Duration: 2hr 55min</div>
        <div class="me-4 mb-1 text-nowrap"><i class="fa-regular fa-user-clock fa-fw me-2"></i>Total attendance: 29hr 10min</div>
      </div>
      <a class="btn btn-sm btn-outline-primary stretched-link" href="blog/article.php?id=346">Read more...</a>
    </div>
  </div>
</div>

<div class="blog-item position-relative">
  <div class="row g-2 g-sm-4">
    <div class="col-sm-3">
      <div class="ratio ratio-16x9"><img class="object-fit-cover" src="media/medium/y.jpg"></div>
    </div>
    <div class="col-sm">
      <div class="small text-body-secondary mb-2">
        <i class="fa-regular fa-calendar me-2"></i>02 Aug 2026          <i class="fa-solid fa-hashtag ms-4 me-2"></i>2026/29          </div>
      <div class="fs-5 fw-bold mb-2">Sheep stuck in a bog</div>
      <div class="mb-2">One of our team members came across a sheep trapped in a bog whilst out walking...</div>
      <div class="d-md-flex flex-wrap small text-body-secondary mb-2">
        <div class="me-4 mb-1 text-nowrap"><i class="fa-regular fa-user-group fa-fw me-2"></i>Attendees: 7</div>
        <div class="me-4 mb-1 text-nowrap"><i class="fa-regular fa-clock fa-fw me-2"></i>Duration: 1hr 38min</div>
        <div class="me-4 mb-1 text-nowrap"><i class="fa-regular fa-user-clock fa-fw me-2"></i>Total attendance: 11hr 26min</div>
      </div>
      <a class="btn btn-sm btn-outline-primary stretched-link" href="blog/article.php?id=344">Read more...</a>
    </div>
  </div>
</div>

<div class="blog-item position-relative">
  <div class="row g-2 g-sm-4">
    <div class="col-sm-3">
      <div class="ratio ratio-16x9"><img class="object-fit-cover" src="media/medium/z.jpg"></div>
    </div>
    <div class="col-sm">
      <div class="small text-body-secondary mb-2">
        <i class="fa-regular fa-calendar me-2"></i>08 Jun 2026          <i class="fa-solid fa-hashtag ms-4 me-2"></i>2026/20          </div>
      <div class="fs-5 fw-bold mb-2">Stranded sheep</div>
      <div class="mb-2">Following a report of a sheep stranded on the River Aire embankment...</div>
      <div class="d-md-flex flex-wrap small text-body-secondary mb-2">
        <div class="me-4 mb-1 text-nowrap"><i class="fa-regular fa-user-group fa-fw me-2"></i>Attendees: 185</div>
        <div class="me-4 mb-1 text-nowrap"><i class="fa-regular fa-clock fa-fw me-2"></i>Duration: 0hr 5min</div>
        <div class="me-4 mb-1 text-nowrap"><i class="fa-regular fa-user-clock fa-fw me-2"></i>Total attendance: 15hr 25min</div>
      </div>
      <a class="btn btn-sm btn-outline-primary stretched-link" href="blog/article.php?id=335">Read more...</a>
    </div>
  </div>
</div>
"""


def test_titles_extracted_correctly_from_real_markup():
    """
    The core regression test: this exact scenario (date and incident
    reference split across two lines by an <i> tag boundary) is what
    caused 100% of real entries to get title=None in production. Every
    title here must now be genuinely extracted, not null.
    """
    entries = _parse_archive_page(REAL_HTML)
    assert len(entries) == 3

    parsed = [_parse_entry_fields(e) for e in entries]
    titles = [p["title"] for p in parsed]

    assert titles == ["Female fallen Bolton Abbaey", "Sheep stuck in a bog", "Stranded sheep"]
    assert None not in titles


def test_date_and_incident_ref_correctly_split_and_rejoined():
    entries = _parse_archive_page(REAL_HTML)
    parsed = [_parse_entry_fields(e) for e in entries]

    assert parsed[0]["date_raw"] == "16 Aug 2026"
    assert parsed[0]["incident_ref"] == "2026/31"
    assert parsed[1]["date_raw"] == "02 Aug 2026"
    assert parsed[1]["incident_ref"] == "2026/29"


def test_article_urls_correct_per_entry():
    entries = _parse_archive_page(REAL_HTML)
    assert entries[0]["article_url"] == "blog/article.php?id=346"
    assert entries[1]["article_url"] == "blog/article.php?id=344"
    assert entries[2]["article_url"] == "blog/article.php?id=335"


def test_attendees_duration_and_total_attendance_parsed_correctly():
    entries = _parse_archive_page(REAL_HTML)
    parsed = [_parse_entry_fields(e) for e in entries]

    assert parsed[0]["attendees"] == "10"
    assert parsed[0]["duration_raw"] == "2hr 55min"
    assert parsed[0]["total_attendance_raw"] == "29hr 10min"


def test_real_data_anomaly_preserved_not_corrected():
    """
    "Attendees: 185" for a sheep rescue is almost certainly a data
    error in the source itself — but this project preserves published
    source data faithfully rather than silently "fixing" values that
    look implausible, the same principle already applied to other
    sources' typos and quirks elsewhere in the pipeline.
    """
    entries = _parse_archive_page(REAL_HTML)
    parsed = [_parse_entry_fields(e) for e in entries]
    assert parsed[2]["attendees"] == "185"


def test_duration_to_minutes_conversion():
    assert _duration_to_minutes("2hr 55min") == 175
    assert _duration_to_minutes("0hr 5min") == 5
    assert _duration_to_minutes("29hr 10min") == 1750
    assert _duration_to_minutes(None) is None
    assert _duration_to_minutes("") is None