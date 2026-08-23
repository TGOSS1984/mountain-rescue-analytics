"""
geocode_locations.py

Turns the free-text `location_text` field (e.g. "Chatsworth Edge",
"Mam Tor", "Wyming brook") into coordinates, so incidents can be plotted
on a map instead of just listed.

Uses Nominatim (OpenStreetMap's geocoder) via geopy, biased toward the
Peak District bounding box since that's where these teams operate — an
unqualified search for "Buxton" would otherwise happily return matches
worldwide.

Two things worth being honest about, and both are written straight into
the output columns rather than buried in a log file:

  - `geocode_confidence`: Nominatim doesn't return a confidence score
    directly, so this is derived from how specific the match type is
    (e.g. "peak" or "natural" is high confidence; a generic fallback to
    the surrounding parish is low). A dashboard built on this data should
    treat "low" confidence points as approximate, not precise.
  - `geocode_status`: "matched", "no_match", or "skipped" (skipped =
    already cached from a previous run, or location_text was empty).
    A "no_match" row still gets kept in the dataset — it lands on the
    incidents table without coordinates, so it's visible in raw counts
    even though it can't be plotted.

Nominatim's usage policy caps requests at 1/second and requires a
descriptive User-Agent — both are respected here. Results are cached to
disk so re-running the pipeline doesn't hammer the API for locations
we've already resolved.
"""

import json
import time
from pathlib import Path

import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

INTERIM_DIR = Path(__file__).resolve().parents[1] / "data" / "interim"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
CACHE_PATH = INTERIM_DIR / "geocode_cache.json"

# Bump this whenever the geocoding logic changes in a way that could
# change results for previously-cached queries (e.g. the viewbox shape
# fix). Cache entries written under an older version are discarded
# rather than silently reused — this is exactly the bug that made the
# viewbox fix look like it hadn't worked: the cache kept replaying
# "no_match" answers recorded by the old broken code, and nothing in
# the cache format could tell the difference between "genuinely no
# match" and "no match because the query itself was malformed."
CACHE_VERSION = 2

# Rough bounding boxes per region, so "Kinder" (Peak District) and
# "Kinder-alike-sounding-place-in-Wales" don't collide, and so a bare
# "Great Gable" gets biased toward the Lake District rather than
# returning the first global match.
#
# geopy's Nominatim.geocode(viewbox=...) expects exactly two points, each
# as (latitude, longitude) — NOT a flat (west, north, east, south) tuple.
# An earlier version of this file used the flat 4-value shape, which
# geopy silently mishandled: combined with bounded=True, every single
# query came back with no result, and because that's not an exception,
# nothing here caught it — it just looked like "no matches anywhere,"
# which is exactly the 0/1197 the pipeline produced. Each entry below is
# (north-west corner, south-east corner) as (lat, lon) pairs.
REGION_VIEWBOXES = {
    "Peak District": ((53.55, -2.05), (53.05, -1.45)),
    "Lake District": ((54.75, -3.65), (54.30, -2.70)),
    "Snowdonia (Eryri)": ((53.25, -4.30), (52.85, -3.60)),
}

# Query suffix appended to each location before geocoding. Diagnostic
# testing against the live site (see pipeline/diagnostics/) showed that
# chaining region+county+country terms actively breaks matching —
# "Tryfan, Snowdonia, Gwynedd, UK" returned nothing, while bare "Tryfan"
# matched instantly and correctly. Nominatim's free-text matcher expects
# terms to correspond to its actual place hierarchy, and "Snowdonia"
# isn't indexed the way you'd expect (the boundary is "Eryri National
# Park" in OSM) — so a "helpful" region suffix was actively hurting the
# match rather than disambiguating it. Kept to just "UK" here: enough to
# avoid wildly wrong-country matches, while letting the bounded viewbox
# (not the query text) do the actual regional disambiguation.
REGION_QUERY_SUFFIX = {
    "Peak District": "UK",
    "Lake District": "UK",
    "Snowdonia (Eryri)": "UK",
}

TEAM_REGION = {
    "edale": "Peak District",
    "buxton": "Peak District",
    "wasdale": "Lake District",
    "ovmro": "Snowdonia (Eryri)",
}
HIGH_CONFIDENCE_TYPES = {"peak", "natural", "water", "hill", "valley"}


def _load_cache():
    if not CACHE_PATH.exists():
        return {}
    raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    # Old cache files (pre-versioning) are a flat dict of entries with
    # no version marker at all — treat those as version 0, which never
    # matches CACHE_VERSION, so they get discarded below rather than
    # crashing on a missing key.
    if raw.get("_cache_version") != CACHE_VERSION:
        print(f"  (geocode cache is from an older code version — starting fresh "
              f"rather than reusing potentially-stale answers)")
        return {}
    return raw.get("entries", {})


