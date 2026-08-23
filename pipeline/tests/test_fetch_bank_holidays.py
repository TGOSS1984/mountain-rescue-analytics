"""
test_fetch_bank_holidays.py

Verifies bank holiday classification, day-of-week/weekend derivation,
and — the important one — that a date outside the API's actually-
published range gets an honest null rather than a falsely confident
"not a holiday". Edale's incident history goes back to 2014; the
gov.uk API typically only covers a rolling few-year window, so this
case is a real, expected part of the dataset, not an edge case.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "holidays"))

import fetch_bank_holidays


@pytest.fixture
def holiday_dirs(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    raw = tmp_path / "raw"
    processed.mkdir()
    raw.mkdir()
    monkeypatch.setattr(fetch_bank_holidays, "PROCESSED_DIR", processed)
    monkeypatch.setattr(fetch_bank_holidays, "RAW_DIR", raw)
    monkeypatch.setattr(fetch_bank_holidays, "CACHE_PATH", raw / "bank_holidays.json")
    return processed, raw


def _fake_response():
    resp = MagicMock()
    resp.json.return_value = {
        "england-and-wales": {
            "division": "england-and-wales",
            "events": [
                {"title": "New Year's Day", "date": "2026-01-01", "notes": "", "bunting": True},
                {"title": "Good Friday", "date": "2026-04-03", "notes": "", "bunting": False},
                {"title": "Christmas Day", "date": "2026-12-25", "notes": "", "bunting": True},
            ],
        }
    }
    return resp


def test_known_holiday_correctly_flagged(holiday_dirs):
    processed, _ = holiday_dirs
    pd.DataFrame([{"location_text": "A", "date": "2026-01-01"}]).to_csv(
        processed / "incidents_geocoded.csv", index=False
    )
    with patch("fetch_bank_holidays._get", return_value=_fake_response()):
        fetch_bank_holidays.main()

    result = pd.read_csv(processed / "incidents_geocoded.csv")
    assert result.iloc[0]["is_bank_holiday"] == True


def test_ordinary_in_range_date_confidently_false(holiday_dirs):
    processed, _ = holiday_dirs
    pd.DataFrame([{"location_text": "B", "date": "2026-01-02"}]).to_csv(
        processed / "incidents_geocoded.csv", index=False
    )
    with patch("fetch_bank_holidays._get", return_value=_fake_response()):
        fetch_bank_holidays.main()

    result = pd.read_csv(processed / "incidents_geocoded.csv")
    assert result.iloc[0]["is_bank_holiday"] == False


def test_date_outside_covered_range_is_null_not_false(holiday_dirs):
    """
    The core reason this module exists in this careful form: a real
    2014 Edale-era date, outside the API's published range, must not
    be silently marked "not a holiday" — that would be a guess
    presented as fact.
    """
    processed, _ = holiday_dirs
    pd.DataFrame([{"location_text": "D", "date": "2014-06-22"}]).to_csv(
        processed / "incidents_geocoded.csv", index=False
    )
    with patch("fetch_bank_holidays._get", return_value=_fake_response()):
        fetch_bank_holidays.main()

    result = pd.read_csv(processed / "incidents_geocoded.csv")
    assert pd.isna(result.iloc[0]["is_bank_holiday"])


def test_day_of_week_and_weekend_computed_even_when_holiday_status_unknown(holiday_dirs):
    processed, _ = holiday_dirs
    pd.DataFrame([
        {"location_text": "D", "date": "2014-06-22"},   # Sunday, out of holiday range
        {"location_text": "F", "date": "2026-01-03"},   # Saturday, in range
    ]).to_csv(processed / "incidents_geocoded.csv", index=False)
    with patch("fetch_bank_holidays._get", return_value=_fake_response()):
        fetch_bank_holidays.main()

    result = pd.read_csv(processed / "incidents_geocoded.csv")
    assert result.iloc[0]["day_of_week"] == "Sunday"
    assert result.iloc[0]["is_weekend"] == True
    assert result.iloc[1]["day_of_week"] == "Saturday"
    assert result.iloc[1]["is_weekend"] == True


def test_missing_date_gives_all_nulls_not_error(holiday_dirs):
    processed, _ = holiday_dirs
    pd.DataFrame([{"location_text": "E", "date": None}]).to_csv(
        processed / "incidents_geocoded.csv", index=False
    )
    with patch("fetch_bank_holidays._get", return_value=_fake_response()):
        fetch_bank_holidays.main()  # should not raise

    result = pd.read_csv(processed / "incidents_geocoded.csv")
    assert pd.isna(result.iloc[0]["is_bank_holiday"])
    assert pd.isna(result.iloc[0]["day_of_week"])