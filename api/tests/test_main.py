"""
test_main.py

API test suite. Uses a temporary SQLite database built fresh for each
test run (not the real pipeline output) so tests are deterministic and
don't depend on whatever real data happens to be on disk — the pipeline
already has its own tests for whether the *data* is correct; these
tests are about whether the *API* correctly serves whatever data is
in the database.

Run with: pytest tests/
"""

import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Builds a small, known test database and points the API at it."""
    db_path = tmp_path / "test_incidents.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL
        )
    """)
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("edale", "Kinder Scout", "2026-03-01", "14:30", "walking", "unrecorded",
             "inferred_from_keywords", "A walker needed assistance.",
             "https://edalemrt.co.uk/incident/1/", 53.38, -1.87, "matched", "high",
             None, None, None),
            ("wasdale", "Scafell Pike", "2026-03-02", None, "walking", "Full Callout",
             "stated_by_team", "Team deployed.", "https://www.wmrt.org.uk/report-page/",
             54.45, -3.21, "matched", "high", None, None, None),
            ("ovmro", "Tryfan", "2026-02-15", None, "climbing", "unrecorded",
             "inferred_from_keywords", "Climber fell.",
             "https://ogwen-rescue.org.uk/incident-details/", 53.11, -3.99, "matched", "high",
             220.0, 1.0, 12.0),
            ("edale", "Dummy Incident", "2026-03-04", None, "unspecified", "unrecorded",
             "inferred_from_keywords", "Test entry.", None, None, None, "no_match", None,
             None, None, None),
        ],
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_root(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "endpoints" in resp.json()


def test_list_incidents_no_filter(client):
    resp = client.get("/incidents")
    body = resp.json()
    assert resp.status_code == 200
    assert body["total"] == 4
    assert len(body["incidents"]) == 4


def test_list_incidents_filter_by_team(client):
    resp = client.get("/incidents?team=ovmro")
    body = resp.json()
    assert body["total"] == 1
    assert body["incidents"][0]["location_text"] == "Tryfan"


def test_list_incidents_geocoded_only_excludes_no_match(client):
    resp = client.get("/incidents?geocoded_only=true")
    body = resp.json()
    assert body["total"] == 3
    assert all(i["geocode_status"] == "matched" for i in body["incidents"])


def test_list_incidents_date_range_filter(client):
    resp = client.get("/incidents?date_from=2026-03-01&date_to=2026-03-02")
    body = resp.json()
    assert body["total"] == 2


def test_ovmro_specific_fields_present(client):
    resp = client.get("/incidents?team=ovmro")
    incident = resp.json()["incidents"][0]
    assert incident["duration_minutes"] == 220.0
    assert incident["casualties_count"] == 1.0
    assert incident["team_members_attended"] == 12.0


def test_non_ovmro_fields_are_null_not_zero(client):
    """
    Regression check for a real design decision made in the pipeline:
    duration/casualties/team-size are null for sources that don't
    publish them, not zero — the API must preserve that distinction
    rather than coercing missing values to 0.
    """
    resp = client.get("/incidents?team=edale&limit=1")
    incident = resp.json()["incidents"][0]
    assert incident["duration_minutes"] is None
    assert incident["casualties_count"] is None


def test_get_single_incident_by_id(client):
    resp = client.get("/incidents/1")
    assert resp.status_code == 200
    assert resp.json()["location_text"] == "Kinder Scout"


def test_get_nonexistent_incident_returns_404(client):
    resp = client.get("/incidents/9999")
    assert resp.status_code == 404


def test_regions_summary(client):
    resp = client.get("/regions")
    body = resp.json()
    assert len(body) == 3  # edale, wasdale, ovmro
    edale = next(r for r in body if r["source_team_id"] == "edale")
    assert edale["region"] == "Peak District"
    assert edale["incident_count"] == 2
    assert edale["geocoded_count"] == 1  # Dummy Incident wasn't matched


def test_overall_stats(client):
    resp = client.get("/stats")
    body = resp.json()
    assert body["total_incidents"] == 4
    assert body["geocoded_incidents"] == 3
    assert body["geocode_match_rate"] == 0.75
    assert body["date_range_start"] == "2026-02-15"
    assert body["date_range_end"] == "2026-03-04"


def test_monthly_stats(client):
    """Updated for the calendar-month redesign: always 12 rows, and the
    fixture's 2026-02/2026-03 dates now fall into month buckets "02"
    and "03" respectively, combined across whatever years exist (here,
    just one)."""
    resp = client.get("/stats/monthly")
    body = resp.json()
    assert len(body) == 12
    counts = {m["month"]: m["incident_count"] for m in body}
    assert counts["02"] == 1
    assert counts["03"] == 3
    assert counts["01"] == 0  # present with zero, not omitted


def test_monthly_stats_filtered_by_team(client):
    resp = client.get("/stats/monthly?team=ovmro")
    body = resp.json()
    assert len(body) == 12
    counts = {m["month"]: m["incident_count"] for m in body}
    assert counts["02"] == 1
    assert counts["03"] == 0


def test_pagination_limit_and_offset(client):
    resp = client.get("/incidents?limit=2&offset=0")
    first_page = resp.json()
    resp = client.get("/incidents?limit=2&offset=2")
    second_page = resp.json()

    assert len(first_page["incidents"]) == 2
    assert len(second_page["incidents"]) == 2
    first_ids = {i["source_url"] for i in first_page["incidents"]}
    second_ids = {i["source_url"] for i in second_page["incidents"]}
    assert first_ids.isdisjoint(second_ids)


@pytest.fixture
def weather_client(tmp_path, monkeypatch):
    """Separate fixture with weather columns populated, including the
    'multiple incidents on one day' case that the days-vs-incidents
    distinction exists to handle correctly."""
    db_path = tmp_path / "test_weather.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT
        )
    """)
    rows = [
        ("edale", "A", "2026-01-01", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, 5, 0, 50, 80, "storm"),
        ("edale", "B", "2026-01-01", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, 5, 0, 50, 80, "storm"),
        ("edale", "C", "2026-01-01", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, 5, 0, 50, 80, "storm"),
        ("edale", "D", "2026-02-01", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, 8, 2, 5, 20, "cloudy"),
        ("edale", "E", "2026-02-02", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, 9, 3, 2, 15, "cloudy"),
        ("edale", "F", "2026-02-03", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
    ]
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_weather_stats_distinguishes_days_from_incidents(weather_client):
    """
    The core reason this endpoint exists: 3 incidents on a single storm
    day must not be reported as "3 storm days" — that would overstate
    how often storms actually occur relative to how many incidents
    happen during them.
    """
    resp = weather_client.get("/stats/weather")
    body = resp.json()

    incidents_storm = next(w for w in body["incidents_by_weather"] if w["weather_summary"] == "storm")
    days_storm = next(w for w in body["days_by_weather"] if w["weather_summary"] == "storm")

    assert incidents_storm["incident_count"] == 3
    assert days_storm["incident_count"] == 1


def test_weather_stats_excludes_rows_without_weather_data(weather_client):
    resp = weather_client.get("/stats/weather")
    body = resp.json()
    assert body["total_incidents"] == 6
    assert body["incidents_with_weather_data"] == 5


@pytest.fixture
def region_comparison_client(tmp_path, monkeypatch):
    """Mirrors the real data-quality split: Wasdale states outcomes
    directly, Edale and OVMRO don't — the region comparison must keep
    this distinction visible rather than blending it."""
    db_path = tmp_path / "test_regions.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT
        )
    """)
    rows = [
        ("edale", "A", "2026-01-01", None, "walking", "unrecorded", "inferred_from_keywords",
         None, None, 53.3, -1.8, "matched", None, None, None, None, None, None, None, None, None),
        ("edale", "B", "2026-01-02", None, "walking", "unrecorded", "inferred_from_keywords",
         None, None, None, None, "no_match", None, None, None, None, None, None, None, None, None),
        ("edale", "C", "2026-01-03", None, "climbing", "unrecorded", "inferred_from_keywords",
         None, None, 53.3, -1.8, "matched", None, None, None, None, None, None, None, None, None),
        ("wasdale", "D", "2026-02-01", None, "walking", "Full Callout", "stated_by_team",
         None, None, 54.4, -3.2, "matched", None, None, None, None, None, None, None, None, None),
        ("wasdale", "E", "2026-02-02", None, "walking", "Alert", "stated_by_team",
         None, None, 54.4, -3.2, "matched", None, None, None, None, None, None, None, None, None),
        ("ovmro", "F", "2026-03-01", None, "climbing", "unrecorded", "inferred_from_keywords",
         None, None, 53.1, -4.0, "matched", None, None, None, None, None, None, None, None, None),
        ("ovmro", "G", "2026-03-02", None, "climbing", "unrecorded", "inferred_from_keywords",
         None, None, 53.1, -4.0, "matched", None, None, None, None, None, None, None, None, None),
    ]
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_region_top_activity_differs_correctly(region_comparison_client):
    resp = region_comparison_client.get("/regions")
    body = {r["source_team_id"]: r for r in resp.json()}

    assert body["edale"]["top_activity_type"] == "walking"
    assert body["ovmro"]["top_activity_type"] == "climbing"


