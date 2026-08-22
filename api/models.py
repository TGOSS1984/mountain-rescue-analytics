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


class MonthlySummary(BaseModel):
    month: str  # YYYY-MM
    incident_count: int


class OverallStats(BaseModel):
    total_incidents: int
    geocoded_incidents: int
    geocode_match_rate: float
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    regions: list[RegionSummary]