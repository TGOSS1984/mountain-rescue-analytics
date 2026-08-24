# Data dictionary & methodology notes

This is the honest version of how the dataset gets built, including the
places where I had to make a judgement call rather than just reading a
value off the page. If you're reviewing this project as a hiring
manager or just curious how it holds together, this file is probably
more useful than the code itself.

## Where the data comes from

**All four confirmed and wired in:**

- **Edale Mountain Rescue Team** (Peak District) — `edalemrt.co.uk/incident/`. Numbered, dated posts with a location title and narrative. Paginated archive + individual detail pages.
- **Wasdale Mountain Rescue Team** (Lake District) — `wmrt.org.uk/report-page/`. The whole year published as one page, numbered entries with an explicit stated callout type (`Alert` / `Limited Callout` / `Full Callout`) right in the source — a real severity signal, not one I had to infer.
- **Ogwen Valley Mountain Rescue Organisation** (Snowdonia/Eryri) — `ogwen-rescue.org.uk/incident-details/`. OVMRO actually publish two views of the same data: an incident *map* that loads via client-side JavaScript (not fetchable with a plain request), and a *details* page that renders the same data as a plain server-side table — which is what the scraper uses. On top of location and narrative, every row states an operation duration, a casualty count, and the number of team members who attended. Worth remembering when the pattern "the map version is JS-loaded" comes up elsewhere — check for a details/table view before concluding a source needs a browser to scrape.
- **Upper Wharfedale Fell Rescue Association** (Yorkshire Dales — Wharfedale, Nidderdale, Littondale, mid-Airedale) — `uwfra.org.uk/incidents`. A custom PHP-based CMS, not WordPress, so no REST API shortcut. Paginated archive with truncated narratives + individual article pages for the full text, same two-step pattern as Edale. Genuinely richer than OVMRO in one respect: alongside operation duration and team size, UWFRA also states a *total attendance* figure — aggregate volunteer person-hours for the whole operation, not just headcount × duration (it accounts for shift changes and rotating personnel, so it's kept as its own field rather than computed). UWFRA is also the first source in this project that regularly responds to animal-welfare callouts (sheep, dogs) as well as human incidents — see `animal_rescue` below.

**Identified but not yet wired in:**

- **Buxton Mountain Rescue Team** (Peak District) — has a `/call-outs` page; CMS platform and structure not yet confirmed.

I chose team-level incident logs over Mountain Rescue England & Wales' national statistics because MREW's published data is annual aggregate PDFs (counts by category and region, going back to 1980) — good for national trend context, but not row-level records with locations, which is what this project needed in order to map and geocode individual incidents.

Having Edale (Peak District), Wasdale (Lake District), OVMRO (Snowdonia), and UWFRA (Yorkshire Dales) together is what makes this a genuinely national picture rather than a single-region case study — four of England and Wales' busiest mountain and upland areas, each with a different terrain and weather profile, and — usefully — four different site structures to scrape, which is a more honest test of the pipeline than one format repeated four times.

## Fields and how they're derived

| Field | How it's produced | Confidence |
|---|---|---|
| `incident_id` | Parsed from "Incident N" or "Dog Callout N" in the post text | High — this is stated directly by the team |
| `date` | Parsed from a date string in the opening line of the post | High where present; ~a handful of posts have no clear date and are left null rather than guessed |
| `time` | Parsed from a timestamp in the opening line (either "1748hrs" or "13:37" style) | High. Earlier version of this regex mistakenly matched the year (e.g. "2026" as 20:26) — caught by the test suite, fixed, and kept as a regression test so it can't silently reappear |
| `location_text` | The incident's title, as published | This is a name, not a coordinate — see geocoding below. UWFRA's titles combine "what happened + where" ("Female fallen Bolton Abbey", "Sheep stuck in a bog") rather than a clean place name alone — kept as-is rather than attempting fragile regex extraction of "just the place," same honest approach already used for Edale/Wasdale titles that aren't pure place names either |
| `activity_type` | Inferred from keywords in the narrative (walker, climber, cyclist, animal-welfare terms, etc.) | **Judgement call.** This is a simple rule-based classifier, not a field the source provides directly. It will misclassify ambiguous cases — e.g. if a walker witnesses a climber's fall, the keyword "climber" wins even though a walker reported it. `animal_rescue` (sheep, dogs) was added for UWFRA, the first source with genuine animal-welfare callouts. Treat this column as a reasonable first pass, not ground truth |
| `outcome` | Team-stated callout type (Wasdale) where available, otherwise inferred from narrative keywords (Edale, OVMRO, UWFRA) | Wasdale: high — this is a direct source field. Others: **judgement call**, see above |
| `outcome_source` | `"stated_by_team"` or `"inferred_from_keywords"` | Records which of the two applies for that row, so the two aren't silently blended |
| `duration_minutes` | OVMRO and UWFRA — total operation duration, stated directly by the team | High confidence, direct source field. Null for Edale/Wasdale, who don't publish this. OVMRO gives `HH:MM`; UWFRA gives `Xhr Ymin` — different formats, parsed by two separate functions rather than one regex forced to cover both |
| `casualties_count` | OVMRO only — number of casualties, where stated | Null (not zero) where OVMRO didn't state a count — "not stated" and "zero" are kept distinct. UWFRA doesn't state a discrete casualty count |
| `team_members_attended` | OVMRO and UWFRA — number of team members deployed | Direct source field for both |
| `total_attendance_minutes` | UWFRA only — aggregate volunteer *person-hours* for the whole operation | Genuinely unique to UWFRA among the four sources. Not computed from `duration_minutes` × `team_members_attended` — it's UWFRA's own stated figure, which accounts for shift changes and rotating personnel that a simple multiplication would miss |
| `lat` / `lon` | Geocoded from `location_text` via Nominatim (OpenStreetMap), biased to a Peak District bounding box | Varies — see `geocode_confidence` |
| `geocode_confidence` | "high" if Nominatim's match type is a natural feature (peak, hill, water); "low" otherwise | Nominatim doesn't return a numeric confidence score, so this is a derived proxy, not a native field |
| `geocode_status` | "matched", "no_match", or "skipped" (empty location text) | — |
| `temp_max_c` / `temp_min_c` / `precipitation_mm` / `wind_speed_max_kmh` | Historical daily weather from Open-Meteo, matched on (region, date) | One reading shared by every incident in that region on that day — see "Weather is regional, not per-incident" below |
| `weather_summary` | Open-Meteo's WMO weather code, collapsed into a handful of readable buckets (clear/cloudy/rain/snow/storm/other) | A simplification for charting — see `pipeline/weather/join_weather.py`'s `WEATHERCODE_BUCKETS` for the exact mapping |
| `daylight_status` | "daylight" or "darkness", from comparing the incident's recorded time against that day's sunrise/sunset | Only computable where both a parsed time and a weather match exist. Always null for OVMRO and UWFRA, neither of which records a start time — see "Fields and how they're derived" above |
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
- **Coverage is four teams across four regions (Peak District, Lake
  District, Snowdonia, Yorkshire Dales), plus Buxton identified but not
  yet wired in.** Scotland was investigated and deliberately excluded —
  see "Why Scotland isn't in this dataset" above. Adding a fifth region
  depends on finding a team whose site actually publishes a structured
  incident log, which turned out to be the real bottleneck when adding
  UWFRA too, not the scraping itself — see below.

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
   selectors will match another team's theme. UWFRA turned out to be a
   custom PHP CMS, not WordPress, and got its own dedicated
   `scrape_uwfra.py` rather than forcing it through the generic scraper.
4. If the team publishes as one long page rather than a paginated
   archive (like Wasdale), it's usually cleaner to write a small
   dedicated parser — see `scrape_wasdale.py` — than to force it through
   the generic archive-page scraper.
5. Add the team's operational region to `TEAM_REGION` and, if it's a new
   region, a bounding box to `REGION_VIEWBOXES` in
   `geocode/geocode_locations.py` — otherwise its incidents will be
   geocoded against the wrong part of the country. **Real trap hit
   while adding UWFRA:** `TEAM_REGION` isn't defined once and shared —
   it's independently copied in four separate files
   (`geocode_locations.py`, `fetch_weather.py`, `join_weather.py`, and
   the API's `main.py`), plus a fifth mapping
   (`REGION_FILE_KEY` in `join_weather.py`) that has to match the
   weather-file naming convention exactly. Missing any one of these
   doesn't fail loudly — it just silently mis-geocodes or drops weather
   for the new region. Grep for the old regions' names across the whole
   repo before considering a new source "wired in."
6. Check whether any chart or endpoint hardcodes an assumption about
   which specific teams have a given field (e.g. "only OVMRO has
   duration data") — several did by the time UWFRA was added, since
   they were written when that assumption was still true. A hardcoded
   region name in a chart's title or copy is a sign the code was
   written for the teams that existed at the time, not built to
   generalise — worth fixing properly rather than just adding a new
   `if` branch.
7. Add appropriate delay/politeness settings — these are volunteer-run
   charity sites, not commercial APIs designed for scraping load.