def test_region_outcome_data_source_not_blended(region_comparison_client):
    """
    The core thing this field exists to prevent: Wasdale's real,
    team-stated severity data must not be reported the same way as
    Edale/OVMRO's keyword-guessed outcomes — that would misrepresent
    uneven data quality as if it were consistent across regions.
    """
    resp = region_comparison_client.get("/regions")
    body = {r["source_team_id"]: r for r in resp.json()}

    assert body["wasdale"]["outcome_data_source"] == "stated_by_team"
    assert body["edale"]["outcome_data_source"] == "inferred_from_keywords"
    assert body["ovmro"]["outcome_data_source"] == "inferred_from_keywords"


def test_region_geocode_match_rate_computed_correctly(region_comparison_client):
    resp = region_comparison_client.get("/regions")
    body = {r["source_team_id"]: r for r in resp.json()}

    # edale: 2 matched out of 3
    assert body["edale"]["geocode_match_rate"] == pytest.approx(0.667, abs=0.001)
    assert body["wasdale"]["geocode_match_rate"] == 1.0


def test_stats_and_regions_endpoints_agree(region_comparison_client):
    """/stats embeds the same region summaries as /regions — they share
    one code path now specifically so they can't drift apart."""
    stats_regions = {r["source_team_id"]: r for r in region_comparison_client.get("/stats").json()["regions"]}
    direct_regions = {r["source_team_id"]: r for r in region_comparison_client.get("/regions").json()}

    assert stats_regions == direct_regions


