"""
fetch_weather.py

Pulls historical daily weather for each region, covering the full date
range of that region's incidents, from Open-Meteo's free historical
archive API (no key required: https://open-meteo.com/en/docs/historical-weather-api).

One call per region, not one per incident — Open-Meteo's archive
endpoint takes a start/end date range and returns every day in between
in a single response, so three regions means three requests total,
regardless of whether there are 100 incidents or 10,000.

Each region is represented by a single reference point (roughly its
geographic centre) rather than each incident's own coordinates. That's
a deliberate simplification worth being upfront about: weather at
Kinder Scout and weather at Stanage Edge on the same day are close
enough for "was it a wet week" analysis, but this is regional daily
weather, not a precise per-incident reading. See docs/data-dictionary.md.
"""

import json
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
INTERIM_DIR = Path(__file__).resolve().parents[1] / "data" / "interim"
HEADERS = {
    "User-Agent": "mountain-rescue-analytics-portfolio-project "
                  "(personal, non-commercial data analysis; contact via GitHub)"
}

# One reference point per region — roughly the geographic centre of
# where each team operates, not any single peak. Good enough for daily
# regional weather; see module docstring for the precision trade-off.
REGION_REFERENCE_POINTS = {
    "Peak District": (53.30, -1.75),
    "Lake District": (54.45, -3.20),
    "Snowdonia (Eryri)": (53.10, -3.95),
    "Yorkshire Dales": (54.05, -1.90),  # near Grassington, UWFRA's own base
}

TEAM_REGION = {
    "edale": "Peak District",
    "buxton": "Peak District",
    "wasdale": "Lake District",
    "ovmro": "Snowdonia (Eryri)",
    "uwfra": "Yorkshire Dales",
}

DAILY_VARIABLES = "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,weathercode,sunrise,sunset"


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
def _get(url, params):
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp


def fetch_region_weather(region, start_date, end_date):
    lat, lon = REGION_REFERENCE_POINTS[region]
    print(f"  fetching {region} weather, {start_date} to {end_date}…")
    resp = _get(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "daily": DAILY_VARIABLES,
            "timezone": "auto",
        },
    )
    return resp.json()


MIN_PLAUSIBLE_YEAR = 2010
MAX_PLAUSIBLE_YEAR = 2035


def main():
    cleaned_path = INTERIM_DIR / "incidents_cleaned.csv"
    if not cleaned_path.exists():
        print("no cleaned incidents found — run the pipeline's cleaning step first")
        return

    df = pd.read_csv(cleaned_path)
    df["region"] = df["source_team_id"].map(TEAM_REGION)

    # Second line of defence, independent of the plausibility check
    # already applied during cleaning (clean_incidents.py). A bad date
    # reaching this step would otherwise silently produce a garbage
    # start_date/end_date range sent straight to Open-Meteo's API — on
    # a real run this happened for real (a date parsed as year 0820 and
    # another as year 2109), and the API correctly rejected the request
    # with a 400, but only after crashing the whole pipeline run rather
    # than skipping the bad row. Filtering here means one corrupted
    # date can't take down the entire weather-fetching step.
    valid_years = pd.to_datetime(df["date"], errors="coerce").dt.year
    implausible = df["date"].notna() & (
        valid_years.isna() | ~valid_years.between(MIN_PLAUSIBLE_YEAR, MAX_PLAUSIBLE_YEAR)
    )
    if implausible.any():
        print(f"  WARNING: {implausible.sum()} row(s) have an implausible date "
              f"(outside {MIN_PLAUSIBLE_YEAR}-{MAX_PLAUSIBLE_YEAR}) — excluding from the "
              f"weather date-range calculation rather than letting them skew it:")
        for _, row in df[implausible].iterrows():
            print(f"    {row['source_team_id']} / {row['location_text']!r} -> date={row['date']!r}")
        df.loc[implausible, "date"] = None

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for region in df["region"].dropna().unique():
        region_dates = df.loc[df["region"] == region, "date"].dropna()
        if region_dates.empty:
            print(f"  {region}: no dated incidents, skipping")
            continue

        start_date, end_date = region_dates.min(), region_dates.max()
        data = fetch_region_weather(region, start_date, end_date)

        safe_name = region.split(" (")[0].lower().replace(" ", "_")
        out_path = RAW_DIR / f"weather_{safe_name}.json"
        out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()