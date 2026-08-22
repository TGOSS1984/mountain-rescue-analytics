"""
clean_incidents.py

Takes the raw scraped incidents (one messy blob of title + body text per
incident) and turns them into a consistent, structured record per row.

This is where most of the actual "data cleaning" work lives, and it's
worth being upfront about what's inference vs. what's stated directly:

  - incident_number, date, and time are parsed out of free text with
    regex, because the source doesn't provide them as separate fields.
    Where parsing fails, the field is left null rather than guessed.
  - `activity_type` and `outcome` are inferred from keywords in the
    narrative (a rule-based classifier, not a source-provided field).
    This is a judgement call, and it's flagged as such in the data
    dictionary — a "walker" mentioned in passing isn't necessarily the
    casualty's activity, so this classifier will get things wrong on
    ambiguous text. It's a reasonable first pass, not ground truth.
  - `location_text` is the incident title as published — it still needs
    geocoding (see pipeline/geocode/) before it's a coordinate.
"""

import json
import re
from pathlib import Path

import pandas as pd
from dateutil import parser as dateparser

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
INTERIM_DIR = Path(__file__).resolve().parents[1] / "data" / "interim"

# Ordered so more specific categories are checked before generic ones.
ACTIVITY_KEYWORDS = [
    ("climbing", ["climber", "climbing", "crag", "abseil", "boulderer", "bouldering"]),
    ("cycling", ["cyclist", "mountain biker", "cycling", "bike"]),
    ("running", ["runner", "running", "fell race"]),
    ("water", ["swimmer", "water rescue", "river", "reservoir", "swiftwater"]),
    ("search_missing_person", ["missing person", "overdue", "search for", "reported missing"]),
    ("walking", ["walker", "walking", "hiker", "hillwalker", "rambler"]),
]

OUTCOME_KEYWORDS = [
    ("fatality", ["sadly died", "confirmed deceased", "fatality", "pronounced dead"]),
    ("air_ambulance", ["air ambulance", "helicopter"]),
    ("hospital_transfer", ["hospital", "ambulance service", "handed over to"]),
    ("self_rescued", ["self rescued", "self-rescued", "made their own way", "stood down before"]),
    ("stood_down", ["stood down", "no further action", "cancelled"]),
]

INCIDENT_NUM_RE = re.compile(r"Incident\s+(\d+)", re.IGNORECASE)
DOG_CALLOUT_RE = re.compile(r"Dog\s+Callout\s+(\d+)", re.IGNORECASE)
DATE_RE = re.compile(
    r"(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})", re.IGNORECASE
)
# Two shapes appear across sources: "1748hrs" (military, no separator,
# always followed by hrs/hours) and "13:37" / "13:37hrs" (colon
# separator, suffix optional). Both require an explicit marker so a
# bare 4-digit year like "2026" is never mistaken for a time — an
# earlier version without that requirement matched "2026" as 20:26,
# caught by the test suite (see pipeline/tests/).
TIME_RE_MILITARY = re.compile(r"\b([01]\d|2[0-3])([0-5]\d)\s*(?:hrs|hours)\b", re.IGNORECASE)
TIME_RE_COLON = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\s*(?:hrs|hours)?\b", re.IGNORECASE)


DATE_DDMMYYYY_RE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def parse_ddmmyyyy(date_str):
    """OVMRO's dates come pre-formatted as DD/MM/YYYY rather than needing
    extraction from free text — this just normalises to ISO, no regex
    hunting required."""
    m = DATE_DDMMYYYY_RE.match((date_str or "").strip())
    if not m:
        return None
    day, month, year = m.groups()
    return f"{year}-{month}-{day}"


def duration_to_minutes(duration_str):
    """Converts OVMRO's 'HH:MM' operation duration into total minutes.
    Note this is elapsed time, not a clock time — '12:00' means the
    operation ran 12 hours, not that it happened at noon."""
    m = re.match(r"^(\d{2}):(\d{2})$", (duration_str or "").strip())
    if not m:
        return None
    hours, minutes = m.groups()
    return int(hours) * 60 + int(minutes)


def _first_match(pattern, text):
    m = pattern.search(text or "")
    return m.group(1) if m else None