def _save_cache(cache):
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"_cache_version": CACHE_VERSION, "entries": cache}
    CACHE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def geocode_all(df, location_col="location_text", team_col="source_team_id"):
    geolocator = Nominatim(user_agent="mountain-rescue-analytics-portfolio-project", timeout=10)
    cache = _load_cache()

    lats, lons, statuses, confidences = [], [], [], []

    total = len(df)
    lookups_since_save = 0
    new_lookups_done = 0
    cache_hits = 0

    for i, (location_text, team_id) in enumerate(zip(df[location_col], df[team_col]), start=1):
        region = TEAM_REGION.get(team_id, "Peak District")
        viewbox = REGION_VIEWBOXES[region]
        query_suffix = REGION_QUERY_SUFFIX[region]

        key = f"{team_id}:{(location_text or '').strip().lower()}"

        if not location_text or not str(location_text).strip():
            lats.append(None); lons.append(None)
            statuses.append("skipped"); confidences.append(None)
            continue

        if key in cache:
            hit = cache[key]
            lats.append(hit["lat"]); lons.append(hit["lon"])
            statuses.append(hit["status"]); confidences.append(hit["confidence"])
            cache_hits += 1
            continue

        # Anchor the search to "<place>, <region>, UK" — source location
        # names are often single words ("Kinder", "Win Hill", "Tryfan")
        # that are ambiguous without regional context, and the same name
        # can plausibly exist in more than one of our three regions.
        query = f"{location_text}, {query_suffix}"

        # Progress feedback: this step is genuinely slow (Nominatim's
        # usage policy caps us at ~1 request/second) and prints nothing
        # by default, which is indistinguishable from having hung. A
        # thousand-plus incidents with many unique locations can take
        # 15-25+ minutes on a first run — this line is what tells you
        # it's working, not frozen.
        print(f"  [{i}/{total}] geocoding new location: {location_text!r} ({region})", flush=True)

        try:
            result = geolocator.geocode(
                query, viewbox=viewbox, bounded=True, addressdetails=True
            )
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            print(f"    -> request failed ({e}), recording as no_match and continuing")
            result = None

        if result:
            place_type = getattr(result, "raw", {}).get("type", "")
            confidence = "high" if place_type in HIGH_CONFIDENCE_TYPES else "low"
            entry = {
                "lat": result.latitude, "lon": result.longitude,
                "status": "matched", "confidence": confidence,
            }
        else:
            entry = {"lat": None, "lon": None, "status": "no_match", "confidence": None}

        cache[key] = entry
        lats.append(entry["lat"]); lons.append(entry["lon"])
        statuses.append(entry["status"]); confidences.append(entry["confidence"])
        new_lookups_done += 1
        lookups_since_save += 1

        # Save the cache periodically, not just once at the very end.
        # Without this, killing the process (e.g. because it *looked*
        # stuck) or a network drop partway through would silently throw
        # away every lookup done so far, forcing a full restart from
        # zero. Every 20 new lookups is a reasonable balance between
        # "don't lose much work" and "don't hammer disk I/O."
        if lookups_since_save >= 20:
            _save_cache(cache)
            lookups_since_save = 0
            print(f"    (progress saved to cache — {new_lookups_done} new lookups so far)")

        time.sleep(1.1)  # Nominatim usage policy: max 1 request/second

    df = df.copy()
    df["lat"] = lats
    df["lon"] = lons
    df["geocode_status"] = statuses
    df["geocode_confidence"] = confidences

    _save_cache(cache)
    print(f"  done — {cache_hits} rows from cache, {new_lookups_done} new lookups made")
    return df


def main():
    # Reads the weather-joined file rather than the plain cleaned one —
    # weather enrichment happens between cleaning/validation and
    # geocoding in the pipeline order (see run_pipeline.py), so by this
    # point every row that has a weather match already carries it.
    in_path = INTERIM_DIR / "incidents_with_weather.csv"
    if not in_path.exists():
        print("no cleaned incidents found — run pipeline/clean/clean_incidents.py first")
        return

    df = pd.read_csv(in_path)
    print(f"geocoding {len(df)} incidents…")
    print("this can take a while on a first run — Nominatim's usage policy caps us at "
          "~1 request/second, and every unique location needs its own request. Progress "
          "prints below as it goes, and results are saved incrementally, so it's safe to "
          "stop and resume rather than risk losing everything if it looks slow.")
    df = geocode_all(df)

    matched = (df["geocode_status"] == "matched").sum()
    print(f"matched {matched}/{len(df)} locations")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "incidents_geocoded.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()