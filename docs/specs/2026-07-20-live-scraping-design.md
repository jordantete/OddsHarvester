# Live Scraping Support - Design

Date: 2026-07-20
Status: validated (pending implementation plan)

## Goal

Add a `live` CLI command that takes a one-shot snapshot of matches currently in play:
per-bookmaker in-play odds for the requested markets, plus live context (score, period,
scrape timestamp). Football first, but the design is sport-generic.

Repeated sampling (watch mode) is explicitly out of scope: polling is orchestrated
externally (cron, odds_evolution_collector), one snapshot per invocation.

## Investigation findings (verified live on 2026-07-20)

OddsPortal has a dedicated in-play architecture:

- `/inplay-odds/live-now/<sport>/` lists matches currently live that have bookmaker
  live odds: period marker (`1S`, `65'`, `HT`), current score, average odds. Rows reuse
  the same `data-testid` family as classic listings (`game-row`, `event-participants`).
  Row hrefs already carry the in-play match URL form.
- `/inplay-odds/scheduled/<sport>/` lists upcoming matches that will have live odds.
- Match-level view: `<match_url>/inplay-odds/#<match_id>` opens an "In-Play Odds" tab,
  distinct from "Pre-match Odds", with a per-bookmaker odds table, live market tabs
  (Home/Away or 1x2, Over/Under, Asian Handicap, Correct Score, Odd or Even), period
  tabs, Classic/Crypto bookie filter, payout column, and live score in the header.
- The in-play view reuses existing scraper selectors: `bookmaker-table-header-line`,
  `bookies-filter-nav`, `kickoff-events-nav`, `sub-nav-*`, `odd-container-default`,
  `over-under-expanded-row`, `game-host`, `game-guest`, breadcrumbs. New live-specific
  testids: `live-info`, `odds-status-indicator`.
- Odds update in place without page reload: the page itself polls first-party feeds
  (`/feed/live-event/*.dat` roughly every 10s, `/feed/postmatch-score/*.dat` every
  3-4s). Verified odds movement during observation (Winamax 1.84/1.78 -> 1.72/1.86).
  A snapshot therefore needs a single page visit and DOM parsing only.
- In-play bookmaker coverage is thin from FR geo: Betclic.fr + Winamax only, versus
  15-20 bookmakers pre-match. Coverage is geo-dependent (same pattern as the Pinnacle
  finding).
- Observed drift from gotcha §9: `FinishedFIN` now appears inside `time-item` on
  `/matches/` listings (doc says `game-status-box`). To be corrected in the gotchas.

## CLI interface

```
oddsharvester live --sport football [--markets 1x2,over_under] [--league <slug>]
                   [--bookies-filter all|classic|crypto] [--match-link URL ...]
                   [--storage local|remote] [--format json|csv] [--headless] ...
```

- `--sport` required. Any sport with registered markets works; football is the first
  target.
- `--league` optional: post-listing filter on the league slug (the live-now listing is
  not league-filterable by URL; filter on row group breadcrumbs).
- `--match-link` optional: scrape the given matches directly in live mode, bypassing
  the listing. This is the building block for external re-sampling of a known match.
  Accepts both the classic match URL and the in-play form; the scraper normalizes by
  appending `/inplay-odds/` before the fragment when missing.
- Reused unchanged: `--markets`, `--bookies-filter`, proxy options, browser options,
  storage options, `--request-delay`, `--concurrency-tasks`, `--links-only`.
- Deliberately absent: `--date`, `--kickoff-within-hours`, `--include-started`,
  `--scrape-odds-history` (no odds history on the in-play view in v1), `--period`
  (v1 scrapes the default current-period view; period tabs are a later extension),
  and any watch/interval option.
- Validation: `--sport` required; clear error if the sport has no registered markets;
  zero live matches is not an error (empty output, message, exit 0).

## Architecture

Mirror of `scrape_upcoming`, four anchor points:

1. **URL builder** (`url_builder.py`): `get_live_listing_url(sport)` returns
   `{base_url}/inplay-odds/live-now/{sport}/`. Honors `--base-url` (regional mirrors,
   gotcha §7).
2. **Link collection** (`base_scraper.py`): new `extract_live_match_links()` on the
   live-now listing. No started filter (everything is live by definition). Per row:
   href (taken as-is, it already carries `/inplay-odds/#<match_id>`), league from the
   group breadcrumb, current score, period marker. Dedupe on href (DOM duplicates,
   see `_is_offscreen_row`).
