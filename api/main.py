"""
main.py

FastAPI service serving the cleaned, geocoded incident data from
pipeline/data/processed/incidents.db.

Run locally: uvicorn main:app --reload
Docs (auto-generated): http://localhost:8000/docs
"""

from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from database import get_connection
from models import (
    Incident, IncidentList, OverallStats, RegionSummary, MonthlySummary,
    WeatherStats, WeatherBreakdown,
)

app = FastAPI(
    title="Mountain Rescue Incident Analytics API",
    description="Real UK mountain rescue callout data — Peak District, Lake District, and Snowdonia.",
    version="0.1.0",
)

# Wide open for local frontend dev (Vite's default port and others).
# Tighten this to a specific origin before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Kept in sync with pipeline/geocode/geocode_locations.py's TEAM_REGION —
# duplicated rather than imported because the API and pipeline are
# separate deployable units that shouldn't reach into each other's
# internals, but this small mapping genuinely needs to match. If a
# fourth team is added to the pipeline, it needs adding here too.
TEAM_REGION = {
    "edale": "Peak District",
    "buxton": "Peak District",
    "wasdale": "Lake District",
    "ovmro": "Snowdonia (Eryri)",
}


def _row_to_incident(row) -> Incident:
    return Incident(**{k: row[k] for k in row.keys() if k != "id"})


@app.get("/")
def root():
    return {
        "service": "Mountain Rescue Incident Analytics API",
        "docs": "/docs",
        "endpoints": ["/incidents", "/incidents/{id}", "/regions", "/stats", "/stats/monthly"],
    }


