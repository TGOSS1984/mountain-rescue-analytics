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
        # OVMRO publish an "Incident Map" with 130+ points (date, location,
        # summary) but the table itself is loaded client-side via JS — the
        # static page just shows "Loading N data points…". The real data
        # comes from a backend endpoint the page's JS calls, which hasn't
        # been identified yet from static fetches alone. Likely either a
        # WordPress REST endpoint or a custom AJAX handler
        # (wp-admin/admin-ajax.php with an action parameter is common for
        # this kind of "loading…" pattern on WP sites).
        #
        # NOT wired into the scraper yet — see docs/data-dictionary.md,
        # "Adding a new source", step 2a: open browser dev tools on
        # /incident-maps/, watch the Network tab for the XHR/fetch request
        # that returns the incident JSON, and drop that URL in here as
        # `rest_api_candidate` (or a new `ajax_endpoint` key if it needs
        # a POST body). This is genuinely the best-looking source of the
        # three once that endpoint is found — it may already include
        # coordinates, which would remove the need to geocode Ogwen rows
        # at all.
        "archive_url": "https://ogwen-rescue.org.uk/incident-maps/",
        "archive_url_template": None,
        "rest_api_candidate": None,
        "post_link_pattern": None,
        "parser": "not_yet_implemented",
    },
    # Add further teams here once their archive structure has been checked
    # by hand — see docs/data-dictionary.md "Adding a new source" section.
]