3. **Per-match scraping** (`odds_portal_scraper.py`): `scrape_live()` modeled on
   `scrape_upcoming`: same concurrency semaphore, `request_delay`, retry. Per match:
   navigate to the in-play URL, extract metadata with existing helpers (`game-host`,
   `game-guest`, breadcrumbs), extract live context from the `live-info` testid
   (score, period) plus a UTC scrape timestamp, then markets via the existing
   `OddsPortalMarketExtractor` (same `sub-nav-*` tabs, same odd containers). One
   visit per match, no refresh.
4. **Orchestration** (`scraper_app.py` + `cli/commands/live.py`): new
   `command="scrape_live"` routed like the others; the CLI command is a near-clone of
   `upcoming.py`.

Edge case: a match can finish between the listing read and the match page visit (or
the In-Play tab can disappear). Detection: header without `live-info` or Finished
status. The match is skipped with an info log, not recorded as a FailedUrl.

Known residual unknowns, to resolve during the first live-football session (with HAR
capture): exact live market tab names for football, and the football `live-info`
format (`65'`, `HT`, score `2:1`). Requested markets absent in live mode produce a
clean warning, never a crash.

## Output format

Same per-match structure as `upcoming` (metadata keys + one block per market with
per-bookmaker odds), plus flat live fields:

```json
{
  "home_team": "...", "away_team": "...", "league_name": "...",
  "match_date": "...",
  "scraped_at_utc": "2026-07-20T19:32:08Z",
  "live_score_home": 2,
  "live_score_away": 1,
  "live_score_raw": "2:1",
  "live_period": "65'",
  "1x2_market": [ { "bookmaker_name": "Betclic.fr", "...": "..." } ]
}
```

- `live_period`: raw marker as displayed. No cross-sport normalization in v1.
- `live_score_home/away`: integers when the main score parses, null otherwise;
  `live_score_raw` keeps the full string (covers compound formats such as tennis
  `0:0 (3:2)` and cricket).
- `scraped_at_utc`: gives meaning to the odds/score pair when an external
  orchestrator samples repeatedly.
- CSV: same fields as flat columns (existing storage flattening).
- Odds come from the In-Play tab only, never mixed with pre-match odds.

## Anti-bot

- One snapshot has exactly the request profile of an `upcoming` run: 1 listing page +
  N match pages, spaced by `--request-delay` (default 1s), concurrency 3. No reload,
  no client-side polling of our own.
- Documentation for external samplers: interval of at least 60s between snapshots,
  and `--match-link` mode to re-scrape a targeted match without re-visiting the
  listing on every tick.
- Gotcha §6 symptoms apply unchanged; no new stealth work.

## Error handling

- Match finished between listing and visit: skip + info log.
- Requested market absent in live mode: warning + empty market, match stays in output.
- Zero live matches: empty output, exit 0, clear message.
- Transient errors: existing retry/backoff (`core/retry.py`).

## Testing

- Unit: saved DOM fixtures (live-now listing + in-play match page) for
  `extract_live_match_links`, `live-info` parsing, URL building. Mirrors the existing
  `tests/` structure.
- Integration (HAR replay): during the first live-football evening, capture one
  listing HAR and one in-play match HAR with the existing capture helper
  (`--capture-har`). A captured live match is ephemeral, so the HAR becomes the only
  replayable truth (capture once, replay forever). The h2h+fragment HAR weakness is
  mitigated here because the `/inplay-odds/` path makes the URL discriminating even
  without the fragment; if needed, `_alias_fragmented_redirect_targets` exists.
- `--live` integration test: self-discovering. It visits live-now and `pytest.skip`s
  when no match is in play (live football at CI time cannot be guaranteed).

## Documentation updates

- New §15 in `docs/agentic-gotchas.md`: in-play architecture (URLs, `.dat` feeds,
  thin bookmaker coverage, Pre-match vs In-Play tab, ephemeral live pages).
- Fix §9 drift: `FinishedFIN` observed inside `time-item`.
- README: `live` command section, including the external-sampling guidance.

## Out of scope (v1)

- Watch/interval mode inside the tool.
- In-play odds history.
- Period-specific live odds (`--period`).
- Cross-sport normalization of period markers.
- Scraping `/inplay-odds/scheduled/` (possible later extension).
