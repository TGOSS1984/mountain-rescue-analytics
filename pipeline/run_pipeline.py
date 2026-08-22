"""
run_pipeline.py

Runs the full chain: scrape -> clean -> validate -> geocode -> report.
Each step's output is written to disk before the next step starts, so if
something fails partway through, you can inspect exactly what the
previous step produced rather than re-running everything blind.

Usage:
    python run_pipeline.py             # full run
    python run_pipeline.py --skip-scrape   # reuse existing raw/ files
                                            # (useful once you've scraped
                                            # once and are iterating on
                                            # cleaning/validation logic)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "ingest"))
sys.path.insert(0, str(Path(__file__).parent / "clean"))
sys.path.insert(0, str(Path(__file__).parent / "validate"))
sys.path.insert(0, str(Path(__file__).parent / "geocode"))

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-scrape", action="store_true",
                         help="reuse existing files in pipeline/data/raw/ instead of re-scraping")
    args = parser.parse_args()

    print("=" * 60)
    if not args.skip_scrape:
        print("STEP 1/4 — scraping team incident logs")
        import scrape_team_incidents
        scrape_team_incidents.main()
    else:
        print("STEP 1/4 — skipped (--skip-scrape), using existing raw data")

    print("=" * 60)
    print("STEP 2/4 — cleaning and standardising")
    import clean_incidents
    clean_incidents.main()

    print("=" * 60)
    print("STEP 3/4 — validating against schema")
    import schema
    interim_path = Path(__file__).parent / "data" / "interim" / "incidents_cleaned.csv"
    df = pd.read_csv(interim_path)
    try:
        schema.validate(df)
        print(f"validation passed — {len(df)} rows")
    except Exception as e:
        print("VALIDATION FAILED — stopping before geocoding.")
        print("Fix the cleaning logic or the schema, don't loosen the schema just to pass.")
        print(e)
        sys.exit(1)

    print("=" * 60)
    print("STEP 4/4 — geocoding locations")
    import geocode_locations
    geocode_locations.main()

    print("=" * 60)
    print("Pipeline complete. Output: pipeline/data/processed/incidents_geocoded.csv")


if __name__ == "__main__":
    main()