@pytest.fixture
def yearly_client(tmp_path, monkeypatch):
    """Mirrors the real coverage gap: Edale has genuine multi-year
    history, Wasdale/OVMRO only exist in the most recent year — the
    yearly endpoint must surface this, not hide it behind a misleading
    combined total."""
    db_path = tmp_path / "test_yearly.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT
        )
    """)
    rows = [
        ("edale", "A", "2023-01-01", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
        ("edale", "B", "2024-01-01", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
        ("edale", "C", "2024-06-01", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
        ("edale", "D", "2026-01-01", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
        ("wasdale", "E", "2026-02-01", None, "walking", "Alert", "stated_by_team",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
        ("ovmro", "F", "2026-03-01", None, "climbing", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
    ]
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_yearly_stats_surfaces_coverage_gap_not_just_totals(yearly_client):
    """
    The core reason teams_reporting exists: a jump from 2 incidents in
    2024 to 3 in 2026 must be explainable as "a new team started
    reporting," not misread as a real 50% increase in incidents.
    """
    resp = yearly_client.get("/stats/yearly")
    body = {y["year"]: y for y in resp.json()}

    assert body["2023"]["teams_reporting"] == ["edale"]
    assert body["2024"]["teams_reporting"] == ["edale"]
    assert body["2024"]["incident_count"] == 2
    assert sorted(body["2026"]["teams_reporting"]) == ["edale", "ovmro", "wasdale"]
    assert body["2026"]["incident_count"] == 3


def test_yearly_stats_filtered_by_team_shows_genuine_trend(yearly_client):
    """Filtering to a single team removes the coverage-gap issue
    entirely — this is the "genuine long-term trend" view."""
    resp = yearly_client.get("/stats/yearly?team=edale")
    body = {y["year"]: y for y in resp.json()}

    assert set(body.keys()) == {"2023", "2024", "2026"}
    assert all(y["teams_reporting"] == ["edale"] for y in body.values())


@pytest.fixture
def timeofday_client(tmp_path, monkeypatch):
    """OVMRO structurally never has a time value — this fixture must
    prove the endpoint reflects that rather than silently including
    Snowdonia as if it had (zero) time data like the others."""
    db_path = tmp_path / "test_timeofday.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT
        )
    """)
    rows = [
        ("edale", "A", "2026-01-01", "14:30", "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
        ("edale", "B", "2026-01-02", "14:45", "walking", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
        ("wasdale", "C", "2026-02-01", "09:15", "walking", "Alert", "stated_by_team",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
        ("ovmro", "D", "2026-03-01", None, "climbing", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
        ("ovmro", "E", "2026-03-02", None, "climbing", "x", "inferred_from_keywords",
         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None),
    ]
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_timeofday_excludes_ovmro_which_never_has_time_data(timeofday_client):
    resp = timeofday_client.get("/stats/timeofday")
    body = resp.json()

    assert "ovmro" not in body["teams_with_time_data"]
    assert set(body["teams_with_time_data"]) == {"edale", "wasdale"}
    assert body["incidents_with_time_data"] == 3
    assert body["total_incidents"] == 5


def test_timeofday_returns_all_24_hours_including_zero_count(timeofday_client):
    resp = timeofday_client.get("/stats/timeofday")
    buckets = resp.json()["buckets"]

    assert len(buckets) == 24
    hour_9 = next(b for b in buckets if b["hour"] == 9)
    hour_14 = next(b for b in buckets if b["hour"] == 14)
    hour_3 = next(b for b in buckets if b["hour"] == 3)

    assert hour_9["incident_count"] == 1
    assert hour_14["incident_count"] == 2
    assert hour_3["incident_count"] == 0


@pytest.fixture
def activity_breakdown_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_activity.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT
        )
    """)
    rows = []
    for i in range(6):
        rows.append(("edale", f"A{i}", "2026-01-01", None, "walking", "x", "inferred_from_keywords",
                      None, None, None, None, "matched", None, None, None, None, None, None, None, None, None))
    for i in range(2):
        rows.append(("edale", f"B{i}", "2026-01-01", None, "climbing", "x", "inferred_from_keywords",
                      None, None, None, None, "matched", None, None, None, None, None, None, None, None, None))
    for i in range(7):
        rows.append(("ovmro", f"C{i}", "2026-01-01", None, "climbing", "x", "inferred_from_keywords",
                      None, None, None, None, "matched", None, None, None, None, None, None, None, None, None))
    for i in range(1):
        rows.append(("ovmro", f"D{i}", "2026-01-01", None, "walking", "x", "inferred_from_keywords",
                      None, None, None, None, "matched", None, None, None, None, None, None, None, None, None))
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_activity_breakdown_shows_regional_skew(activity_breakdown_client):
    """The core reason this endpoint exists: Snowdonia's real skew
    toward climbing vs. the other regions' skew toward walking must
    show up as proportions, not be flattened into one 'top activity'
    label."""
    resp = activity_breakdown_client.get("/stats/activity-breakdown")
    body = resp.json()

    edale_rows = {r["activity_type"]: r["incident_count"] for r in body if r["source_team_id"] == "edale"}
    ovmro_rows = {r["activity_type"]: r["incident_count"] for r in body if r["source_team_id"] == "ovmro"}

    assert edale_rows["walking"] == 6
    assert edale_rows["climbing"] == 2
    assert ovmro_rows["climbing"] == 7
    assert ovmro_rows["walking"] == 1


@pytest.fixture
def notable_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_notable.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT
        )
    """)
    rows = [
        ("ovmro", "Tryfan", "2026-01-01", None, "climbing", "x", "inferred_from_keywords",
         "Narrative.", "https://ogwen-rescue.org.uk/1", None, None, "matched", None,
         220, 1, 12, None, None, None, None, None),
        ("ovmro", "Glyder Fach", "2026-02-01", None, "climbing", "x", "inferred_from_keywords",
         "Narrative.", "https://ogwen-rescue.org.uk/2", None, None, "matched", None,
         720, 2, 22, None, None, None, None, None),
        ("ovmro", "Aber Falls", "2026-03-01", None, "walking", "x", "inferred_from_keywords",
         "Narrative.", "https://ogwen-rescue.org.uk/3", None, None, "matched", None,
         90, None, 25, None, None, None, None, None),
        ("edale", "Kinder", "2026-01-01", None, "walking", "x", "inferred_from_keywords",
         "Narrative.", "https://x.com", None, None, "matched", None,
         None, None, None, None, None, None, None, None),
    ]
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_notable_stats_correctness(notable_client):
    resp = notable_client.get("/stats/notable")
    body = resp.json()

    assert body["longest_operation"]["location_text"] == "Glyder Fach"
    assert body["longest_operation"]["value"] == 720.0
    assert body["largest_deployment"]["location_text"] == "Aber Falls"
    assert body["largest_deployment"]["value"] == 25.0
    assert body["total_operation_hours"] == pytest.approx(17.2, abs=0.01)
    assert body["based_on_incident_count"] == 3  # Edale row excluded, no duration data


def test_notable_stats_never_includes_casualties(notable_client):
    """
    The core reason NotableRecord doesn't have a casualties field:
    turning a real operation into a casualty-count 'record' would be
    poor taste regardless of accuracy. This checks the raw response
    text, not just the schema, so a future field addition can't
    silently reintroduce it without this test catching it.
    """
    resp = notable_client.get("/stats/notable")
    assert "casualt" not in resp.text.lower()


@pytest.fixture
def top_locations_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_toploc.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT
        )
    """)
    rows = []
    def add(team, loc, n):
        for i in range(n):
            rows.append((team, loc, "2026-01-01", None, "walking", "x", "inferred_from_keywords",
                         None, None, None, None, "matched", None, None, None, None, None, None, None, None, None))
    add("edale", "Kinder Scout", 12)
    add("edale", "Stanage Edge", 9)
    add("edale", "Kinder", 5)
    add("ovmro", "Tryfan", 15)
    add("wasdale", "Scafell Pike", 20)
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_top_locations_ordering_and_limit(top_locations_client):
    resp = top_locations_client.get("/stats/top-locations?limit=3")
    body = resp.json()

    assert len(body) == 3
    assert body[0]["location_text"] == "Scafell Pike"
    assert body[0]["incident_count"] == 20
    assert body[1]["location_text"] == "Tryfan"
    assert body[2]["location_text"] == "Kinder Scout"


def test_top_locations_keeps_near_duplicates_separate(top_locations_client):
    """
    Documents the known limitation directly: "Kinder Scout" and
    "Kinder" are the same real place but stay as two entries, since
    this endpoint does raw-text frequency counting, not gazetteer
    matching.
    """
    resp = top_locations_client.get("/stats/top-locations?limit=10")
    locations = {r["location_text"]: r["incident_count"] for r in resp.json()}

    assert locations["Kinder Scout"] == 12
    assert locations["Kinder"] == 5
    assert "Kinder Scout" != "Kinder"  # sanity — they really are separate keys


@pytest.fixture
def elevation_daylight_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_elev_daylight.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT, daylight_status TEXT, elevation_m REAL
        )
    """)
    rows = [
        ("edale", "Kinder Scout", "2026-01-05", "17:45", "walking", "x", "inferred_from_keywords",
         None, None, 53.38, -1.87, "matched", None, None, None, None,
         4, 0, 0, 10, "clear", "darkness", 630),
        ("edale", "Mam Tor", "2026-01-05", "10:00", "walking", "x", "inferred_from_keywords",
         None, None, 53.35, -1.81, "matched", None, None, None, None,
         4, 0, 0, 10, "clear", "daylight", 517),
        ("wasdale", "Scafell Pike", "2026-02-01", "14:00", "walking", "x", "inferred_from_keywords",
         None, None, 54.45, -3.21, "matched", None, None, None, None,
         2, -2, 0, 20, "clear", "daylight", 978),
        ("ovmro", "Tryfan", "2026-03-01", None, "climbing", "x", "inferred_from_keywords",
         None, None, 53.11, -3.99, "matched", None, None, None, None,
         None, None, None, None, None, None, 917),
        ("edale", "No coords", "2026-04-01", None, "walking", "x", "inferred_from_keywords",
         None, None, None, None, "no_match", None, None, None, None,
         None, None, None, None, None, None, None),
    ]
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_elevation_bands_correctly_assigned(elevation_daylight_client):
    resp = elevation_daylight_client.get("/stats/elevation")
    body = resp.json()
    bands = {b["band_label"]: b["incident_count"] for b in body["bands"]}

    assert bands["400-600m"] == 1  # Mam Tor, 517m
    assert bands["600-800m"] == 1  # Kinder Scout, 630m
    assert bands["800-1000m"] == 2  # Tryfan 917m, Scafell Pike 978m
    assert body["incidents_with_elevation"] == 4  # ungeocoded row excluded
    assert body["total_incidents"] == 5


