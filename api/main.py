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
from models import Incident, IncidentList, OverallStats, RegionSummary, MonthlySummary

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


@app.get("/regions", response_model=list[RegionSummary])
def list_regions():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT source_team_id, "
            "       COUNT(*) as incident_count, "
            "       SUM(CASE WHEN geocode_status = 'matched' THEN 1 ELSE 0 END) as geocoded_count "
            "FROM incidents GROUP BY source_team_id"
        ).fetchall()
    finally:
        conn.close()

    return [
        RegionSummary(
            source_team_id=r["source_team_id"],
            region=TEAM_REGION.get(r["source_team_id"], "Unknown"),
            incident_count=r["incident_count"],
            geocoded_count=r["geocoded_count"],
        )
        for r in rows
    ]


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

        region_rows = conn.execute(
            "SELECT source_team_id, "
            "       COUNT(*) as incident_count, "
            "       SUM(CASE WHEN geocode_status = 'matched' THEN 1 ELSE 0 END) as geocoded_count "
            "FROM incidents GROUP BY source_team_id"
        ).fetchall()
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
        regions=[
            RegionSummary(
                source_team_id=r["source_team_id"],
                region=TEAM_REGION.get(r["source_team_id"], "Unknown"),
                incident_count=r["incident_count"],
                geocoded_count=r["geocoded_count"],
            )
            for r in region_rows
        ],
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