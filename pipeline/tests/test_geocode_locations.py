"""
test_geocode_locations.py

Tests for extract_place_name_for_geocoding — the heuristic built to
fix UWFRA's ~1% geocode match rate. Root cause: UWFRA's location_text
is the full incident title ("Female fallen Bolton Abbey"), not a clean
place name, and sending that whole title as a Nominatim query performs
badly since Nominatim is a place-name search engine, not an NLP
entity extractor.

Verified against 20 real UWFRA titles (all pulled from actual fetched
HTML, not invented) before ever being wired into the pipeline —
listed here in full so the test suite documents exactly what's been
checked, not just a couple of convenient examples.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "geocode"))

from geocode_locations import extract_place_name_for_geocoding

# Every real UWFRA title available at the time this was built, with
# the expected extraction. Half have no genuine place name at all
# ("Sheep stuck in a bog") and must correctly return None rather than
# guessing — extracting a wrong "place" would be worse than admitting
# there isn't one to find.
REAL_TITLE_CASES = [
    ("Female fallen Bolton Abbaey", "Bolton Abbaey"),
    ("Injury Scar House Reservoir", "Scar House Reservoir"),
    ("Sheep stuck in a bog", None),
    ("Injury Nidd Gorge", "Nidd Gorge"),
    ("Male suspected stroke Trollers Gill", "Trollers Gill"),
    ("Moblity scooter rescue", None),
    ("Male rescue Gargrave", "Gargrave"),
    ("Female in river", None),
    ("Cragfast Brimham Rocks", "Brimham Rocks"),
    ("Fallen horse rider East Marton", "East Marton"),
    ("Assist ambulance service Riffa Woods", "Riffa Woods"),
    ("Stranded sheep", None),
    ("Female fallen off cycle", None),
    ("Male injured How Stean Gorge", "How Stean Gorge"),
    ("Male fallen from mountain bike", None),
    ("Fallen youth Brimham Rocks", "Brimham Rocks"),
    ("Incident Bolon Abbey", "Bolon Abbey"),
    ("Hight risk missing person Grassington", "Grassington"),
    ("Injured female Skipton Woods", "Skipton Woods"),
    ("Dog rescue North York Moors", "North York Moors"),
]


def test_extraction_against_every_real_title():
    for title, expected in REAL_TITLE_CASES:
        assert extract_place_name_for_geocoding(title) == expected, (
            f"extract_place_name_for_geocoding({title!r}) did not match expected {expected!r}"
        )


def test_source_typos_preserved_not_corrected():
    """
    "Bolon Abbey" (missing a 't') and "Bolton Abbaey" (extra 'e') are
    both real typos in the source data. This project doesn't silently
    "fix" published source text — the extracted query should carry the
    typo through exactly as published, same principle already applied
    elsewhere (e.g. duration/attendee values).
    """
    assert extract_place_name_for_geocoding("Incident Bolon Abbey") == "Bolon Abbey"
    assert extract_place_name_for_geocoding("Female fallen Bolton Abbaey") == "Bolton Abbaey"


def test_extraction_would_wrongly_truncate_other_sources_clean_names():
    """
    Documents exactly why this is UWFRA-only, not applied universally:
    the other three sources' location_text is already a clean place
    name with no descriptive prefix, so "exclude the first word" would
    wrongly chop off part of the real name.
    """
    assert extract_place_name_for_geocoding("Kinder Scout") == "Scout"  # would be WRONG to use
    assert extract_place_name_for_geocoding("Great Gable") == "Gable"  # would be WRONG to use
    assert extract_place_name_for_geocoding("Tryfan") is None  # single word, would be WRONG to use


def test_geocode_all_only_applies_extraction_to_uwfra():
    """
    Confirms the actual wiring in geocode_all(), not just the
    standalone function: a non-UWFRA row's Nominatim query must use
    the raw location_text unmodified, while a UWFRA row's query must
    use the extracted place name.
    """
    import pandas as pd
    from unittest.mock import patch, MagicMock
    import geocode_locations

    captured_queries = []

    def fake_geocode(query, **kwargs):
        captured_queries.append(query)
        return None  # no_match is fine — we're only checking what query was sent

    df = pd.DataFrame({
        "location_text": ["Kinder Scout", "Female fallen Bolton Abbaey"],
        "source_team_id": ["edale", "uwfra"],
    })

    with patch.object(geocode_locations, "Nominatim") as mock_nominatim_cls, \
         patch.object(geocode_locations, "_load_cache", return_value={}), \
         patch.object(geocode_locations, "_save_cache"), \
         patch("time.sleep"):
        mock_geolocator = MagicMock()
        mock_geolocator.geocode.side_effect = fake_geocode
        mock_nominatim_cls.return_value = mock_geolocator

        geocode_locations.geocode_all(df)

    assert captured_queries[0].startswith("Kinder Scout,")  # Edale: unmodified
    assert captured_queries[1].startswith("Bolton Abbaey,")  # UWFRA: extracted, not full title