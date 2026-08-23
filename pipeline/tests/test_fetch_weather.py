"""
test_fetch_weather.py

Regression test for a real bug found on a live pipeline run: two rows
with implausible mis-parsed dates (year 0820 and year 2109) skewed the
date range sent to Open-Meteo's API, which correctly rejected the
request with a 400 and crashed the whole pipeline run. Fixed with a
second plausibility check independent of the one in clean_incidents.py,
so one bad date can't take the weather step down.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "weather"))

import fetch_weather


@pytest.fixture
def weather_dirs(tmp_path, monkeypatch):
    interim = tmp_path / "interim"
    raw = tmp_path / "raw"
    interim.mkdir()
    raw.mkdir()
    monkeypatch.setattr(fetch_weather, "INTERIM_DIR", interim)
    monkeypatch.setattr(fetch_weather, "RAW_DIR", raw)
    return interim, raw


def test_implausible_dates_excluded_from_range(weather_dirs):
    interim, raw = weather_dirs

    pd.DataFrame([
        {"source_team_id": "edale", "location_text": "Kinder Scout", "date": "2026-01-05"},
        {"source_team_id": "edale", "location_text": "Bad Row A", "date": "0820-02-27"},
        {"source_team_id": "edale", "location_text": "Bad Row B", "date": "2109-11-08"},
        {"source_team_id": "edale", "location_text": "Mam Tor", "date": "2026-06-20"},
    ]).to_csv(interim / "incidents_cleaned.csv", index=False)

    fake_response = MagicMock()
    fake_response.json.return_value = {"daily": {
        "time": [], "temperature_2m_max": [], "temperature_2m_min": [],
        "precipitation_sum": [], "windspeed_10m_max": [], "weathercode": [],
    }}

    with patch("fetch_weather._get", return_value=fake_response) as mock_get:
        fetch_weather.main()  # should not raise
        _, kwargs = mock_get.call_args_list[0]

    assert kwargs["params"]["start_date"] == "2026-01-05"
    assert kwargs["params"]["end_date"] == "2026-06-20"