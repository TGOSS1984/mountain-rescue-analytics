# Data dictionary & methodology notes

This is the honest version of how the dataset gets built, including the
places where I had to make a judgement call rather than just reading a
value off the page. If you're reviewing this project as a hiring
manager or just curious how it holds together, this file is probably
more useful than the code itself.

## Where the data comes from

**All three confirmed and wired in:**

- **Edale Mountain Rescue Team** (Peak District) — `edalemrt.co.uk/incident/`. Numbered, dated posts with a location title and narrative. Paginated archive + individual detail pages.
- **Wasdale Mountain Rescue Team** (Lake District) — `wmrt.org.uk/report-page/`. The whole year published as one page, numbered entries with an explicit stated callout type (`Alert` / `Limited Callout` / `Full Callout`) right in the source — a real severity signal, not one I had to infer.
- **Ogwen Valley Mountain Rescue Organisation** (Snowdonia/Eryri) — `ogwen-rescue.org.uk/incident-details/`. OVMRO actually publish two views of the same data: an incident *map* that loads via client-side JavaScript (not fetchable with a plain request), and a *details* page that renders the same data as a plain server-side table — which is what the scraper uses. It's the richest of the three sources: on top of location and narrative, every row states an operation duration, a casualty count, and the number of team members who attended, none of which the other two teams publish. Worth remembering when the pattern "the map version is JS-loaded" comes up elsewhere — check for a details/table view before concluding a source needs a browser to scrape.

**Identified but not yet wired in:**

- **Buxton Mountain Rescue Team** (Peak District) — has a `/call-outs` page; CMS platform and structure not yet confirmed.

I chose team-level incident logs over Mountain Rescue England & Wales' national statistics because MREW's published data is annual aggregate PDFs (counts by category and region, going back to 1980) — good for national trend context, but not row-level records with locations, which is what this project needed in order to map and geocode individual incidents.

Having Edale (Peak District), Wasdale (Lake District), and OVMRO (Snowdonia) together is what makes this a genuinely national picture rather than a single-region case study — three of England and Wales' busiest mountain areas, each with a different terrain and weather profile, and — usefully — three different site structures to scrape, which is a more honest test of the pipeline than one format repeated three times.

## Fields and how they're derived

| Field | How it's produced | Confidence |
|---|---|---|
| `incident_id` | Parsed from "Incident N" or "Dog Callout N" in the post text | High — this is stated directly by the team |
| `date` | Parsed from a date string in the opening line of the post | High where present; ~a handful of posts have no clear date and are left null rather than guessed |
| `time` | Parsed from a timestamp in the opening line (either "1748hrs" or "13:37" style) | High. Earlier version of this regex mistakenly matched the year (e.g. "2026" as 20:26) — caught by the test suite, fixed, and kept as a regression test so it can't silently reappear |
| `location_text` | The incident's title, as published | This is a name, not a coordinate — see geocoding below |
| `activity_type` | Inferred from keywords in the narrative (walker, climber, cyclist, etc.) | **Judgement call.** This is a simple rule-based classifier, not a field the source provides directly. It will misclassify ambiguous cases — e.g. if a walker witnesses a climber's fall, the keyword "climber" wins even though a walker reported it. Treat this column as a reasonable first pass, not ground truth |
| `outcome` | Team-stated callout type (Wasdale) where available, otherwise inferred from narrative keywords (Edale, OVMRO) | Wasdale: high — this is a direct source field. Edale/OVMRO: **judgement call**, see above |
| `outcome_source` | `"stated_by_team"` or `"inferred_from_keywords"` | Records which of the two applies for that row, so the two aren't silently blended |
| `duration_minutes` | OVMRO only — total operation duration, stated directly by the team | High confidence, direct source field. Null for Edale/Wasdale, who don't publish this |
| `casualties_count` | OVMRO only — number of casualties, where stated | Null (not zero) where OVMRO didn't state a count — "not stated" and "zero" are kept distinct |
| `team_members_attended` | OVMRO only — number of team members deployed | Direct source field |
| `lat` / `lon` | Geocoded from `location_text` via Nominatim (OpenStreetMap), biased to a Peak District bounding box | Varies — see `geocode_confidence` |
| `geocode_confidence` | "high" if Nominatim's match type is a natural feature (peak, hill, water); "low" otherwise | Nominatim doesn't return a numeric confidence score, so this is a derived proxy, not a native field |
| `geocode_status` | "matched", "no_match", or "skipped" (empty location text) | — |
| `temp_max_c` / `temp_min_c` / `precipitation_mm` / `wind_speed_max_kmh` | Historical daily weather from Open-Meteo, matched on (region, date) | One reading shared by every incident in that region on that day — see "Weather is regional, not per-incident" below |
| `weather_summary` | Open-Meteo's WMO weather code, collapsed into a handful of readable buckets (clear/cloudy/rain/snow/storm/other) | A simplification for charting — see `pipeline/weather/join_weather.py`'s `WEATHERCODE_BUCKETS` for the exact mapping |
| `daylight_status` | "daylight" or "darkness", from comparing the incident's recorded time against that day's sunrise/sunset | Only computable where both a parsed time and a weather match exist. Always null for OVMRO, which never records a start time at all |
| `elevation_m` | Terrain elevation at the geocoded coordinate, from Open-Meteo's elevation API | Null wherever `lat`/`lon` are null. Deduplicated and cached — two incidents at the same named peak cost one lookup, not two |
| `is_bank_holiday` | Whether the date was a UK bank holiday (England & Wales division), from gov.uk's bank holidays API | Null for dates outside the range that API actually publishes (a rolling few years) — see "Bank holidays don't cover the full date range" below. Not the same as `False` |
| `day_of_week` / `is_weekend` | Derived directly from `date` | High confidence wherever a date exists — no external dependency, unlike `is_bank_holiday` |

