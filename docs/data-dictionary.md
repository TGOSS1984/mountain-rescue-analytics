# Data dictionary & methodology notes

This is the honest version of how the dataset gets built, including the
places where I had to make a judgement call rather than just reading a
value off the page. If you're reviewing this project as a hiring
manager or just curious how it holds together, this file is probably
more useful than the code itself.

## Where the data comes from

**Confirmed and wired in:**

- **Edale Mountain Rescue Team** (Peak District) — `edalemrt.co.uk/incident/`. Numbered, dated posts with a location title and narrative. Paginated archive + individual detail pages.
- **Wasdale Mountain Rescue Team** (Lake District) — `wmrt.org.uk/report-page/`. The whole year published as one page, numbered entries with an explicit stated callout type (`Alert` / `Limited Callout` / `Full Callout`) right in the source — a real severity signal, not one I had to infer.

**Identified but not yet wired in:**

- **Ogwen Valley Mountain Rescue Organisation** (Snowdonia/Eryri) — `ogwen-rescue.org.uk/incident-maps/`. This looks like the best source of the three: over 130 incidents, and the page structure (date/location/summary table plus an actual map) suggests they may already hold coordinates, not just place names. The catch is that the table loads via client-side JavaScript rather than being present in the page's initial HTML — the data comes from a backend request the page's own JS makes, which I haven't identified yet from a static fetch. Finding it just means opening the page in a browser, watching the Network tab for the request that returns the incident data, and pointing the scraper at that URL directly instead of the HTML. See "Adding a new source" below.
- **Buxton Mountain Rescue Team** (Peak District) — has a `/call-outs` page; CMS platform and structure not yet confirmed.

I chose team-level incident logs over Mountain Rescue England & Wales' national statistics because MREW's published data is annual aggregate PDFs (counts by category and region, going back to 1980) — good for national trend context, but not row-level records with locations, which is what this project needed in order to map and geocode individual incidents.

Bringing in Wasdale (Lake District) and, once its data endpoint is found, Ogwen Valley (Snowdonia) alongside Edale (Peak District) is what actually makes this a national picture rather than a single-region case study — three of England and Wales' busiest mountain areas, each with a genuinely different terrain and weather profile.

## Fields and how they're derived

| Field | How it's produced | Confidence |
|---|---|---|
| `incident_id` | Parsed from "Incident N" or "Dog Callout N" in the post text | High — this is stated directly by the team |
| `date` | Parsed from a date string in the opening line of the post | High where present; ~a handful of posts have no clear date and are left null rather than guessed |
| `time` | Parsed from a timestamp in the opening line (either "1748hrs" or "13:37" style) | High. Earlier version of this regex mistakenly matched the year (e.g. "2026" as 20:26) — caught by the test suite, fixed, and kept as a regression test so it can't silently reappear |
| `location_text` | The incident's title, as published | This is a name, not a coordinate — see geocoding below |
| `activity_type` | Inferred from keywords in the narrative (walker, climber, cyclist, etc.) | **Judgement call.** This is a simple rule-based classifier, not a field the source provides directly. It will misclassify ambiguous cases — e.g. if a walker witnesses a climber's fall, the keyword "climber" wins even though a walker reported it. Treat this column as a reasonable first pass, not ground truth |
| `outcome` | Team-stated callout type (Wasdale) where available, otherwise inferred from narrative keywords (Edale) | Wasdale: high — this is a direct source field. Edale: **judgement call**, see above |
| `outcome_source` | `"stated_by_team"` or `"inferred_from_keywords"` | Records which of the two applies for that row, so the two aren't silently blended |
| `lat` / `lon` | Geocoded from `location_text` via Nominatim (OpenStreetMap), biased to a Peak District bounding box | Varies — see `geocode_confidence` |
| `geocode_confidence` | "high" if Nominatim's match type is a natural feature (peak, hill, water); "low" otherwise | Nominatim doesn't return a numeric confidence score, so this is a derived proxy, not a native field |
| `geocode_status` | "matched", "no_match", or "skipped" (empty location text) | — |

## What gets dropped, and why

A row is dropped during cleaning only if it has **neither** a parseable
date **nor** any location text — at that point there's nothing usable
left to analyse. Rows missing just one of those (e.g. a location but no
clear date) are kept, with the missing field left null, so they still
count toward totals even if they can't be plotted on a timeline.

Duplicate detection is on (`source_team_id`, `incident_id`, `date`)
together, not `incident_id` alone — incident numbering resets per team,
so "Incident 12" from two different teams on two different dates are
legitimately different rows.

## Known limitations

- **Geocoding precision reflects the source, not a shortcoming of the
  pipeline.** Team incident logs name a feature ("Kinder", "Mam Tor"),
  not a grid reference — so coordinates land on the named landmark, not
  the exact spot on the hill. That's an appropriate level of precision
  for a national/regional trends dashboard and deliberately mirrors how
  publicly available.
- **The activity/outcome classifiers are keyword-based**, not NLP. On a
  larger version of this project, a proper text classification model
  would be a natural next step — documented here rather than pretended
  away.
- **Coverage is currently one confirmed team (Edale) plus placeholders
  for others.** The "multi-team, multi-region" version of this dataset
  depends on checking each new team's site structure individually — see
  below.

## Adding a new source

1. Visit the team's incident/callout archive in a browser and confirm
   it follows a similar shape: dated, numbered (or at least individually
   linkable) posts with a title and narrative.
2. Check whether it's WordPress and whether `/wp-json/wp/v2/{post_type}`
   responds — if so, add `rest_api_candidate` in `sources.py` and you're
   mostly done.
   - **2a. If the data loads via JavaScript** (a page that shows
     "Loading N data points…" before the table appears, like OVMRO's
     incident map) — the HTML you fetch won't contain the data at all.
     Open the page in a real browser, open dev tools → Network tab,
     reload, and look for an XHR/fetch request returning JSON. That URL
     is your real data source — point the scraper at it directly rather
     than trying to parse rendered HTML that a plain `requests.get()`
     will never actually see.
3. If not WordPress, inspect the archive page's HTML for the actual
   heading/link selectors and update `_parse_archive_page` in
   `scrape_team_incidents.py` accordingly — don't assume Edale's
   selectors will match another team's theme.
4. If the team publishes as one long page rather than a paginated
   archive (like Wasdale), it's usually cleaner to write a small
   dedicated parser — see `scrape_wasdale.py` — than to force it through
   the generic archive-page scraper.
5. Add the team's operational region to `TEAM_REGION` and, if it's a new
   region, a bounding box to `REGION_VIEWBOXES` in
   `geocode/geocode_locations.py` — otherwise its incidents will be
   geocoded against the wrong part of the country.
6. Add appropriate delay/politeness settings — these are volunteer-run
   charity sites, not commercial APIs designed for scraping load.