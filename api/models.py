"""
models.py

Pydantic response models. These mirror the pandera schema in
pipeline/validate/schema.py deliberately — the API's contract with the
frontend should be a direct reflection of what the pipeline actually
validated, not a reinterpretation of it. If a field changes shape in
the pipeline schema, it should have to change here too, not silently
drift apart.
"""

from typing import Optional
from pydantic import BaseModel


class Incident(BaseModel):
    source_team_id: str
    location_text: str
    date: Optional[str] = None
    time: Optional[str] = None
    activity_type: str
    outcome: str
    outcome_source: str
    narrative_raw: Optional[str] = None
    source_url: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    geocode_status: str
    geocode_confidence: Optional[str] = None
    # OVMRO-only fields — null for every other source, same as in the
    # pipeline. See docs/data-dictionary.md for why these aren't
    # zero-filled.
    duration_minutes: Optional[float] = None
    casualties_count: Optional[float] = None
    team_members_attended: Optional[float] = None
    # Regional daily weather on the incident's date — null wherever the
    # date itself is missing/unparseable, or falls outside the range
    # fetched for that region. Region-level (one weather reading shared
    # by every incident in that region on that day), not per-incident —
    # see docs/data-dictionary.md for what that trade-off means.
    temp_max_c: Optional[float] = None
    temp_min_c: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_speed_max_kmh: Optional[float] = None
    weather_summary: Optional[str] = None
    # Daylight/darkness at the incident's recorded start time — null
    # wherever weather, date, or time data is missing. Always null for
    # OVMRO specifically, since that source never records a start time
    # at all (only an operation duration). See docs/data-dictionary.md.
    daylight_status: Optional[str] = None
    # Terrain elevation in metres at the geocoded location — null for
    # any unmatched location, same reasoning as lat/lon.
    elevation_m: Optional[float] = None
    # Bank holiday status is null for dates outside the range the
    # gov.uk API actually publishes (a rolling few years), not just
    # dates without a holiday — see docs/data-dictionary.md.
    is_bank_holiday: Optional[bool] = None
    day_of_week: Optional[str] = None
    is_weekend: Optional[bool] = None


class WeatherBreakdown(BaseModel):
    weather_summary: str
    incident_count: int


class WeatherStats(BaseModel):
    """
    Summary stats for the weather-vs-incidents insight: how incident
    counts break down by weather condition, plus enough context (the
    number of *days* with each condition, not just incidents) to tell
    "storms cause more incidents" apart from "there just happen to be
    more incidents on the many ordinary cloudy days" — the second is
    the far more common real answer, and the API should make it
    possible to check that rather than inviting the wrong conclusion.
    """
    incidents_by_weather: list[WeatherBreakdown]
    days_by_weather: list[WeatherBreakdown]  # same shape, but counting distinct weather-days, not incidents
    incidents_with_weather_data: int
    total_incidents: int


class TimeOfDayBucket(BaseModel):
    hour: int  # 0-23
    incident_count: int


class TimeOfDayStats(BaseModel):
    """
    OVMRO's source data only gives an operation *duration*, never a
    start time (see pipeline/clean/clean_incidents.py) — so this isn't
    "less complete" for Snowdonia, it's structurally absent. teams_with_time_data
    makes that explicit rather than letting a viewer assume all three
    regions are represented here the way they are in every other chart.
    """
    buckets: list[TimeOfDayBucket]
    incidents_with_time_data: int
    total_incidents: int
    teams_with_time_data: list[str]


class IncidentList(BaseModel):
    total: int
    limit: int
    offset: int
    incidents: list[Incident]


class RegionSummary(BaseModel):
    source_team_id: str
    region: str
    incident_count: int
    geocoded_count: int
    geocode_match_rate: float
    top_activity_type: Optional[str] = None
    # Whether this region's `outcome` field is a real, team-stated
    # severity (currently only Wasdale) or my own keyword guess
    # (everyone else). Deliberately NOT collapsed into a single
    # "severity rate" comparable across regions — a "Full Callout %"
    # for Wasdale and an "air_ambulance %" for Edale/OVMRO aren't the
    # same measurement, and presenting them side by side as if they
    # were would misrepresent data quality that's actually uneven.
    # See docs/data-dictionary.md.
    outcome_data_source: str


class MonthlySummary(BaseModel):
    """
    A genuine seasonal aggregate — one row per calendar month (Jan
    through Dec), combining incidents from every year in the dataset.
    Always 12 rows, in calendar order, including months with zero
    incidents. This is deliberately NOT a year-by-year timeline (that's
    /stats/yearly) — an earlier version of this endpoint grouped by
    year-and-month together, which produced a genuinely confusing chart
    once Edale's decade-plus of history was included: with 80+ points
    crammed into one chart, the chart library auto-skips axis labels to
    avoid overlap, so the handful of labels actually visible weren't
    even adjacent bars — it looked randomly ordered even though the
    underlying data wasn't.
    """
    month: str  # "01" through "12"
    month_label: str  # "Jan" through "Dec", for direct display
    incident_count: int