## Weather is regional, not per-incident

Weather is joined per region per day, using one fixed reference point per region (roughly the geographic centre of where each team operates), not each incident's own coordinates. Two incidents on the same day, one at Kinder Scout and one at Stanage Edge, get identical weather readings. That's a deliberate simplification: it's accurate enough for "was it a wet week" analysis, but it's regional daily weather, not a precise per-incident reading, and the weather chart's own copy says so rather than implying more precision than the data actually has.

## Bank holidays don't cover the full date range

Gov.uk's bank holidays API only publishes a rolling window of a few years, not a full historical archive — and Edale's incident history goes back to 2014. A date outside that published range gets `is_bank_holiday = null`, not `false`. Marking it `false` would be a guess dressed up as a fact: the API genuinely doesn't say either way for those years, and the pipeline says so rather than assuming "probably not a holiday" and moving on.

## Why Scotland isn't in this dataset

I looked into this properly rather than assuming it wasn't possible. Scottish Mountain Rescue, the umbrella body, publishes the same kind of thing Mountain Rescue England & Wales does — annual aggregate PDF statistics, not row-level incident records, so it was never going to work for this project regardless of region.

The more interesting finding was at team level. I checked Cairngorm, Lochaber (which covers Ben Nevis and Glencoe), Glencoe MRT directly, and Arran MRT — the classic, well-known Highland teams, exactly the ones you'd expect to have the richest data. None of them publish a structured incident log on their own website the way Edale, Wasdale, and OVMRO do:

- **Lochaber's** website has three pages total — home, about the team, how to support us — and explicitly points people to Facebook and Instagram for updates.
- **Cairngorm's** `/blog` is real, but it's equipment donations, training days, and partnership announcements. Their actual callout narratives live on X.
- **Glencoe** and **Arran** follow the same pattern — Arran posts numbered callouts, but only to X, never their own site.

I did consider scraping X for one of these teams, since Arran's posts are genuinely structured (numbered, dated, with a narrative — similar shape to what I already had). I decided against it. X requires authentication now, the API costs money, and unauthenticated scraping is fragile and against their terms of service — a fundamentally different and riskier kind of problem than politely fetching a public webpage, which is what every other source in this project does.

**Moffat Mountain Rescue Team** (Southern Uplands — Dumfries and the Scottish Borders, not the Highlands) is the one Scottish team I found with a genuine website incident archive, a WordPress `/news/` page with real dated callout posts. It's not currently included, mainly because it isn't the "proper Highlands" data most people would picture when they hear "Scottish mountain rescue," and because unlike the other three sources, Moffat's news feed mixes real callouts with unrelated posts (award announcements, fundraising, recruitment), which would need a filtering step none of the current sources require. It's a legitimate future addition, just not the same one-to-one fit as the other three.

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
- **Coverage is three teams across three regions (Peak District, Lake
  District, Snowdonia), plus Buxton identified but not yet wired in.**
  Scotland was investigated and deliberately excluded — see "Why
  Scotland isn't in this dataset" above. Adding a fourth region depends
  on finding a team whose site actually publishes a structured incident
  log, which turned out to be the real bottleneck, not the scraping
  itself — see below.

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