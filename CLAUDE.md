# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OddsHarvester is a Python web scraper that extracts sports betting odds from oddsportal.com. It uses Playwright for browser automation and BeautifulSoup/lxml for HTML parsing. Supports multiple sports (football, tennis, basketball, rugby, ice hockey, baseball, American football, handball, volleyball, cricket), various betting markets, and stores output locally (JSON/CSV) or remotely (AWS S3).

## Before You Code — Read This

**`docs/agentic-gotchas.md`** documents recurring OddsPortal-specific traps that are not deducible from the code alone — stale/phantom SSR data, silent truncation by client-side rendering (pagination ellipsis, lazy-load, URL conventions), per-bookmaker data format variation, league sponsor renames, CLI normalization layering, and anti-bot detection symptoms. Read it before:

- Adding or modifying any DOM/JSON parsing in `base_scraper.py` or `market_extraction/`
- Iterating over rendered DOM collections (pagination, listings, scroll, market dropdowns)
- Parsing or extracting bookmaker odds, names, or any per-row attribute
- Adding a new league or modifying `sport_league_constants.py` / `league_aliases.py`
- Adding a CLI option or modifying option-validation logic in `cli/commands/`
- Changing Playwright browser args, stealth scripts, or anti-detection config in `playwright_manager.py`
- Triaging a "0 results returned" symptom before assuming it's a parsing bug

When a fix exposes a new OddsPortal behaviour worth remembering, append it to `docs/agentic-gotchas.md` (criteria are listed at the bottom of that file).

## Behavioral Guidelines (Karpathy / Multica)

Bias toward **caution over speed**. For trivial tasks, use judgment. **Project rules below override these** when they conflict.

### 1. Think Before Coding

- **State assumptions explicitly.** If multiple interpretations exist, present them — don't pick silently.
- **If unclear, stop and ask.** Don't hide confusion behind plausible-looking code.
- **If a simpler approach exists, say so.** Push back when warranted.

### 2. Simplicity First

- Minimum code that solves the problem. No speculative features, no abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested. No error handling for impossible scenarios.
- If you wrote 200 lines and 50 would do, rewrite.

### 3. Surgical Changes

- Touch only what the task requires. Don't "improve" adjacent code, comments, or formatting.
- Match existing style even if you'd do it differently.
- If you spot unrelated dead code, **mention it — don't delete it**.
- Only clean up imports/symbols _your own_ changes orphaned.
- Every changed line must trace directly to the user's request.

### 4. Goal-Driven Execution

Transform tasks into verifiable goals **before** coding:

- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step work, state a brief plan with per-step verification.

## Commands

**Package manager**: uv

```bash
# Install
uv sync

# Run scraper
uv run oddsharvester upcoming --sport football --date 20250101 --market 1x2
uv run oddsharvester historic --sport football --league england-premier-league --season 2022-2023 --market 1x2
uv run oddsharvester community --sport football --output top_predictions.json
uv run oddsharvester community --user BLAPRO --output profile.json
uv run oddsharvester community --match-url "https://www.oddsportal.com/football/h2h/.../" --output match_votes.json

# Tests
uv run pytest tests/ -q --ignore=tests/integration/                                # unit
uv run pytest tests/integration/ -q -m integration                                 # integration (HAR replay, default)
uv run pytest tests/integration/ -q -m integration --live                          # integration (live network)
uv run pytest tests/core/test_url_builder.py::TestUrlBuilder::test_method_name -q  # single test
uv run pytest --cov=src/oddsharvester --cov-report=term --ignore=tests/integration/

# Lint / format
uv run ruff format .
uv run ruff check --fix src/

# Validate league URLs (diagnostic, requires internet)
uv run python scripts/validate_league.py -s football -l brazil-serie-a --season 2024
uv run python scripts/validate_league.py -s football --all
```

## Architecture

Four-layer flow: `CLI (cli/) → Core (core/) → Data (utils/) → Storage (storage/)`. Entry point: `oddsharvester` (or `python -m oddsharvester`).

**Core orchestration** (`src/oddsharvester/core/`):

- `scraper_app.py` orchestrates browser + scraper + storage
- `odds_portal_scraper.py` navigates pages and coordinates per-match scraping
- `playwright_manager.py` owns browser lifecycle (reads `ODDSHARVESTER_HAR_REPLAY` / `ODDSHARVESTER_HAR_RECORD`)
- `browser/` — focused helpers (`CookieDismisser`, `PageScroller`, `MarketTabNavigator`, `SelectionManager`)
- `odds_portal_market_extractor.py` + `market_extraction/` — odds extraction, submarket grouping, odds history, navigation
- `url_builder.py`, `sport_market_registry.py`, `sport_period_registry.py`, `odds_portal_selectors.py`
- `retry.py` — **canonical location for `TRANSIENT_ERROR_KEYWORDS`** and retry/backoff utilities
- `scrape_result.py`, `exceptions.py` — `ScrapeResult` / `FailedUrl` / `ScrapeStats` and exception hierarchy

