"""
sources.py

Registry of mountain rescue team incident logs we pull from.

Keeping this as a plain list of config dicts (rather than hardcoding URLs
inside the scraper) means adding a new team later — Buxton MRT, a Lake
District team, a Welsh team — is a one-entry change here, not a new script.

Each entry describes the shape of that team's incident archive so the
scraper knows how to walk it. `archive_url_template` takes a page number;
most WordPress sites paginate as /incident/page/{n}/.
"""

SOURCES = [
    {
        "team_id": "edale",
        "team_name": "Edale Mountain Rescue Team",
        "region": "Peak District",
        "base_url": "https://edalemrt.co.uk",
        "archive_url": "https://edalemrt.co.uk/incident/",
        "archive_url_template": "https://edalemrt.co.uk/incident/page/{page}/",
        # Tried first — cleaner structured data if the endpoint is open.
        # Standard WordPress REST path for a custom post type named "incident".
        "rest_api_candidate": "https://edalemrt.co.uk/wp-json/wp/v2/incident",
        "post_link_pattern": r"https://edalemrt\.co\.uk/incident/(\d+)/",
    },
    {
        "team_id": "buxton",
        "team_name": "Buxton Mountain Rescue Team",
        "region": "Peak District",
        "base_url": "https://www.buxtonmountainrescue.org.uk",
        "archive_url": "https://www.buxtonmountainrescue.org.uk/call-outs",
        "archive_url_template": "https://www.buxtonmountainrescue.org.uk/call-outs?page={page}",
        "rest_api_candidate": None,  # confirm CMS platform before assuming WP
        "post_link_pattern": None,
    },
    {
        "team_id": "wasdale",
        "team_name": "Wasdale Mountain Rescue Team",
        "region": "Lake District",
        "base_url": "https://www.wmrt.org.uk",
        # Single long page listing the whole year's incidents in order,
        # rather than a paginated archive + separate detail pages like
        # Edale. Numbered entries follow the shape:
        #   "N. Location - Callout Type - HH:MMhrs Weekday Dth Month YYYY"
        # followed by the narrative paragraph(s). Handled by its own
        # parser (see ingest/scrape_wasdale.py) rather than the generic
        # WordPress-style scraper, because the page structure genuinely
        # is different — no point forcing one scraper to do both jobs.
        "archive_url": "https://www.wmrt.org.uk/report-page/",
        "archive_url_template": None,
        "rest_api_candidate": None,
        "post_link_pattern": None,
        "parser": "wasdale_single_page",
    },
    {
        "team_id": "ovmro",
        "team_name": "Ogwen Valley Mountain Rescue Organisation",
        "region": "Snowdonia (Eryri)",
        "base_url": "https://ogwen-rescue.org.uk",
        # The incident MAP page loads its data via client-side JS and
        # isn't fetchable directly (see scrape_ovmro.py docstring) — but
        # OVMRO also publish a separate "Incident Details" page with the
        # same data server-rendered as a plain table. That's what's
        # actually used, and it's richer than the map data anyway:
        # duration, casualty count, and team members attended per
        # incident, none of which Edale or Wasdale provide.
        "archive_url": "https://ogwen-rescue.org.uk/incident-details/",
        "archive_url_template": None,
        "rest_api_candidate": None,
        "post_link_pattern": None,
        "parser": "ovmro_details_table",
    },
    # Add further teams here once their archive structure has been checked
    # by hand — see docs/data-dictionary.md "Adding a new source" section.
]