"""
join_weather.py

Merges the per-region daily weather pulled by fetch_weather.py onto the
cleaned incidents table, matched on (region, date). Writes
incidents_with_weather.csv to interim/, which becomes the input to
geocoding instead of the plain incidents_cleaned.csv.

A row with no date, or a date outside the fetched weather range (which
shouldn't happen given fetch_weather.py derives the range from the data
itself, but worth guarding anyway), gets null weather columns rather
than the row being dropped — an incident without a matched location or
weather reading is still a real incident and stays in the dataset.
"""

import json
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
INTERIM_DIR = Path(__file__).resolve().parents[1] / "data" / "interim"

TEAM_REGION = {
    "edale": "Peak District",
    "buxton": "Peak District",
    "wasdale": "Lake District",
    "ovmro": "Snowdonia (Eryri)",
}

REGION_FILE_KEY = {
    "Peak District": "peak_district",
    "Lake District": "lake_district",
    "Snowdonia (Eryri)": "snowdonia",
}

# Open-Meteo's weathercode is a WMO code — collapsed here into a small
# number of human-readable buckets, since "weathercode 61" means
# nothing to a reader of a chart. Not every WMO code is enumerated;
# anything not explicitly listed falls back to "other".
WEATHERCODE_BUCKETS = {
    **{c: "clear" for c in (0, 1)},
    **{c: "cloudy" for c in (2, 3, 45, 48)},
    **{c: "rain" for c in (51, 53, 55, 61, 63, 65, 80, 81, 82)},
    **{c: "snow" for c in (71, 73, 75, 77, 85, 86)},
    **{c: "storm" for c in (95, 96, 99)},
}


def _load_region_weather(region):
    key = REGION_FILE_KEY[region]
    path = RAW_DIR / f"weather_{key}.json"
    if not path.exists():
        return None

    raw = json.loads(path.read_text(encoding="utf-8"))
    daily = raw.get("daily", {})
    if not daily:
        return None

    weather_df = pd.DataFrame({
        "date": pd.array(daily["time"], dtype="string"),
        "temp_max_c": daily["temperature_2m_max"],
        "temp_min_c": daily["temperature_2m_min"],
        "precipitation_mm": daily["precipitation_sum"],
        "wind_speed_max_kmh": daily["windspeed_10m_max"],
        "weathercode": daily["weathercode"],
    })
    weather_df["weather_summary"] = weather_df["weathercode"].map(
        lambda c: WEATHERCODE_BUCKETS.get(c, "other")
    )
    return weather_df


def main():
    cleaned_path = INTERIM_DIR / "incidents_cleaned.csv"
    if not cleaned_path.exists():
        print("no cleaned incidents found — run the pipeline's cleaning step first")
        return

    incidents = pd.read_csv(cleaned_path)
    incidents["region"] = incidents["source_team_id"].map(TEAM_REGION)

    # Pin the date column to a consistent nullable string dtype before
    # merging. Without this, a batch where every date happens to be
    # null gets inferred by pandas as float64 (NaN), which then fails
    # to merge against the weather table's string dates with a dtype
    # error — caught by test_undated_row_kept_with_null_weather_not_dropped
    # rather than assumed safe.
    incidents["date"] = incidents["date"].astype("string")

    weather_frames = []
    for region in incidents["region"].dropna().unique():
        weather_df = _load_region_weather(region)
        if weather_df is None:
            print(f"  no weather data found for {region} — run fetch_weather.py first. "
                  f"Continuing with null weather for this region's incidents.")
            continue
        weather_df["region"] = region
        weather_frames.append(weather_df)

    if weather_frames:
        all_weather = pd.concat(weather_frames, ignore_index=True)
        merged = incidents.merge(all_weather, on=["region", "date"], how="left")
    else:
        merged = incidents.copy()
        for col in ["temp_max_c", "temp_min_c", "precipitation_mm", "wind_speed_max_kmh", "weather_summary"]:
            merged[col] = None

    matched = merged["weather_summary"].notna().sum()
    print(f"  matched weather for {matched}/{len(merged)} incidents")

    out_path = INTERIM_DIR / "incidents_with_weather.csv"
    merged.to_csv(out_path, index=False, encoding="utf-8")
    print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()