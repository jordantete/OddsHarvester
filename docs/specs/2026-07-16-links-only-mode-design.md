# Links-only mode (`--links-only`)

**Date:** 2026-07-16
**Branch:** `feat/links-only-mode` (off `master`)
**Notion task:** Add --links-only mode to collect match URLs without scraping
**Origin:** GitHub issue #75 (two-pass workflow for a ~300K match run: collect the
match links first, scrape odds per link afterwards)

## Objective

Let a user collect the match links of a league/season (or an upcoming-matches
listing) **without scraping any odds**. The output feeds the existing
`--match-link` flow: collect links in pass 1, scrape odds per link in pass 2,
re-run only the failures with `--match-link ... --append`.

Today the link collection already exists internally (`_collect_match_links` for
historic pagination, `extract_match_links` for upcoming listings) but is always
followed by `extract_match_odds`. The feature is: stop after collection and emit
the links through the normal storage layer.

## Non-goals (YAGNI)

- No new subcommand (`collect-links`) — decided: a flag on `historic`/`upcoming`.
- No plain-text output format; links go through the existing JSON/CSV storage.
- No link-level dedup across files/runs (append stays pure concatenation).
- No resume/checkpoint of a partially collected pagination.
- No proxy rotation change: link collection stays on the default context
  (see multi-proxy spec, 2026-07-03).

## Decisions (from brainstorming)

1. **CLI shape:** boolean flag `--links-only` on both `historic` and `upcoming`,
   declared in `common_options` (envvar `OH_LINKS_ONLY`, default `False`).
2. **Output shape:** one row per match through `store_data`, with context columns:
   - historic: `{"match_link", "sport", "league", "season"}`
   - upcoming: `{"match_link", "sport", "league", "date"}` (`league` may be `None`
     in date mode)
3. **Ordering fix (shared code):** `_collect_match_links` deduplicates with
   `list(dict.fromkeys(all_links))` instead of `list(set(all_links))` — same
   dedup, listing order preserved, deterministic output. Benefits the normal
   historic flow too.
4. **Plumbing:** a `links_only: bool = False` parameter on
   `scrape_historic`/`scrape_upcoming` with an early return after link
   collection, passed down from `run_scraper`. Reuses `retry_scrape`,
   `_scrape_multiple_leagues` merging, storage, `--append`, stats and failure
   reporting unchanged.

## CLI behavior

- `--links-only` + `--match-link` is contradictory (the links are already
  collected) → click `UsageError` raised at validation time, before any browser
  starts.
- Options with no effect in links-only mode (`--markets`, `--period`,
  `--scrape-odds-history`, `--preview-only`, `--target-bookmaker`,
  `--bookies-filter`) are silently ignored (`--markets` has a default value, so
  erroring is not possible). Documented in `--help` and README.
- Options that stay honored: `--leagues`, `--season`, `--date`, `--max-pages`,
  `--include-started`, proxies, `--headless`, `--base-url`, locale/timezone,
  storage options (`--storage`, `--format`, `--file-path`, `--append`).
- End-of-run message: `Collected N match links (M listing pages failed).`
  Failed listing pages are reported through the existing stderr channel
  (`Failed URLs: [...]`), as page URLs.
- Exit code: `1` only when no links were collected (same contract as odds runs).

Examples:

```bash
# Pass 1 — collect links for a season
oddsharvester historic --sport football --leagues england-premier-league \
    --season 2022-2023 --links-only --format csv --file-path links.csv

# Upcoming listing
oddsharvester upcoming --sport football --date 20260720 --links-only

# Pass 2 — scrape odds per link (existing flow, repeat --match-link)
oddsharvester historic --sport football --season 2022-2023 --market 1x2 \
    --match-link "https://www.oddsportal.com/football/..." --append
```

## Core changes

### `core/odds_portal_scraper.py`

- `scrape_historic(..., links_only: bool = False)`: after
  `_collect_match_links`, if `links_only` return a `ScrapeResult` where
  - `success` = one dict per link: `{"match_link": url, "sport": sport,
    "league": league, "season": season}`, in listing order;
  - `failed` = one `FailedUrl` per failed listing page with
    `url=f"{base_url}#/page/{n}"`, so the existing stderr reporting shows which
    pages were missed.
- `scrape_upcoming(..., links_only: bool = False)`: after
  `extract_match_links` (date filter and `skip_started` already applied), if
  `links_only` return the same shape with `date` instead of `season`; no failed
  entries (single listing page — a navigation failure raises and is handled by
  `retry_scrape` as today).
- One small private helper builds the `ScrapeResult` from a list of links +
  context columns (single place that shapes the rows).
- `_collect_match_links`: `result.links = list(dict.fromkeys(all_links))`.

### `core/scraper_app.py`

- `run_scraper(..., links_only: bool = False)` forwards the flag to
  `scrape_historic`/`scrape_upcoming` in all four paths (single/multi-league ×
  historic/upcoming). The `match_links` fast path is unreachable with
  `links_only` (blocked at CLI validation).

### Storage

Unchanged. Link rows flow through `store_data` exactly like match rows
(JSON/CSV, `--append`, local/S3).

## Error handling

Same contract as today: operation-level retry with backoff around the scrape
call; failed listing pages are tracked without failing the run; the run fails
(exit 1) only when nothing was collected.

## Tests

- **CLI** (`tests/cli/`):
  - `--links-only --match-link` → `UsageError` for both commands.
  - flag parsed and forwarded to `run_scraper` (historic + upcoming).
- **Core** (`tests/core/`):
  - `scrape_historic(links_only=True)` stops before `extract_match_odds`
    (mocked, assert not called) and returns correctly shaped rows + `FailedUrl`
    per failed page.
  - `scrape_upcoming(links_only=True)` same, with `date` column and
    `league=None` in date mode.
  - `_collect_match_links` dedup preserves first-seen order across pages with
    duplicates.
  - `run_scraper` forwards `links_only` (single and multi-league paths).
- Audit existing tests for any dependence on `set()` ordering; update if found.

## Docs

- README: new "Two-pass workflow (collect links, then scrape)" section with the
  examples above, `--links-only` in the options table, note on ignored options,
  reference to issue #75.
