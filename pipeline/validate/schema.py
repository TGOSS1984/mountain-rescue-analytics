"""
schema.py

Pandera schema for the cleaned incidents table, run as a checkpoint
between cleaning and geocoding. If this fails, the pipeline stops rather
than quietly passing bad data downstream — a wrong incident count in a
portfolio dashboard is exactly the kind of thing that undermines the
"real analyst work" story this project is trying to tell.
"""

import pandera as pa
from pandera import Column, Check

ALLOWED_ACTIVITY_TYPES = {
    "climbing", "cycling", "running", "water",
    "search_missing_person", "walking", "animal_rescue", "unspecified",
}

ALLOWED_OUTCOMES = {
    "fatality", "air_ambulance", "hospital_transfer",
    "self_rescued", "stood_down", "unrecorded",
    # Wasdale states these directly rather than us inferring them —
    # kept as distinct values rather than remapped onto the keyword-based
    # set above, since "Alert" (no team deployment) and "self_rescued"
    # aren't quite the same claim.
    "Alert", "Limited Callout", "Full Callout",
}

incidents_schema = pa.DataFrameSchema(
    {
        "source_team_id": Column(str, nullable=False),
        "source_method": Column(str, Check.isin([
            "rest_api", "html_scrape",
            "html_scrape_single_page",        # Wasdale
            "html_scrape_rendered_table",     # OVMRO
            "html_scrape_paginated_archive",  # UWFRA
        ])),
        "incident_id": Column(str, nullable=True),  # nullable — see clean_incidents.py notes
        "location_text": Column(str, nullable=False),
        "date": Column(str, nullable=True, checks=Check.str_matches(r"^\d{4}-\d{2}-\d{2}$"), coerce=True),
        "time": Column(str, nullable=True, checks=Check.str_matches(r"^\d{2}:\d{2}$"), coerce=True),
        "activity_type": Column(str, Check.isin(ALLOWED_ACTIVITY_TYPES)),
        "outcome": Column(str, Check.isin(ALLOWED_OUTCOMES)),
        "outcome_source": Column(str, Check.isin(["stated_by_team", "inferred_from_keywords"])),
        "narrative_raw": Column(str, nullable=True),
        "source_url": Column(str, nullable=True),
        # duration_minutes/team_members_attended: originally OVMRO-only,
        # now also populated by UWFRA — null for Edale/Wasdale, which
        # simply don't publish this data, not zero-filled, so "not
        # provided" stays distinguishable from "recorded as zero."
        "duration_minutes": Column(float, nullable=True, checks=Check.ge(0)),
        "casualties_count": Column(float, nullable=True, checks=Check.ge(0)),
        "team_members_attended": Column(float, nullable=True, checks=Check.ge(0)),
        # UWFRA-only: aggregate volunteer person-hours for the whole
        # operation, genuinely unique to this source among the four.
        "total_attendance_minutes": Column(float, nullable=True, checks=Check.ge(0)),
    },
    strict=False,   # allow extra columns added later (e.g. geocoded lat/lon) without breaking this check
    coerce=True,
)


def validate(df):
    """Raises pandera.errors.SchemaError on failure — let it bubble up to run_pipeline.py."""
    return incidents_schema.validate(df, lazy=True)