def test_elevation_region_averages(elevation_daylight_client):
    resp = elevation_daylight_client.get("/stats/elevation")
    by_region = {r["source_team_id"]: r for r in resp.json()["by_region"]}

    assert by_region["edale"]["average_elevation_m"] == pytest.approx(573.5)
    assert by_region["ovmro"]["average_elevation_m"] == 917.0
    assert by_region["wasdale"]["average_elevation_m"] == 978.0


def test_daylight_stats_correctness_and_ovmro_exclusion(elevation_daylight_client):
    """
    The important check: OVMRO has real elevation data in this fixture
    but must still be fully absent from daylight stats — proving the
    two exclusions (elevation vs. daylight) are independent, not
    accidentally coupled to the same "has any enrichment data" flag.
    """
    resp = elevation_daylight_client.get("/stats/daylight")
    body = resp.json()

    assert body["daylight_count"] == 2
    assert body["darkness_count"] == 1
    assert "ovmro" not in body["teams_included"]
    assert set(body["teams_included"]) == {"edale", "wasdale"}
    assert body["incidents_with_daylight_data"] == 3
    assert body["total_incidents"] == 5


@pytest.fixture
def dow_holiday_client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_dow_holiday.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT, daylight_status TEXT, elevation_m REAL,
            is_bank_holiday INTEGER, day_of_week TEXT, is_weekend INTEGER
        )
    """)
    rows = []
    def add(date, holiday, dow, weekend, n):
        for i in range(n):
            rows.append(("edale", f"Loc{i}", date, None, "walking", "x", "inferred_from_keywords",
                         None, None, None, None, "matched", None, None, None, None,
                         None, None, None, None, None, None, None, holiday, dow, weekend))
    add("2026-01-01", 1, "Thursday", 0, 6)
    add("2026-01-02", 0, "Friday", 0, 2)
    add("2026-01-03", 0, "Saturday", 1, 2)
    add("2026-01-05", 0, "Monday", 0, 2)
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_day_of_week_ordering_and_counts(dow_holiday_client):
    resp = dow_holiday_client.get("/stats/day-of-week")
    body = resp.json()

    days = [d["day_of_week"] for d in body["by_day"]]
    assert days == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    counts = {d["day_of_week"]: d["incident_count"] for d in body["by_day"]}
    assert counts["Thursday"] == 6
    assert counts["Tuesday"] == 0
    assert body["weekday_count"] == 10
    assert body["weekend_count"] == 2


def test_bank_holiday_uses_per_day_average_not_raw_total(dow_holiday_client):
    """
    The core reason this endpoint computes per-day averages: 6 raw
    incidents on the one bank holiday vs 6 raw incidents across three
    ordinary days would tie at "6 vs 6" if compared as totals — but the
    honest per-day rate is 6.0/day for the holiday vs 2.0/day for
    ordinary days, a real and correctly threefold difference.
    """
    resp = dow_holiday_client.get("/stats/bank-holidays")
    body = resp.json()

    assert body["avg_incidents_per_bank_holiday"] == 6.0
    assert body["avg_incidents_per_ordinary_day"] == 2.0
    assert body["bank_holiday_days_observed"] == 1
    assert body["ordinary_days_observed"] == 3


@pytest.fixture
def monthly_seasonal_client(tmp_path, monkeypatch):
    """Same scenario that broke the old year-and-month version: several
    years of data, August consistently busy, February consistently quiet."""
    db_path = tmp_path / "test_monthly_seasonal.db"
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE incidents (
            source_team_id TEXT, location_text TEXT, date TEXT, time TEXT,
            activity_type TEXT, outcome TEXT, outcome_source TEXT,
            narrative_raw TEXT, source_url TEXT, lat REAL, lon REAL,
            geocode_status TEXT, geocode_confidence TEXT,
            duration_minutes REAL, casualties_count REAL, team_members_attended REAL,
            temp_max_c REAL, temp_min_c REAL, precipitation_mm REAL,
            wind_speed_max_kmh REAL, weather_summary TEXT, daylight_status TEXT, elevation_m REAL,
            is_bank_holiday INTEGER, day_of_week TEXT, is_weekend INTEGER
        )
    """)
    rows = []
    for year in [2015, 2018, 2020, 2022, 2024, 2026]:
        for i in range(8):
            rows.append(("edale", "Loc", f"{year}-08-{i+1:02d}", None, "walking", "x",
                         "inferred_from_keywords", None, None, None, None, "matched", None,
                         None, None, None, None, None, None, None, None, None, None, None, None, None))
        for i in range(2):
            rows.append(("edale", "Loc", f"{year}-02-{i+1:02d}", None, "walking", "x",
                         "inferred_from_keywords", None, None, None, None, "matched", None,
                         None, None, None, None, None, None, None, None, None, None, None, None, None))
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()

    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)

    from main import app
    return TestClient(app)


def test_monthly_stats_aggregates_across_years_in_calendar_order(monthly_seasonal_client):
    """
    The core reason this endpoint was rewritten: it must combine every
    year into one true seasonal pattern (12 rows, Jan-Dec), not a
    chronological year-and-month timeline that only looks ordered when
    there's one year of data and breaks down once there are several.
    """
    resp = monthly_seasonal_client.get("/stats/monthly")
    body = resp.json()

    assert len(body) == 12
    assert [m["month"] for m in body] == [f"{i:02d}" for i in range(1, 13)]
    assert [m["month_label"] for m in body][:3] == ["Jan", "Feb", "Mar"]

    counts = {m["month_label"]: m["incident_count"] for m in body}
    assert counts["Aug"] == 48  # 8 incidents x 6 years
    assert counts["Feb"] == 12  # 2 incidents x 6 years
    assert counts["Jan"] == 0   # present with zero, not missing entirely