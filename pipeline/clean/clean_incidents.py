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
import html

import pandas as pd
from dateutil import parser as dateparser

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
INTERIM_DIR = Path(__file__).resolve().parents[1] / "data" / "interim"

# Ordered so more specific categories are checked before generic ones.
ACTIVITY_KEYWORDS = [
    (
        "animal_rescue",
        # UWFRA is the first source in this project to regularly respond
        # to animal welfare callouts, not just human incidents — real
        # examples: "Sheep stuck in a bog", "Stranded sheep", "Dog
        # rescue North York Moors". Checked early since these titles
        # rarely contain any other activity keyword to conflict with.
        ["sheep", "dog rescue", "livestock", "animal welfare", "trapped animal"],
    ),
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


UWFRA_DURATION_RE = re.compile(r"(\d+)hr\s+(\d+)min")


def uwfra_duration_to_minutes(duration_str):
    """UWFRA gives duration as 'Xhr Ymin' — a different shape from
    OVMRO's 'HH:MM', so this is a separate parser rather than trying to
    force one regex to cover both. Used for both the Duration and Total
    attendance fields, which share this same format in the source."""
    m = UWFRA_DURATION_RE.search(duration_str or "")
    if not m:
        return None
    hours, minutes = m.groups()
    return int(hours) * 60 + int(minutes)


DATE_DDMONYYYY_RE = re.compile(r"^(\d{1,2})\s+(\w{3})\s+(\d{4})$")
_MONTH_ABBREV = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def parse_uwfra_date(date_str):
    """UWFRA's archive already gives a clean 'DD Mon YYYY' string per
    incident (e.g. '16 Aug 2026') — no need to hunt it out of free text
    the way parse_date() does for Edale/UWFRA's narratives; just
    normalise the format directly."""
    m = DATE_DDMONYYYY_RE.match((date_str or "").strip())
    if not m:
        return None
    day, month_abbrev, year = m.groups()
    month = _MONTH_ABBREV.get(month_abbrev.lower())
    if not month:
        return None
    return f"{year}-{month}-{int(day):02d}"


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


# Sane bounds for a date this project could plausibly ever see — real
# incidents span roughly the last decade to the present. Anything
# outside this is almost certainly a mis-parsed accidental match deep
# in a narrative (e.g. "since 1956" combined with an unrelated nearby
# month name), not a real incident date, and gets rejected the same way
# an unparseable string would be: left null, not trusted.
MIN_PLAUSIBLE_YEAR = 2010
MAX_PLAUSIBLE_YEAR = 2035


def parse_date(text):
    # Only search the opening of the text, not the whole narrative —
    # the real date always appears in the first line or two ("Incident
    # 95 – Tuesday 18th August 2026..."). Scanning the full narrative
    # risked matching an unrelated date-shaped phrase buried in the
    # story (confirmed on a real pipeline run: min/max dates came back
    # as year 0820 and year 2109, neither of which is a real incident —
    # something later in one or two narratives coincidentally matched
    # the "day month year" pattern). Mirrors the same header-only
    # restriction parse_time() already uses, for the same reason.
    header = (text or "")[:200]
    raw = _first_match(DATE_RE, header)
    if not raw:
        return None
    try:
        parsed = dateparser.parse(raw, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None

    # Second line of defence: even a match within the header window
    # should still fail a basic plausibility check rather than be
    # trusted blindly — belt and braces, since a wrong date silently
    # poisoning a weather join or a trend chart is a worse outcome than
    # an occasional row left with no date at all.
    if not (MIN_PLAUSIBLE_YEAR <= parsed.year <= MAX_PLAUSIBLE_YEAR):
        return None

    return parsed.isoformat()


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
    raw_incidents = json.loads(raw_path.read_text(encoding="utf-8"))
    rows = []

    for item in raw_incidents:
        full_text = item.get("content_text") or item.get("content_html") or ""
        # NOT item.get("title_raw", "").strip() — .get()'s default only
        # applies when the key is *missing*, not when it's present but
        # explicitly None, which is exactly what happened for some real
        # UWFRA entries where the title-extraction regex in
        # scrape_uwfra.py failed to find a match (confirmed against a
        # real pipeline run: AttributeError on 'NoneType'.strip()).
        # Matches full_text's existing or-chain pattern above for the
        # same reason.
        title = (item.get("title_raw") or "").strip()

        # WordPress's REST API returns title/content with raw HTML
        # entities un-decoded (e.g. "Lady Canning&#8217;s" instead of
        # "Lady Canning's") — the HTML-scrape fallback path already got
        # this for free via BeautifulSoup's get_text(), but REST-sourced
        # rows (i.e. most of Edale) never did. Found by spotting it in
        # real output: several location names were silently hurting
        # their own geocoding match rate by querying Nominatim for
        # "Gardom&#8217;s edge" instead of "Gardom's edge". Unescaping
        # once here, at the source, rather than patching it downstream.
        full_text = html.unescape(full_text)
        title = html.unescape(title)
        stated_callout_type = item.get("callout_type_stated")
        is_ovmro = item["source_team_id"] == "ovmro"
        is_uwfra = item["source_team_id"] == "uwfra"

        row = {
            "source_team_id": item["source_team_id"],
            "source_method": item["source_method"],
            "incident_id": (
                f"uwfra_{item['incident_ref']}" if is_uwfra and item.get("incident_ref")
                else parse_incident_number(full_text) or parse_incident_number(title)
            ),
            "location_text": title if not stated_callout_type and not is_ovmro else (
                item.get("location_text_stated") if is_ovmro else _wasdale_location(title)
            ),
            # OVMRO and UWFRA both give a clean pre-parsed date directly;
            # Edale/Wasdale need it extracted from free text.
            "date": (
                parse_ddmmyyyy(item.get("date_raw_ddmmyyyy")) if is_ovmro
                else parse_uwfra_date(item.get("date_raw_ddmonyyyy")) if is_uwfra
                else parse_date(full_text)
            ),
            # OVMRO's source data is an elapsed *duration*, not a clock-in
            # time, so there's no meaningful "time" value to set here —
            # left null rather than misusing duration as a timestamp.
            # UWFRA likewise only gives a date, no time of day.
            "time": None if (is_ovmro or is_uwfra) else parse_time(full_text),
            "activity_type": classify(full_text, ACTIVITY_KEYWORDS),
            "outcome": stated_callout_type if stated_callout_type else classify(full_text, OUTCOME_KEYWORDS, default="unrecorded"),
            "outcome_source": "stated_by_team" if stated_callout_type else "inferred_from_keywords",
            "narrative_raw": full_text.strip(),
            "source_url": item.get("link"),
            # duration_minutes and team_members_attended were originally
            # OVMRO-exclusive fields; UWFRA also publishes both (its own
            # "Duration" and "Attendees" fields), so both sources now
            # populate these — still null for Edale/Wasdale, which
            # simply don't publish this.
            "duration_minutes": (
                duration_to_minutes(item.get("duration_raw")) if is_ovmro
                else uwfra_duration_to_minutes(item.get("duration_raw")) if is_uwfra
                else None
            ),
            "casualties_count": (
                int(item["casualties_count"]) if is_ovmro and item.get("casualties_count") else None
            ),
            "team_members_attended": (
                int(item["team_members_attended"]) if is_ovmro and item.get("team_members_attended")
                else int(item["attendees_count"]) if is_uwfra and item.get("attendees_count")
                else None
            ),
            # Genuinely unique to UWFRA — aggregate volunteer person-hours
            # for the whole operation (not just headcount x duration;
            # accounts for shift changes/rotating personnel, so it's kept
            # as its own stated field rather than computed).
            "total_attendance_minutes": (
                uwfra_duration_to_minutes(item.get("total_attendance_raw")) if is_uwfra else None
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
    combined.to_csv(out_path, index=False, encoding="utf-8")
    print(f"wrote {len(combined)} cleaned rows to {out_path}")


if __name__ == "__main__":
    main()