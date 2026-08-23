"""
test_fetch_elevation.py

Verifies the batching (100-coordinate limit), deduplication (shared
coordinates share one elevation value, not a fresh lookup each time),
and caching behaviour (a second run makes zero new API calls).
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "elevation"))

import fetch_elevation


@pytest.fixture
def elevation_dirs(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    interim = tmp_path / "interim"
    processed.mkdir()
    interim.mkdir()
    monkeypatch.setattr(fetch_elevation, "PROCESSED_DIR", processed)
    monkeypatch.setattr(fetch_elevation, "INTERIM_DIR", interim)
    monkeypatch.setattr(fetch_elevation, "CACHE_PATH", interim / "elevation_cache.json")
    return processed, interim


def _fake_get_factory(call_counter):
    def fake_get(url, params):
        call_counter[0] += 1
        n = len(params["latitude"].split(","))
        resp = MagicMock()
        resp.json.return_value = {"elevation": [100.0 + i for i in range(n)]}
        return resp
    return fake_get


def test_batches_over_100_coordinates_into_multiple_requests(elevation_dirs):
    processed, _ = elevation_dirs
    rows = [
        {"location_text": f"Loc{i}", "lat": 53.0 + i * 0.001, "lon": -1.8 - i * 0.001,
         "geocode_status": "matched"}
        for i in range(150)
    ]
    pd.DataFrame(rows).to_csv(processed / "incidents_geocoded.csv", index=False)

    call_count = [0]
    with patch("fetch_elevation._get", side_effect=_fake_get_factory(call_count)):
        fetch_elevation.main()

    assert call_count[0] == 2  # 150 uniques -> batches of 100 + 50


def test_shared_coordinates_get_identical_elevation(elevation_dirs):
    processed, _ = elevation_dirs
    rows = [
        {"location_text": "Kinder Scout", "lat": 53.38, "lon": -1.87, "geocode_status": "matched"},
        {"location_text": "Also Kinder Scout", "lat": 53.38, "lon": -1.87, "geocode_status": "matched"},
    ]
    pd.DataFrame(rows).to_csv(processed / "incidents_geocoded.csv", index=False)

    call_count = [0]
    with patch("fetch_elevation._get", side_effect=_fake_get_factory(call_count)):
        fetch_elevation.main()

    result = pd.read_csv(processed / "incidents_geocoded.csv")
    values = result["elevation_m"].tolist()
    assert values[0] == values[1]
    assert call_count[0] == 1  # one coordinate, one batch


def test_no_match_rows_get_null_elevation_not_error(elevation_dirs):
    processed, _ = elevation_dirs
    rows = [
        {"location_text": "Matched", "lat": 53.0, "lon": -1.8, "geocode_status": "matched"},
        {"location_text": "Unmatched", "lat": None, "lon": None, "geocode_status": "no_match"},
    ]
    pd.DataFrame(rows).to_csv(processed / "incidents_geocoded.csv", index=False)

    with patch("fetch_elevation._get", side_effect=_fake_get_factory([0])):
        fetch_elevation.main()  # should not raise

    result = pd.read_csv(processed / "incidents_geocoded.csv")
    assert result[result["location_text"] == "Unmatched"]["elevation_m"].isna().all()


def test_second_run_uses_cache_with_zero_api_calls(elevation_dirs):
    processed, _ = elevation_dirs
    rows = [{"location_text": "Kinder Scout", "lat": 53.38, "lon": -1.87, "geocode_status": "matched"}]
    pd.DataFrame(rows).to_csv(processed / "incidents_geocoded.csv", index=False)

    call_count = [0]
    with patch("fetch_elevation._get", side_effect=_fake_get_factory(call_count)):
        fetch_elevation.main()
        fetch_elevation.main()  # second run

    assert call_count[0] == 1  # only the first run should have hit the API