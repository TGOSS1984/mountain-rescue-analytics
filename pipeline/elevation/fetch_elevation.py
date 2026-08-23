"""
fetch_elevation.py

Adds terrain elevation (metres) to every geocoded incident, using
Open-Meteo's free elevation API — same trusted provider as the weather
data, no separate signup needed. Runs after geocoding (needs lat/lon)
and before the warehouse build.

Batches up to 100 unique coordinates per request rather than one call
per incident — with ~900+ geocoded incidents but far fewer *unique*
locations (many incidents share a location), this is typically a
handful of requests total, not hundreds.

Rounds coordinates to 4 decimal places (~11m precision) before
deduplicating and caching — two incidents geocoded to the same named
peak will have bit-identical floats anyway, but rounding first makes
the cache robust to that assumption rather than depending on it.
"""

import json
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

INTERIM_DIR = Path(__file__).resolve().parents[1] / "data" / "interim"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
CACHE_PATH = INTERIM_DIR / "elevation_cache.json"
HEADERS = {
    "User-Agent": "mountain-rescue-analytics-portfolio-project "
                  "(personal, non-commercial data analysis; contact via GitHub)"
}

BATCH_SIZE = 100
COORD_PRECISION = 4


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
    resp = requests.get(url, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp


def _load_cache():
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def _save_cache(cache):
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _coord_key(lat, lon):
    return f"{round(lat, COORD_PRECISION)},{round(lon, COORD_PRECISION)}"


def fetch_elevations(coord_pairs):
    """
    coord_pairs: list of (lat, lon) tuples, already deduplicated.
    Returns dict mapping coord_key -> elevation_metres.
    """
    cache = _load_cache()
    to_fetch = [(lat, lon) for lat, lon in coord_pairs if _coord_key(lat, lon) not in cache]

    print(f"  {len(coord_pairs)} unique locations, {len(to_fetch)} need fetching "
          f"({len(coord_pairs) - len(to_fetch)} already cached)")

    for i in range(0, len(to_fetch), BATCH_SIZE):
        batch = to_fetch[i:i + BATCH_SIZE]
        lats = ",".join(str(lat) for lat, _ in batch)
        lons = ",".join(str(lon) for _, lon in batch)

        print(f"  fetching batch {i // BATCH_SIZE + 1} ({len(batch)} coordinates)…")
        resp = _get("https://api.open-meteo.com/v1/elevation", params={"latitude": lats, "longitude": lons})
        elevations = resp.json()["elevation"]

        for (lat, lon), elevation in zip(batch, elevations):
            cache[_coord_key(lat, lon)] = elevation

        _save_cache(cache)  # incremental save, same reasoning as the geocoder

    return {_coord_key(lat, lon): cache[_coord_key(lat, lon)] for lat, lon in coord_pairs}


def main():
    in_path = PROCESSED_DIR / "incidents_geocoded.csv"
    if not in_path.exists():
        print("no geocoded incidents found — run geocoding first")
        return

    df = pd.read_csv(in_path)
    geocoded = df[df["lat"].notna() & df["lon"].notna()]

    coord_pairs = list({(row.lat, row.lon) for row in geocoded.itertuples()})
    elevations = fetch_elevations(coord_pairs)

    df["elevation_m"] = df.apply(
        lambda r: elevations.get(_coord_key(r["lat"], r["lon"])) if pd.notna(r["lat"]) else None,
        axis=1,
    )

    matched = df["elevation_m"].notna().sum()
    print(f"  elevation added for {matched}/{len(df)} incidents")

    out_path = PROCESSED_DIR / "incidents_geocoded.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()