@app.get("/incidents", response_model=IncidentList)
def list_incidents(
    team: Optional[str] = Query(None, description="Filter by source team id, e.g. 'edale'"),
    activity_type: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD, inclusive"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD, inclusive"),
    geocoded_only: bool = Query(False, description="Only return rows with matched coordinates"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conditions = []
    params: list = []

    if team:
        conditions.append("source_team_id = ?")
        params.append(team)
    if activity_type:
        conditions.append("activity_type = ?")
        params.append(activity_type)
    if outcome:
        conditions.append("outcome = ?")
        params.append(outcome)
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)
    if geocoded_only:
        conditions.append("geocode_status = 'matched'")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    conn = get_connection()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) as count FROM incidents {where_clause}", params
        ).fetchone()["count"]

        rows = conn.execute(
            f"SELECT rowid as id, * FROM incidents {where_clause} "
            f"ORDER BY date DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    finally:
        conn.close()

    return IncidentList(
        total=total,
        limit=limit,
        offset=offset,
        incidents=[_row_to_incident(r) for r in rows],
    )


@app.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT rowid as id, * FROM incidents WHERE rowid = ?", (incident_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail=f"No incident with id {incident_id}")
    return _row_to_incident(row)


def _get_region_summaries(conn) -> list[RegionSummary]:
    """
    Shared by both /regions and /stats so the two endpoints can't
    silently drift apart on how a region summary is computed.
    """
    rows = conn.execute(
        "SELECT source_team_id, "
        "       COUNT(*) as incident_count, "
        "       SUM(CASE WHEN geocode_status = 'matched' THEN 1 ELSE 0 END) as geocoded_count "
        "FROM incidents GROUP BY source_team_id"
    ).fetchall()

    top_activity_rows = conn.execute(
        "SELECT source_team_id, activity_type, COUNT(*) as n FROM incidents "
        "GROUP BY source_team_id, activity_type"
    ).fetchall()

    outcome_source_rows = conn.execute(
        "SELECT source_team_id, outcome_source, COUNT(*) as n FROM incidents "
        "GROUP BY source_team_id, outcome_source"
    ).fetchall()

    top_activity = {}
    activity_counts = {}
    for r in top_activity_rows:
        team = r["source_team_id"]
        if team not in activity_counts or r["n"] > activity_counts[team]:
            activity_counts[team] = r["n"]
            top_activity[team] = r["activity_type"]

    outcome_sources_by_team = {}
    for r in outcome_source_rows:
        outcome_sources_by_team.setdefault(r["source_team_id"], set()).add(r["outcome_source"])

    def _outcome_data_source(team):
        sources = outcome_sources_by_team.get(team, set())
        if sources == {"stated_by_team"}:
            return "stated_by_team"
        if sources == {"inferred_from_keywords"}:
            return "inferred_from_keywords"
        return "mixed"

    return [
        RegionSummary(
            source_team_id=r["source_team_id"],
            region=TEAM_REGION.get(r["source_team_id"], "Unknown"),
            incident_count=r["incident_count"],
            geocoded_count=r["geocoded_count"],
            geocode_match_rate=round(r["geocoded_count"] / r["incident_count"], 3) if r["incident_count"] else 0.0,
            top_activity_type=top_activity.get(r["source_team_id"]),
            outcome_data_source=_outcome_data_source(r["source_team_id"]),
        )
        for r in rows
    ]


@app.get("/regions", response_model=list[RegionSummary])
def list_regions():
    conn = get_connection()
    try:
        return _get_region_summaries(conn)
    finally:
        conn.close()


@app.get("/stats", response_model=OverallStats)
def overall_stats():
    conn = get_connection()
    try:
        totals = conn.execute(
            "SELECT COUNT(*) as total, "
            "       SUM(CASE WHEN geocode_status = 'matched' THEN 1 ELSE 0 END) as geocoded, "
            "       MIN(date) as start_date, MAX(date) as end_date "
            "FROM incidents"
        ).fetchone()

        region_rows = _get_region_summaries(conn)
    finally:
        conn.close()

    total = totals["total"] or 0
    geocoded = totals["geocoded"] or 0

    return OverallStats(
        total_incidents=total,
        geocoded_incidents=geocoded,
        geocode_match_rate=round(geocoded / total, 3) if total else 0.0,
        date_range_start=totals["start_date"],
        date_range_end=totals["end_date"],
        regions=region_rows,
    )


@app.get("/stats/monthly", response_model=list[MonthlySummary])
def monthly_stats(team: Optional[str] = Query(None)):
    conn = get_connection()
    try:
        params: list = []
        where_clause = ""
        if team:
            where_clause = "WHERE source_team_id = ? AND date IS NOT NULL"
            params.append(team)
        else:
            where_clause = "WHERE date IS NOT NULL"

        rows = conn.execute(
            f"SELECT substr(date, 1, 7) as month, COUNT(*) as incident_count "
            f"FROM incidents {where_clause} "
            f"GROUP BY month ORDER BY month",
            params,
        ).fetchall()
    finally:
        conn.close()

    return [MonthlySummary(month=r["month"], incident_count=r["incident_count"]) for r in rows]


@app.get("/stats/weather", response_model=WeatherStats)
def weather_stats(team: Optional[str] = Query(None)):
    """
    Incidents broken down by weather condition on the day, alongside
    how many distinct (region, date) days had each condition — the
    second series is what makes this an honest comparison rather than
    a misleading one. Most days are ordinary, so most incidents will
    land on ordinary-weather days no matter what; what's actually
    interesting is whether incidents are *disproportionately* common on
    bad-weather days relative to how often those days occur, which
    needs both numbers side by side to see.
    """
    conn = get_connection()
    try:
        params: list = []
        where_clause = "WHERE weather_summary IS NOT NULL"
        if team:
            where_clause += " AND source_team_id = ?"
            params.append(team)

        incident_rows = conn.execute(
            f"SELECT weather_summary, COUNT(*) as incident_count "
            f"FROM incidents {where_clause} "
            f"GROUP BY weather_summary ORDER BY incident_count DESC",
            params,
        ).fetchall()

        # Distinct (region, date) pairs per weather condition — a day
        # with 5 incidents shouldn't count as "storm" 5 times over when
        # asking "how many storm days were there".
        day_rows = conn.execute(
            f"SELECT weather_summary, COUNT(*) as incident_count FROM ("
            f"  SELECT DISTINCT source_team_id, date, weather_summary "
            f"  FROM incidents {where_clause}"
            f") GROUP BY weather_summary ORDER BY incident_count DESC",
            params,
        ).fetchall()

        totals = conn.execute(
            f"SELECT COUNT(*) as total FROM incidents "
            f"{'WHERE source_team_id = ?' if team else ''}",
            [team] if team else [],
        ).fetchone()
        with_weather = conn.execute(
            f"SELECT COUNT(*) as total FROM incidents {where_clause}", params
        ).fetchone()
    finally:
        conn.close()

    return WeatherStats(
        incidents_by_weather=[
            WeatherBreakdown(weather_summary=r["weather_summary"], incident_count=r["incident_count"])
            for r in incident_rows
        ],
        days_by_weather=[
            WeatherBreakdown(weather_summary=r["weather_summary"], incident_count=r["incident_count"])
            for r in day_rows
        ],
        incidents_with_weather_data=with_weather["total"],
        total_incidents=totals["total"],
    )