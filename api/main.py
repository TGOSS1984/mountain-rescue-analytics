"""
main.py

FastAPI service serving the cleaned, geocoded incident data from
pipeline/data/processed/incidents.db.

Run locally: uvicorn main:app --reload
Docs (auto-generated): http://localhost:8000/docs
"""

import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from database import get_connection
from models import (
    Incident, IncidentList, OverallStats, RegionSummary, MonthlySummary,
    YearlySummary, WeatherStats, WeatherBreakdown, TimeOfDayStats, TimeOfDayBucket,
    ActivityBreakdownRow, NotableStats, NotableRecord, TopLocation,
    ElevationStats, ElevationBand, RegionElevation, DaylightStats,
    DayOfWeekCount, DayOfWeekStats, BankHolidayComparison,
)

app = FastAPI(
    title="Mountain Rescue Incident Analytics API",
    description="Real UK mountain rescue callout data — Peak District, Lake District, and Snowdonia.",
    version="0.1.0",
)

# Comma-separated list of allowed origins, set via an ALLOWED_ORIGINS
# environment variable in production (the real deployed frontend URL,
# e.g. https://mountain-rescue-analytics.vercel.app) — never falls back
# to "*" once that variable is set. Defaults to Vite's local dev origin
# so nothing needs configuring just to run this locally.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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


@app.get("/stats/yearly", response_model=list[YearlySummary])
def yearly_stats(team: Optional[str] = Query(None)):
    """
    Multi-year trend. Genuinely different data than /stats/monthly's
    seasonal pattern — Edale's REST API returned its full posting
    history, not just this year, so this can show real year-over-year
    change for that team. Wasdale and OVMRO's scrapers only pulled
    their current reporting page, so their data is effectively
    single-year — teams_reporting on each row is what lets the frontend
    show that honestly rather than implying a real trend where the real
    story is "another team started reporting."
    """
    conn = get_connection()
    try:
        params: list = []
        where_clause = "WHERE date IS NOT NULL"
        if team:
            where_clause += " AND source_team_id = ?"
            params.append(team)

        rows = conn.execute(
            f"SELECT substr(date, 1, 4) as year, source_team_id, COUNT(*) as n "
            f"FROM incidents {where_clause} "
            f"GROUP BY year, source_team_id ORDER BY year",
            params,
        ).fetchall()
    finally:
        conn.close()

    by_year: dict = {}
    for r in rows:
        entry = by_year.setdefault(r["year"], {"count": 0, "teams": set()})
        entry["count"] += r["n"]
        entry["teams"].add(r["source_team_id"])

    return [
        YearlySummary(year=year, incident_count=data["count"], teams_reporting=sorted(data["teams"]))
        for year, data in sorted(by_year.items())
    ]


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


@app.get("/stats/timeofday", response_model=TimeOfDayStats)
def time_of_day_stats(team: Optional[str] = Query(None)):
    """
    Distribution of incident start times across the day. OVMRO never
    has a `time` value (its source only gives an operation duration,
    not a start time), so this endpoint structurally excludes
    Snowdonia — teams_with_time_data makes that explicit rather than
    letting a chart imply all three regions are represented the way
    they are everywhere else in the API.
    """
    conn = get_connection()
    try:
        params: list = []
        where_clause = "WHERE time IS NOT NULL"
        if team:
            where_clause += " AND source_team_id = ?"
            params.append(team)

        rows = conn.execute(
            f"SELECT CAST(substr(time, 1, 2) AS INTEGER) as hour, COUNT(*) as n "
            f"FROM incidents {where_clause} "
            f"GROUP BY hour ORDER BY hour",
            params,
        ).fetchall()

        teams_rows = conn.execute(
            f"SELECT DISTINCT source_team_id FROM incidents {where_clause}", params
        ).fetchall()

        totals = conn.execute(
            f"SELECT COUNT(*) as total FROM incidents "
            f"{'WHERE source_team_id = ?' if team else ''}",
            [team] if team else [],
        ).fetchone()
        with_time = conn.execute(
            f"SELECT COUNT(*) as total FROM incidents {where_clause}", params
        ).fetchone()
    finally:
        conn.close()

    # Fill every hour 0-23 explicitly, including zero-count ones, so the
    # frontend gets a complete 24-point series rather than having to
    # guess which hours are "genuinely zero" vs "missing from the response."
    counts_by_hour = {r["hour"]: r["n"] for r in rows}
    buckets = [
        TimeOfDayBucket(hour=h, incident_count=counts_by_hour.get(h, 0))
        for h in range(24)
    ]

    return TimeOfDayStats(
        buckets=buckets,
        incidents_with_time_data=with_time["total"],
        total_incidents=totals["total"],
        teams_with_time_data=sorted(r["source_team_id"] for r in teams_rows),
    )


