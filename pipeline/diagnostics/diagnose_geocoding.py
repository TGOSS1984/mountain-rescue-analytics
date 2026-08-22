"""
diagnose_geocoding.py

Standalone script — run this directly (not through run_pipeline.py) to
see exactly what Nominatim is actually returning, with full detail, for
a handful of well-known real places. This exists because the pipeline's
cache was masking the real signal: 1219 of 1293 rows on the last run
were replayed from a cache written during an earlier, genuinely broken
run (bad viewbox format), so "still 0 matched" doesn't tell us whether
the *current* code works — it might just be reusing old bad answers.

Run from pipeline/: python diagnostics/diagnose_geocoding.py

This does NOT touch the real cache file, and prints full exception
details rather than swallowing them, so whatever it finds is exactly
what a human would see too.
"""

import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderQueryError, GeocoderServiceError, GeocoderTimedOut

geolocator = Nominatim(user_agent="mountain-rescue-analytics-diagnostic-script", timeout=10)

TEST_CASES = [
    # (query, viewbox_or_None, bounded)
    ("Tryfan, Snowdonia, Gwynedd, UK", None, False),
    ("Tryfan, Snowdonia, Gwynedd, UK", ((53.25, -4.30), (52.85, -3.60)), False),
    ("Tryfan, Snowdonia, Gwynedd, UK", ((53.25, -4.30), (52.85, -3.60)), True),
    ("Tryfan", None, False),
    ("Aber Falls, Snowdonia, Gwynedd, UK", ((53.25, -4.30), (52.85, -3.60)), True),
    # The actual fix being tested: simplified "<place>, UK" suffix
    # combined with the bounded viewbox — this exact combination wasn't
    # covered by the cases above, so it needs its own direct check
    # rather than being assumed to work from the others.
    ("Tryfan, UK", ((53.25, -4.30), (52.85, -3.60)), True),
    ("Aber Falls, UK", ((53.25, -4.30), (52.85, -3.60)), True),
    ("Kinder Scout, UK", ((53.55, -2.05), (53.05, -1.45)), True),
    ("Scafell Pike, UK", ((54.75, -3.65), (54.30, -2.70)), True),
]

for query, viewbox, bounded in TEST_CASES:
    print(f"\n{'='*70}")
    print(f"Query: {query!r}")
    print(f"viewbox={viewbox}  bounded={bounded}")
    try:
        kwargs = {}
        if viewbox:
            kwargs["viewbox"] = viewbox
        if bounded:
            kwargs["bounded"] = bounded
        result = geolocator.geocode(query, addressdetails=True, **kwargs)
        if result:
            print(f"RESULT: {result.address}")
            print(f"  lat={result.latitude}, lon={result.longitude}")
            print(f"  raw type/class: {result.raw.get('type')}, {result.raw.get('class')}")
        else:
            print("RESULT: None (Nominatim returned zero matches for this query)")
    except (GeocoderQueryError, GeocoderServiceError, GeocoderTimedOut) as e:
        print(f"EXCEPTION: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"UNEXPECTED EXCEPTION: {type(e).__name__}: {e}")

    time.sleep(1.5)

print(f"\n{'='*70}")
print("Done. Paste this whole output back — the pattern across these 5 cases")
print("(which succeed, which return None, which error) tells us exactly")
print("where the real problem is, rather than guessing blind again.")