**Data layer** (`utils/`): `sport_market_constants.py` (`Sport` enum + per-sport `Market` enums + `SPORT_MARKETS_MAPPING`), `sport_league_constants.py`, `period_constants.py`.

**Storage layer** (`storage/`): `storage_manager.py` routes to `local_data_storage.py` (JSON/CSV) or `remote_data_storage.py` (S3).

## Adding a New Sport

1. Add to `Sport` enum in `utils/sport_market_constants.py`
2. Create market enum classes + add to `SPORT_MARKETS_MAPPING`
3. Add league URLs in `utils/sport_league_constants.py`
4. Add period definitions in `utils/period_constants.py`
5. Register markets in `core/sport_market_registry.py` (add to `register_all_markets`)
6. Add tests

## Adding a New League

1. Find the league URL on oddsportal.com
2. Add an entry to the appropriate sport dict in `utils/sport_league_constants.py`:
   ```python
   "league-slug": "https://www.oddsportal.com/{sport}/{country}/{league}/",
   ```
3. Slug is lowercase with hyphens (e.g., `croatia-hnl`, `japan-j1-league`)

## Integration Tests — HAR Replay

Integration tests run in **HAR replay mode by default** (deterministic, no network). Each JSON fixture has a sibling `<stem>.har`; the `har_for_match` fixture (`tests/integration/conftest.py`) returns it, and `PlaywrightManager` wires `context.route_from_har(..., not_found="abort")` when `ODDSHARVESTER_HAR_REPLAY` is set.

**Modes:**

- Default (`pytest tests/integration/ -m integration`) — replay only, `live_only` tests skipped.
- `--live` — bypass HAR, hit OddsPortal directly (slow, flaky on fixture drift; for nightly checks and re-capture).

**Capture / refresh:**

```bash
# Single match (writes JSON output + sibling .har)
uv run python -m tests.integration.helpers.capture --sport football --league premier-league \
    --match-url "https://..." --markets "1x2" --period "full_time" --bookies-filter "all" --capture-har

# Bulk re-capture
uv run python scripts/capture_all_hars.py
```

Recapture on parsing changes, Playwright upgrades, or quarterly.

**Known limit — `live_only` tests:** OddsPortal H2H pages (NBA, real-madrid-barcelona, djokovic-sinner) combine URL fragments (`#match_id`) with runtime-cache-busted AJAX, which HAR can't reproduce — replay falls back to the wrong match. Marked `@pytest.mark.live_only`, skipped by default; run with `--live`. See `tests/integration/helpers/capture.py:_alias_fragmented_redirect_targets` for the partial workaround that handles redirect-with-fragment cases.

## Code Style

- Python >=3.12, line length 120, double quotes, Ruff (pre-commit enforces)
- `S101` (assert) and `T201` (print) are allowed

## Development Guidelines

### Testing

- **Before any modification**: `uv run pytest tests/ -q` must pass.
- After changes: update related tests when behavior changes; new code → unit tests covering critical paths.
- Tests mirror source structure under `tests/`.

### DRY — Canonical Locations

Constants live in ONE place; import everywhere else. Never duplicate tuples/lists across files.

- Error keywords/patterns → `core/retry.py` (`TRANSIENT_ERROR_KEYWORDS`)
- Sport/market constants → `utils/sport_market_constants.py`
- Retry logic → `core/retry.py`

Before adding new constants/utilities, `grep`/`rg` to check if it already exists.

### Branch & Merge (linear history)

`master` history must stay **linear** — no `--no-ff` merge bubbles. Local config enforces `merge.ff = only` and `pull.ff = only`.

```bash
git switch -c feat/my-thing            # never commit straight to master
# ... commits ...
git fetch origin
git rebase origin/master               # replay branch on top of master
git switch master
git merge --ff-only feat/my-thing
git branch -d feat/my-thing
```

- **Never** `git merge --no-ff`; never resolve divergence with a merge commit.
- If `--ff-only` is rejected, rebase — don't work around it.
- **Never `push --force` published `master`** — public repo with forks and external PRs. Pre-`v0.2.1` history stays as-is.

## Release Process

Tag-based; PyPI publish is automated by `release.yml` on tag push (runs tests, builds, publishes, creates GitHub Release). Versioning follows SemVer.

```bash
git checkout master && git pull origin master
uv run pytest tests/ -q --ignore=tests/integration/

# bump version in pyproject.toml (X.Y.Z), then:
git add pyproject.toml
git commit -m "chore: release vX.Y.Z"
git tag vX.Y.Z
git push origin master --tags
```
