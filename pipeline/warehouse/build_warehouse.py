"""
build_warehouse.py

Loads pipeline/data/processed/incidents_geocoded.csv into a proper
SQLite database at pipeline/data/processed/incidents.db, which is what
the API actually queries.

This is a genuinely separate step from geocoding, not just "save as a
different file format" — it's where the flat CSV becomes something with
real types, an index, and a queryable shape, and it's the natural place
to do a final pass of sanity checks (e.g. lat/lon actually within the
UK) before anything downstream trusts the data.
"""

import sqlite3
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
CSV_PATH = PROCESSED_DIR / "incidents_geocoded.csv"
DB_PATH = PROCESSED_DIR / "incidents.db"

# Rough sanity bounds for the whole of England & Wales — catches a
# geocoding result that's technically "matched" but wildly wrong (e.g.
# Nominatim resolving an ambiguous name to a same-named place in another
# country), which a naive "did it match" check wouldn't catch.
UK_LAT_RANGE = (49.5, 61.0)
UK_LON_RANGE = (-8.5, 2.0)


def build():
    if not CSV_PATH.exists():
        print(f"no geocoded data found at {CSV_PATH} — run the full pipeline first")
        return

    df = pd.read_csv(CSV_PATH)
    print(f"loaded {len(df)} rows from {CSV_PATH.name}")

    # Flag (not drop) matched coordinates that fall outside a sane UK
    # bounding box — a genuine edge case worth surfacing rather than
    # silently trusting every "matched" status.
    out_of_bounds = df[
        df["lat"].notna()
        & (
            ~df["lat"].between(*UK_LAT_RANGE)
            | ~df["lon"].between(*UK_LON_RANGE)
        )
    ]
    if len(out_of_bounds):
        print(f"WARNING: {len(out_of_bounds)} matched rows have coordinates outside "
              f"a sane UK bounding box — worth a manual look:")
        for _, row in out_of_bounds.iterrows():
            print(f"  {row['source_team_id']} / {row['location_text']!r} -> "
                  f"({row['lat']}, {row['lon']})")

    conn = sqlite3.connect(DB_PATH)
    df.to_sql("incidents", conn, if_exists="replace", index=False)

    # Indexes on the columns the API will actually filter by — this is
    # a small dataset so it wouldn't be *slow* without them, but it's
    # the honest, correct thing to do for a table meant to be queried.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_team ON incidents(source_team_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_date ON incidents(date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_incidents_activity ON incidents(activity_type)")
    conn.commit()
    conn.close()

    print(f"wrote {len(df)} rows to {DB_PATH}")


if __name__ == "__main__":
    build()