@app.get("/stats/activity-breakdown", response_model=list[ActivityBreakdownRow])
def activity_breakdown():
    """
    Full activity-type distribution per region — not just the single
    "most common" figure /regions gives. This is what actually shows
    "Snowdonia skews climbing, the other two skew walking" as a
    proportion, not just a headline label. Deliberately not
    team-filterable: comparing one region's activity mix against itself
    doesn't mean anything, the whole point is the cross-region shape.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT source_team_id, activity_type, COUNT(*) as n "
            "FROM incidents GROUP BY source_team_id, activity_type "
            "ORDER BY source_team_id, n DESC"
        ).fetchall()
    finally:
        conn.close()

    return [
        ActivityBreakdownRow(
            source_team_id=r["source_team_id"],
            region=TEAM_REGION.get(r["source_team_id"], "Unknown"),
            activity_type=r["activity_type"],
            incident_count=r["n"],
        )
        for r in rows
    ]


@app.get("/stats/notable", response_model=NotableStats)
def notable_stats():
    """
    Uses OVMRO's duration/team-size fields, currently unused by any
    other chart. Deliberately excludes anything built from
    casualties_count — see NotableStats docstring for why.
    """
    conn = get_connection()
    try:
        longest = conn.execute(
            "SELECT location_text, date, duration_minutes, source_url FROM incidents "
            "WHERE source_team_id = 'ovmro' AND duration_minutes IS NOT NULL "
            "ORDER BY duration_minutes DESC LIMIT 1"
        ).fetchone()

        largest = conn.execute(
            "SELECT location_text, date, team_members_attended, source_url FROM incidents "
            "WHERE source_team_id = 'ovmro' AND team_members_attended IS NOT NULL "
            "ORDER BY team_members_attended DESC LIMIT 1"
        ).fetchone()

        aggregates = conn.execute(
            "SELECT SUM(duration_minutes) as total_minutes, "
            "       AVG(team_members_attended) as avg_team, "
            "       COUNT(*) as n "
            "FROM incidents WHERE source_team_id = 'ovmro' AND duration_minutes IS NOT NULL"
        ).fetchone()
    finally:
        conn.close()

    return NotableStats(
        longest_operation=NotableRecord(
            location_text=longest["location_text"], date=longest["date"],
            value=longest["duration_minutes"], source_url=longest["source_url"],
        ) if longest else None,
        largest_deployment=NotableRecord(
            location_text=largest["location_text"], date=largest["date"],
            value=largest["team_members_attended"], source_url=largest["source_url"],
        ) if largest else None,
        total_operation_hours=round((aggregates["total_minutes"] or 0) / 60, 1),
        average_team_size=round(aggregates["avg_team"], 1) if aggregates["avg_team"] else None,
        based_on_team="ovmro",
        based_on_incident_count=aggregates["n"] or 0,
    )


@app.get("/stats/top-locations", response_model=list[TopLocation])
def top_locations(limit: int = Query(10, ge=1, le=50), team: Optional[str] = Query(None)):
    """
    Simple raw-frequency leaderboard — see TopLocation's docstring for
    why near-duplicate place names ("Kinder" vs "Kinder Scout") aren't
    collapsed together here.
    """
    conn = get_connection()
    try:
        params: list = []
        where_clause = "WHERE location_text IS NOT NULL AND location_text != ''"
        if team:
            where_clause += " AND source_team_id = ?"
            params.append(team)

        rows = conn.execute(
            f"SELECT location_text, source_team_id, COUNT(*) as n FROM incidents "
            f"{where_clause} GROUP BY location_text, source_team_id "
            f"ORDER BY n DESC LIMIT ?",
            params + [limit],
        ).fetchall()
    finally:
        conn.close()

    return [
        TopLocation(
            location_text=r["location_text"],
            region=TEAM_REGION.get(r["source_team_id"], "Unknown"),
            source_team_id=r["source_team_id"],
            incident_count=r["n"],
        )
        for r in rows
    ]


ELEVATION_BANDS = [
    (0, "0-200m"), (200, "200-400m"), (400, "400-600m"),
    (600, "600-800m"), (800, "800-1000m"), (1000, "1000m+"),
]


def _band_for(elevation):
    """Returns (band_min_m, band_label) for the highest band whose
    threshold the elevation meets or exceeds."""
    result_min, result_label = ELEVATION_BANDS[0]
    for band_min, label in ELEVATION_BANDS:
        if elevation >= band_min:
            result_min, result_label = band_min, label
    return result_min, result_label


@app.get("/stats/elevation", response_model=ElevationStats)
def elevation_stats():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT elevation_m FROM incidents WHERE elevation_m IS NOT NULL"
        ).fetchall()

        region_rows = conn.execute(
            "SELECT source_team_id, AVG(elevation_m) as avg_elev, "
            "       SUM(CASE WHEN elevation_m IS NOT NULL THEN 1 ELSE 0 END) as n "
            "FROM incidents GROUP BY source_team_id"
        ).fetchall()

        totals = conn.execute("SELECT COUNT(*) as total FROM incidents").fetchone()
    finally:
        conn.close()

    band_counts = {label: 0 for _, label in ELEVATION_BANDS}
    for r in rows:
        _, label = _band_for(r["elevation_m"])
        band_counts[label] += 1

    bands = [
        ElevationBand(band_label=label, band_min_m=band_min, incident_count=band_counts[label])
        for band_min, label in ELEVATION_BANDS
    ]

    by_region = [
        RegionElevation(
            source_team_id=r["source_team_id"],
            region=TEAM_REGION.get(r["source_team_id"], "Unknown"),
            average_elevation_m=round(r["avg_elev"], 1) if r["avg_elev"] is not None else None,
            incident_count=r["n"],
        )
        for r in region_rows
    ]

    return ElevationStats(
        bands=bands,
        by_region=by_region,
        incidents_with_elevation=len(rows),
        total_incidents=totals["total"],
    )


@app.get("/stats/daylight", response_model=DaylightStats)
def daylight_stats():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT daylight_status, COUNT(*) as n FROM incidents "
            "WHERE daylight_status IS NOT NULL GROUP BY daylight_status"
        ).fetchall()

        teams_rows = conn.execute(
            "SELECT DISTINCT source_team_id FROM incidents WHERE daylight_status IS NOT NULL"
        ).fetchall()

        totals = conn.execute("SELECT COUNT(*) as total FROM incidents").fetchone()
        with_data = conn.execute(
            "SELECT COUNT(*) as total FROM incidents WHERE daylight_status IS NOT NULL"
        ).fetchone()
    finally:
        conn.close()

    counts = {r["daylight_status"]: r["n"] for r in rows}

    return DaylightStats(
        daylight_count=counts.get("daylight", 0),
        darkness_count=counts.get("darkness", 0),
        incidents_with_daylight_data=with_data["total"],
        total_incidents=totals["total"],
        teams_included=sorted(r["source_team_id"] for r in teams_rows),
    )


DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@app.get("/stats/day-of-week", response_model=DayOfWeekStats)
def day_of_week_stats():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT day_of_week, COUNT(*) as n FROM incidents "
            "WHERE day_of_week IS NOT NULL GROUP BY day_of_week"
        ).fetchall()

        weekend_totals = conn.execute(
            "SELECT is_weekend, COUNT(*) as n FROM incidents "
            "WHERE is_weekend IS NOT NULL GROUP BY is_weekend"
        ).fetchall()

        totals = conn.execute("SELECT COUNT(*) as total FROM incidents").fetchone()
        with_data = conn.execute(
            "SELECT COUNT(*) as total FROM incidents WHERE day_of_week IS NOT NULL"
        ).fetchone()
    finally:
        conn.close()

    counts = {r["day_of_week"]: r["n"] for r in rows}
    by_day = [DayOfWeekCount(day_of_week=d, incident_count=counts.get(d, 0)) for d in DAY_ORDER]

    weekend_map = {bool(r["is_weekend"]): r["n"] for r in weekend_totals}

    return DayOfWeekStats(
        by_day=by_day,
        weekday_count=weekend_map.get(False, 0),
        weekend_count=weekend_map.get(True, 0),
        incidents_with_data=with_data["total"],
        total_incidents=totals["total"],
    )


@app.get("/stats/bank-holidays", response_model=BankHolidayComparison)
def bank_holiday_stats():
    conn = get_connection()
    try:
        # Per-distinct-day counts, split by holiday status — mirrors the
        # weather endpoint's days_by_weather pattern, for the same reason:
        # a raw incident-count comparison would be meaningless given the
        # huge imbalance between ~8 bank holidays and ~357 ordinary days
        # a year.
        daily_counts = conn.execute(
            "SELECT date, is_bank_holiday, COUNT(*) as n FROM incidents "
            "WHERE is_bank_holiday IS NOT NULL AND date IS NOT NULL "
            "GROUP BY date, is_bank_holiday"
        ).fetchall()

        totals = conn.execute("SELECT COUNT(*) as total FROM incidents").fetchone()
        with_data = conn.execute(
            "SELECT COUNT(*) as total FROM incidents WHERE is_bank_holiday IS NOT NULL"
        ).fetchone()
    finally:
        conn.close()

    holiday_day_counts = [r["n"] for r in daily_counts if r["is_bank_holiday"]]
    ordinary_day_counts = [r["n"] for r in daily_counts if not r["is_bank_holiday"]]

    avg_holiday = sum(holiday_day_counts) / len(holiday_day_counts) if holiday_day_counts else 0.0
    avg_ordinary = sum(ordinary_day_counts) / len(ordinary_day_counts) if ordinary_day_counts else 0.0

    return BankHolidayComparison(
        avg_incidents_per_bank_holiday=round(avg_holiday, 2),
        avg_incidents_per_ordinary_day=round(avg_ordinary, 2),
        bank_holiday_days_observed=len(holiday_day_counts),
        ordinary_days_observed=len(ordinary_day_counts),
        incidents_with_known_holiday_status=with_data["total"],
        total_incidents=totals["total"],
    )