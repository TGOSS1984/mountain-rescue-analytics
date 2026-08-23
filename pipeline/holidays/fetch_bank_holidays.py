"""
fetch_bank_holidays.py

Adds is_bank_holiday, day_of_week, and is_weekend to every incident,
using the UK government's free bank holidays API
(https://www.gov.uk/bank-holidays.json — no key, no auth, one request
for the whole dataset since it's not location-dependent).

All three of our regions (Peak District, Lake District, Snowdonia)
fall under the "england-and-wales" division, so that's the only
division used, even though the source also publishes Scotland and
Northern Ireland separately.

One real constraint worth being upfront about: this API only publishes
a rolling few years of data, not a full historical archive — and
Edale's incident history goes back to 2014. A date outside the range
the API actually covers is NOT assumed to be "not a holiday" (that
would be a guess dressed up as a fact); it's left null instead, same
as any other missing-data case elsewhere in this pipeline.
"""

import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
CACHE_PATH = RAW_DIR / "bank_holidays.json"
HEADERS = {
    "User-Agent": "mountain-rescue-analytics-portfolio-project "
                  "(personal, non-commercial data analysis; contact via GitHub)"
}

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _is_retryable(exception):
    if isinstance(exception, requests.HTTPError):
        status = exception.response.status_code if exception.response is not None else None
        return status is not None and status >= 500
    return isinstance(exception, (requests.ConnectionError, requests.Timeout))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)
def _get(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp


def fetch_holidays():
    print("  fetching UK bank holidays (england-and-wales)…")
    resp = _get("https://www.gov.uk/bank-holidays.json")
    data = resp.json()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    events = data["england-and-wales"]["events"]
    holiday_dates = {e["date"] for e in events}
    covered_years = {int(e["date"][:4]) for e in events}

    print(f"  {len(holiday_dates)} bank holidays covering years "
          f"{min(covered_years)}-{max(covered_years)}")
    return holiday_dates, covered_years


def classify_date(date_str, holiday_dates, covered_years):
    if pd.isna(date_str):
        return None, None, None

    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None, None, None

    day_of_week = DAY_NAMES[parsed.weekday()]
    is_weekend = parsed.weekday() >= 5

    if parsed.year in covered_years:
        is_bank_holiday = date_str in holiday_dates
    else:
        # Outside the range this API actually publishes — an honest
        # "don't know" rather than a guessed False. See module docstring.
        is_bank_holiday = None

    return is_bank_holiday, day_of_week, is_weekend


def main():
    in_path = PROCESSED_DIR / "incidents_geocoded.csv"
    if not in_path.exists():
        print("no geocoded incidents found — run the pipeline up to geocoding first")
        return

    holiday_dates, covered_years = fetch_holidays()

    df = pd.read_csv(in_path)
    classified = df["date"].apply(lambda d: classify_date(d, holiday_dates, covered_years))
    df["is_bank_holiday"] = classified.apply(lambda t: t[0])
    df["day_of_week"] = classified.apply(lambda t: t[1])
    df["is_weekend"] = classified.apply(lambda t: t[2])

    holiday_known = df["is_bank_holiday"].notna().sum()
    holiday_true = (df["is_bank_holiday"] == True).sum()
    print(f"  bank holiday status known for {holiday_known}/{len(df)} incidents "
          f"({holiday_true} were on a bank holiday)")

    out_path = PROCESSED_DIR / "incidents_geocoded.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()