def parse_incident_number(text):
    num = _first_match(INCIDENT_NUM_RE, text)
    if num:
        return f"incident_{num}"
    dog_num = _first_match(DOG_CALLOUT_RE, text)
    if dog_num:
        return f"dog_callout_{dog_num}"
    return None


def parse_date(text):
    raw = _first_match(DATE_RE, text)
    if not raw:
        return None
    try:
        return dateparser.parse(raw, dayfirst=True).date().isoformat()
    except (ValueError, OverflowError):
        return None


def parse_time(text):
    # Only look in the first ~150 chars — the opening line is where the
    # timestamp lives; later digits in the narrative (e.g. "70m down")
    # are not times and would give false matches if we scanned the whole text.
    header = (text or "")[:150]
    m = TIME_RE_MILITARY.search(header) or TIME_RE_COLON.search(header)
    if not m:
        return None
    hour, minute = m.groups()
    return f"{int(hour):02d}:{minute}"


def classify(text, keyword_map, default="unspecified"):
    text_lower = (text or "").lower()
    for label, keywords in keyword_map:
        if any(kw in text_lower for kw in keywords):
            return label
    return default


def clean_team_file(raw_path):
    raw_incidents = json.loads(raw_path.read_text())
    rows = []

    for item in raw_incidents:
        full_text = item.get("content_text") or item.get("content_html") or ""
        title = item.get("title_raw", "").strip()
        stated_callout_type = item.get("callout_type_stated")
        is_ovmro = item["source_team_id"] == "ovmro"

        row = {
            "source_team_id": item["source_team_id"],
            "source_method": item["source_method"],
            "incident_id": parse_incident_number(full_text) or parse_incident_number(title),
            "location_text": item.get("title_raw") if not stated_callout_type and not is_ovmro else (
                item.get("location_text_stated") if is_ovmro else _wasdale_location(title)
            ),
            # OVMRO gives a clean pre-parsed date directly; other sources
            # need it extracted from free text.
            "date": parse_ddmmyyyy(item.get("date_raw_ddmmyyyy")) if is_ovmro else parse_date(full_text),
            # OVMRO's source data is an elapsed *duration*, not a clock-in
            # time, so there's no meaningful "time" value to set here —
            # left null rather than misusing duration as a timestamp.
            "time": None if is_ovmro else parse_time(full_text),
            "activity_type": classify(full_text, ACTIVITY_KEYWORDS),
            "outcome": stated_callout_type if stated_callout_type else classify(full_text, OUTCOME_KEYWORDS, default="unrecorded"),
            "outcome_source": "stated_by_team" if stated_callout_type else "inferred_from_keywords",
            "narrative_raw": full_text.strip(),
            "source_url": item.get("link"),
            # OVMRO-specific fields — null for every other source, which
            # is honest: Edale and Wasdale simply don't publish this.
            "duration_minutes": duration_to_minutes(item.get("duration_raw")) if is_ovmro else None,
            "casualties_count": (
                int(item["casualties_count"]) if is_ovmro and item.get("casualties_count") else None
            ),
            "team_members_attended": (
                int(item["team_members_attended"]) if is_ovmro and item.get("team_members_attended") else None
            ),
        }
        rows.append(row)

    return pd.DataFrame(rows)


def _wasdale_location(title_raw):
    """Wasdale titles are 'N. Location' — strip the leading number+dot."""
    return re.sub(r"^\d+\.\s*", "", title_raw or "").strip()


def main():
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    frames = []

    for raw_path in RAW_DIR.glob("*_incidents_raw.json"):
        print(f"cleaning {raw_path.name}…")
        df = clean_team_file(raw_path)
        frames.append(df)

    if not frames:
        print("no raw files found — run the ingest step first")
        return

    combined = pd.concat(frames, ignore_index=True)

    # A record with no incident_id, no date, AND no location isn't usable —
    # drop those, but keep a log of how many so it's visible, not silent.
    before = len(combined)
    combined = combined.dropna(subset=["date", "location_text"], how="all")
    dropped = before - len(combined)
    if dropped:
        print(f"dropped {dropped} rows with neither a date nor a location")

    combined = combined.drop_duplicates(subset=["source_team_id", "incident_id", "date"])

    out_path = INTERIM_DIR / "incidents_cleaned.csv"
    combined.to_csv(out_path, index=False)
    print(f"wrote {len(combined)} cleaned rows to {out_path}")


if __name__ == "__main__":
    main()