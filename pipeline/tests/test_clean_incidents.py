"""
test_clean_incidents.py

Unit tests for the regex/keyword parsing logic in clean_incidents.py.
These run against small hand-written text snippets, not live scraped
data, so they stay fast and deterministic — the point is to pin down
parsing behaviour (including edge cases) independently of whether the
scraper can currently reach the live site.

Run with: pytest pipeline/tests/
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "clean"))

from clean_incidents import parse_incident_number, parse_date, parse_time, classify, ACTIVITY_KEYWORDS, OUTCOME_KEYWORDS


def test_parse_incident_number_standard():
    assert parse_incident_number("Incident 95 – Tuesday 18th August 2026, 1748hrs") == "incident_95"


def test_parse_incident_number_dog_callout():
    assert parse_incident_number("Dog Callout 5 7th August 2026 1700hrs") == "dog_callout_5"


def test_parse_incident_number_missing():
    assert parse_incident_number("A walker was assisted near the edge") is None


def test_parse_date_with_ordinal_suffix():
    assert parse_date("Incident 93 – Saturday 15th August 2026 17:37hrs.") == "2026-08-15"


def test_parse_date_missing():
    assert parse_date("No date information in this string") is None


def test_parse_time_standard():
    assert parse_time("Incident 95 – Tuesday 18th August 2026, 1748hrs") == "17:48"


def test_parse_time_with_colon():
    assert parse_time("Incident 90 – Tuesday 11th August 2026 13:37hrs") == "13:37"


def test_parse_time_ignores_distance_mentions_later_in_text():
    # regression case: "70m down Y Gully" earlier caused a false time match
    # when the whole narrative was scanned instead of just the header
    text = "Incident 91 Saturday 15th August 2026 12:37hrs. A person tumbled approximately 70m down Y Gully."
    assert parse_time(text) == "12:37"


def test_classify_activity_climbing():
    assert classify("A climber fell on Birchin Edge", ACTIVITY_KEYWORDS) == "climbing"


def test_classify_activity_defaults_to_unspecified():
    assert classify("Someone needed help", ACTIVITY_KEYWORDS) == "unspecified"


def test_classify_outcome_air_ambulance():
    assert classify("The air ambulance attended and airlifted the casualty", OUTCOME_KEYWORDS) == "air_ambulance"


def test_classify_outcome_self_rescued():
    assert classify("The family self rescued before the team arrived", OUTCOME_KEYWORDS) == "self_rescued"


def test_wasdale_location_strips_leading_number():
    from clean_incidents import _wasdale_location
    assert _wasdale_location("16. Slight Side, Scafell") == "Slight Side, Scafell"


def test_wasdale_stated_outcome_passed_through_not_reinferred():
    """
    Wasdale entries carry an explicit callout_type_stated field. Cleaning
    should use that directly and mark outcome_source accordingly, rather
    than running the keyword classifier over the narrative and silently
    overwriting a value the source already gave us.
    """
    import json
    from pathlib import Path
    import tempfile
    from clean_incidents import clean_team_file

    raw = [{
        "source_team_id": "wasdale",
        "source_method": "html_scrape_single_page",
        "title_raw": "16. Slight Side, Scafell",
        "content_text": "Incident 16 - Slight Side, Scafell - Limited Callout - 16:09 Sat 21st Feb 2026\n"
                         "Cumbria Police reported two lost walkers.",
        "callout_type_stated": "Limited Callout",
        "link": "https://www.wmrt.org.uk/report-page/",
    }]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = Path(tmp) / "wasdale_incidents_raw.json"
        raw_path.write_text(json.dumps(raw))
        df = clean_team_file(raw_path)

    assert df.iloc[0]["outcome"] == "Limited Callout"
    assert df.iloc[0]["outcome_source"] == "stated_by_team"
    assert df.iloc[0]["location_text"] == "Slight Side, Scafell"


def test_parse_ddmmyyyy():
    from clean_incidents import parse_ddmmyyyy
    assert parse_ddmmyyyy("16/08/2026") == "2026-08-16"
    assert parse_ddmmyyyy("not a date") is None


def test_duration_to_minutes():
    from clean_incidents import duration_to_minutes
    assert duration_to_minutes("03:40") == 220
    assert duration_to_minutes("12:00") == 720
    assert duration_to_minutes(None) is None


def test_ovmro_row_uses_stated_fields_not_regex_extraction():
    """
    OVMRO's scraper pre-parses date/location/duration/casualties directly
    from the source table, so cleaning should use those fields as-is
    rather than re-extracting them from narrative text the way it has to
    for Edale. This is a real row from the live site, included verbatim
    as a regression fixture.
    """
    import json
    from pathlib import Path
    import tempfile
    from clean_incidents import clean_team_file

    raw = [{
        "source_team_id": "ovmro",
        "source_method": "html_scrape_rendered_table",
        "title_raw": "12 Llyn Crafant, Mannod Quarry",
        "content_text": (
            "A pair of climbers were drytooling at a quarry near Crafnant when one of "
            "them felt unwell and then collapsed. Despite attempts to resuscitate him, "
            "the casualty sadly died at the scene and was later evacuated from the "
            "quarry by the team."
        ),
        "location_text_stated": "Llyn Crafant, Mannod Quarry",
        "date_raw_ddmmyyyy": "03/02/2026",
        "duration_raw": "06:08",
        "casualties_count": "1",
        "team_members_attended": "19",
        "link": "https://ogwen-rescue.org.uk/incident-details/",
    }]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = Path(tmp) / "ovmro_incidents_raw.json"
        raw_path.write_text(json.dumps(raw))
        df = clean_team_file(raw_path)

    row = df.iloc[0]
    assert row["location_text"] == "Llyn Crafant, Mannod Quarry"
    assert row["date"] == "2026-02-03"
    assert row["time"] is None
    assert row["duration_minutes"] == 368
    assert row["casualties_count"] == 1
    assert row["team_members_attended"] == 19