"""
test_scrape_dispatch.py

Regression test for a real bug: scrape_uwfra.py was built and tested
thoroughly in isolation, but the dispatcher in scrape_team_incidents.py
that's supposed to route each source to its dedicated scraper (the
same pattern already used for Wasdale and OVMRO) never got a matching
branch for UWFRA. A full local pipeline run silently fell through to
the generic REST/HTML-fallback path instead — no error, no exception,
just "[uwfra] collected 0 raw incidents" — and the gap only surfaced
when the deployed API's /regions response was checked directly and
UWFRA was visibly missing.

This test proves the dispatch itself is correct, independent of
whether each scraper's own parsing logic works (that's covered
separately in test_scrape_uwfra.py, test_scrape_wasdale.py, etc.) —
every source with its own dedicated scraper must actually have that
scraper called, not just exist as an unused module.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))

import scrape_team_incidents


def test_every_source_with_a_dedicated_scraper_actually_gets_called():
    with patch("scrape_wasdale.main") as mock_wasdale, \
         patch("scrape_ovmro.main") as mock_ovmro, \
         patch("scrape_uwfra.main") as mock_uwfra, \
         patch.object(scrape_team_incidents, "scrape_source", return_value=[]) as mock_generic, \
         patch("pathlib.Path.write_text"):
        scrape_team_incidents.main()

    assert mock_wasdale.called
    assert mock_ovmro.called
    assert mock_uwfra.called, (
        "scrape_uwfra.main() was not called — the exact bug this test "
        "exists to catch. Check for a matching 'if source[\"team_id\"] "
        "== \"uwfra\":' branch in scrape_team_incidents.py's dispatcher."
    )

    # Only sources WITHOUT their own dedicated scraper (currently just
    # Edale) should ever reach the generic fallback path.
    generic_team_ids = [call[0][0]["team_id"] for call in mock_generic.call_args_list]
    assert generic_team_ids == ["edale"]
    assert "uwfra" not in generic_team_ids
    assert "wasdale" not in generic_team_ids
    assert "ovmro" not in generic_team_ids