class YearlySummary(BaseModel):
    year: str  # YYYY
    incident_count: int
    # Which teams have data for this year — matters because only Edale's
    # REST API returned genuine multi-year history; Wasdale and OVMRO's
    # scrapers only pulled their current reporting page (this year only).
    # Without this, a combined "all regions" yearly trend would show an
    # apparent surge in the current year that's actually just three
    # teams reporting instead of one — a coverage artifact, not a real
    # change in incident rates. See docs/data-dictionary.md.
    teams_reporting: list[str]


class OverallStats(BaseModel):
    total_incidents: int
    geocoded_incidents: int
    geocode_match_rate: float
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    regions: list[RegionSummary]


class ActivityBreakdownRow(BaseModel):
    """
    Tidy (long-format) rows: one per (region, activity_type) pair with
    a nonzero count. The frontend pivots this into the wide shape a
    stacked bar chart needs — kept tidy here rather than pre-pivoted,
    since that's the more normal REST shape and doesn't bake in an
    assumption about which activity types exist ahead of time.
    """
    source_team_id: str
    region: str
    activity_type: str
    incident_count: int


class NotableRecord(BaseModel):
    location_text: str
    date: Optional[str] = None
    value: float
    source_url: Optional[str] = None


class NotableStats(BaseModel):
    """
    OVMRO's incident log is the only source that records operation
    duration and team size — genuinely unused data otherwise, worth
    surfacing. Deliberately excludes anything built from
    casualties_count: turning a real operation (possibly involving
    injury or worse) into a "record" would be poor taste regardless of
    how factually accurate the number is. Longest operation and largest
    deployment are shown as plain operational facts (location, duration,
    date) with no narrative text, same as anywhere else these appear.
    """
    longest_operation: Optional[NotableRecord] = None  # value = duration_minutes
    largest_deployment: Optional[NotableRecord] = None  # value = team_members_attended
    total_operation_hours: float
    average_team_size: Optional[float] = None
    based_on_team: str
    based_on_incident_count: int


class TopLocation(BaseModel):
    """
    Raw frequency count on location_text as published — no fuzzy
    matching or normalisation attempted. "Kinder Scout", "Kinder", and
    "Kinder southern edge" are geographically close but count as three
    separate entries here, not one. That's an honest limitation worth
    knowing rather than a bug: collapsing near-duplicate place names
    reliably would need real gazetteer matching, which this project
    doesn't attempt. See docs/data-dictionary.md.
    """
    location_text: str
    region: str
    source_team_id: str
    incident_count: int


class ElevationBand(BaseModel):
    band_label: str  # e.g. "400-600m"
    band_min_m: int
    incident_count: int


class RegionElevation(BaseModel):
    source_team_id: str
    region: str
    average_elevation_m: Optional[float] = None
    incident_count: int  # count this average is based on, i.e. rows with elevation data


class ElevationStats(BaseModel):
    bands: list[ElevationBand]
    by_region: list[RegionElevation]
    incidents_with_elevation: int
    total_incidents: int


class DaylightStats(BaseModel):
    """
    Tests a specific claim Wasdale made in their own published safety
    message — a rise in incidents from walkers becoming "benighted"
    without a head torch — against the actual data, rather than just
    repeating the claim. OVMRO is structurally excluded (never records
    a start time), same as the time-of-day endpoint; teams_included
    makes that explicit.
    """
    daylight_count: int
    darkness_count: int
    incidents_with_daylight_data: int
    total_incidents: int
    teams_included: list[str]


class DayOfWeekCount(BaseModel):
    day_of_week: str
    incident_count: int


class DayOfWeekStats(BaseModel):
    by_day: list[DayOfWeekCount]  # Monday through Sunday, in order
    weekday_count: int
    weekend_count: int
    incidents_with_data: int
    total_incidents: int


class BankHolidayComparison(BaseModel):
    """
    Average incidents PER DAY for bank holidays vs. ordinary days, not
    raw totals — there are only ~8 bank holidays a year against ~357
    ordinary days, so a raw total comparison would trivially and
    meaninglessly favour ordinary days every time. This is the same
    "days vs incidents" honesty pattern already used for the weather
    endpoint. Only dates within the range the gov.uk API actually
    covers are included — see is_bank_holiday's docstring on Incident.
    """
    avg_incidents_per_bank_holiday: float
    avg_incidents_per_ordinary_day: float
    bank_holiday_days_observed: int
    ordinary_days_observed: int
    incidents_with_known_holiday_status: int
    total_incidents: int