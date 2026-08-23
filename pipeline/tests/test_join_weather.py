"""
test_join_weather.py

Tests for the weather join logic: correct region matching, undated/
unmatched rows kept (not dropped) with null weather, and the
weathercode-to-summary bucketing.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "weather"))

from join_weather import main as join_main, WEATHERCODE_BUCKETS


@pytest.fixture
def weather_env(tmp_path, monkeypatch):
    import join_weather
    interim = tmp_path / "interim"
    raw = tmp_path / "raw"
    interim.mkdir()
    raw.mkdir()
    monkeypatch.setattr(join_weather, "INTERIM_DIR", interim)
    monkeypatch.setattr(join_weather, "RAW_DIR", raw)
    return interim, raw


def test_weather_joins_on_region_and_date(weather_env):
    interim, raw = weather_env

    pd.DataFrame([
        {"source_team_id": "edale", "location_text": "Kinder Scout", "date": "2026-01-05"},
    ]).to_csv(interim / "incidents_cleaned.csv", index=False)

    (raw / "weather_peak_district.json").write_text(json.dumps({
        "daily": {
            "time": ["2026-01-05"],
            "temperature_2m_max": [4.2], "temperature_2m_min": [0.1],
            "precipitation_sum": [12.4], "windspeed_10m_max": [38.5],
            "weathercode": [61],
        }
    }))

    join_main()
    result = pd.read_csv(interim / "incidents_with_weather.csv")

    assert result.iloc[0]["weather_summary"] == "rain"
    assert result.iloc[0]["wind_speed_max_kmh"] == 38.5


def test_undated_row_kept_with_null_weather_not_dropped(weather_env):
    interim, raw = weather_env

    pd.DataFrame([
        {"source_team_id": "edale", "location_text": "Undated", "date": None},
    ]).to_csv(interim / "incidents_cleaned.csv", index=False)

    (raw / "weather_peak_district.json").write_text(json.dumps({
        "daily": {"time": ["2026-01-05"], "temperature_2m_max": [4.2],
                  "temperature_2m_min": [0.1], "precipitation_sum": [0.0],
                  "windspeed_10m_max": [10.0], "weathercode": [1]}
    }))

    join_main()
    result = pd.read_csv(interim / "incidents_with_weather.csv")

    assert len(result) == 1
    assert pd.isna(result.iloc[0]["weather_summary"])


def test_missing_region_weather_file_does_not_crash(weather_env):
    """If fetch_weather.py hasn't been run for a region yet, joining
    should degrade to null weather for that region's rows, not error out."""
    interim, raw = weather_env

    pd.DataFrame([
        {"source_team_id": "ovmro", "location_text": "Tryfan", "date": "2026-03-01"},
    ]).to_csv(interim / "incidents_cleaned.csv", index=False)
    # deliberately no weather_snowdonia.json written

    join_main()  # should not raise
    result = pd.read_csv(interim / "incidents_with_weather.csv")

    assert len(result) == 1
    assert pd.isna(result.iloc[0]["weather_summary"])


def test_weathercode_bucketing_covers_common_codes():
    assert WEATHERCODE_BUCKETS[0] == "clear"
    assert WEATHERCODE_BUCKETS[61] == "rain"
    assert WEATHERCODE_BUCKETS[95] == "storm"
    assert WEATHERCODE_BUCKETS[71] == "snow"
    # A code not in the map should simply not be present, so callers
    # relying on .get(code, "other") get the fallback rather than a
    # KeyError — this test would fail loudly if the bucketing map ever
    # accidentally covered every possible code and hid that fallback path.
    assert 42 not in WEATHERCODE_BUCKETS


def test_extract_hhmm_from_openmeteo_iso_format():
    from join_weather import _extract_hhmm
    assert _extract_hhmm("2026-01-05T08:12") == "08:12"
    assert _extract_hhmm(None) is None
    assert _extract_hhmm(float("nan")) is None


def test_daylight_status_winter_and_summer_boundaries():
    """
    Tests the actual claim Wasdale made in their own safety message
    (a rise in incidents from walkers becoming benighted without a
    head torch) is computable at all — boundary-inclusive on both
    sunrise and sunset, correct for both a short winter day and a long
    summer one.
    """
    from join_weather import compute_daylight_status

    # Winter: sunrise 08:12, sunset 16:30
    assert compute_daylight_status("14:30", "08:12", "16:30") == "daylight"
    assert compute_daylight_status("17:45", "08:12", "16:30") == "darkness"
    assert compute_daylight_status("07:00", "08:12", "16:30") == "darkness"
    assert compute_daylight_status("08:12", "08:12", "16:30") == "daylight"  # sunrise boundary
    assert compute_daylight_status("16:30", "08:12", "16:30") == "daylight"  # sunset boundary

    # Summer: sunrise 04:45, sunset 21:15
    assert compute_daylight_status("20:00", "04:45", "21:15") == "daylight"
    assert compute_daylight_status("22:00", "04:45", "21:15") == "darkness"


def test_daylight_status_missing_data_returns_none():
    from join_weather import compute_daylight_status
    import pandas as pd

    assert compute_daylight_status(None, "08:12", "16:30") is None
    assert compute_daylight_status("14:00", "08:12", pd.NA) is None
    assert compute_daylight_status("14:00", pd.NA, "16:30") is None


def test_ovmro_rows_never_get_daylight_status(weather_env):
    """
    OVMRO structurally never has an incident time (see
    clean_incidents.py), so daylight_status must be null for every
    OVMRO row even when weather data itself matched successfully —
    the same honest gap already documented for the time-of-day chart.
    """
    interim, raw = weather_env

    pd.DataFrame([
        {"source_team_id": "ovmro", "location_text": "Tryfan", "date": "2026-01-05", "time": None},
    ]).to_csv(interim / "incidents_cleaned.csv", index=False)

    (raw / "weather_snowdonia.json").write_text(json.dumps({
        "daily": {
            "time": ["2026-01-05"],
            "temperature_2m_max": [4.0], "temperature_2m_min": [0.0],
            "precipitation_sum": [0.0], "windspeed_10m_max": [10.0], "weathercode": [1],
            "sunrise": ["2026-01-05T08:30"], "sunset": ["2026-01-05T16:15"],
        }
    }))

    join_main()
    result = pd.read_csv(interim / "incidents_with_weather.csv")

    assert result.iloc[0]["weather_summary"] == "clear"  # weather itself did match
    assert pd.isna(result.iloc[0]["daylight_status"])  # but daylight status can't be computed