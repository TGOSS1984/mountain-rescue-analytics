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
    month: str  # YYYY-MM
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