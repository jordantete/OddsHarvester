# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OddsHarvester is a Python web scraper that extracts sports betting odds from oddsportal.com. It uses Playwright for browser automation and BeautifulSoup/lxml for HTML parsing. Supports multiple sports (football, tennis, basketball, rugby, ice hockey, baseball, American football, handball), various betting markets, and stores output locally (JSON/CSV) or remotely (AWS S3).

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

## Commands

**Package manager**: uv

```bash
# Install dependencies
uv sync

# Run the scraper
uv run oddsharvester scrape-upcoming --sport football --date 20250101 --markets 1x2
uv run oddsharvester scrape-historic --sport football --leagues england-premier-league --season 2022-2023 --markets 1x2

# Run unit tests
uv run pytest tests/ -q --ignore=tests/integration/

# Run integration tests (default mode: HAR replay, deterministic, no network)
uv run pytest tests/integration/ -q -m integration

# Run integration tests against live OddsPortal (slower, hits the network)
uv run pytest tests/integration/ -q -m integration --live

# Run a single test file
uv run pytest tests/core/test_url_builder.py -q

# Run a specific test
uv run pytest tests/core/test_url_builder.py::TestUrlBuilder::test_method_name -q

# Coverage report
uv run pytest --cov=src/oddsharvester --cov-report=term --ignore=tests/integration/

# Lint and format
uv run ruff format .
uv run ruff check --fix src/

# Validate league URLs (diagnostic tool, requires internet)
uv run python scripts/validate_league.py -s football -l brazil-serie-a --season 2024
uv run python scripts/validate_league.py -s football --all
```

## Architecture

Four-layer architecture:

```
CLI Layer (src/oddsharvester/cli/) → Core Layer (src/oddsharvester/core/) → Data Layer (src/oddsharvester/utils/) → Storage Layer (src/oddsharvester/storage/)
```

**Entry points**: `oddsharvester` CLI command (or `python -m oddsharvester`)

**Core Layer** (`src/oddsharvester/core/`):

- `scraper_app.py` — Top-level orchestrator; initializes browser, scraper, and storage
- `odds_portal_scraper.py` — Navigates pages, extracts match links, coordinates per-match scraping
- `playwright_manager.py` — Browser lifecycle (launch, context, page creation)
- `browser/` — Sub-package of focused browser-interaction helpers: `cookies.py` (`CookieDismisser`), `scrolling.py` (`PageScroller`), `market_navigation.py` (`MarketTabNavigator`), `selection.py` (`SelectionManager` + strategy pattern for filter/period selection)
- `odds_portal_market_extractor.py` — Extracts odds for specified markets from a match page
- `url_builder.py` — Constructs oddsportal.com URLs for historic/upcoming matches
- `sport_market_registry.py` — Registers market name→tab mappings per sport
- `sport_period_registry.py` — Manages match period selection (full-time, halves, quarters)
- `odds_portal_selectors.py` — CSS/XPath selectors for the OddsPortal DOM
- `retry.py` — Retry utilities with exponential backoff; **canonical location for `TRANSIENT_ERROR_KEYWORDS`**
- `scrape_result.py` — Data structures for scraping results (`ScrapeResult`, `FailedUrl`, `ScrapeStats`)
- `exceptions.py` — Custom exception hierarchy (`ScraperError`, `NavigationError`, `ParsingError`, etc.)
- `market_extraction/` — Sub-components: submarket extraction, odds parsing, odds history, navigation, market grouping

**Data Layer** (`src/oddsharvester/utils/`):

- `sport_market_constants.py` — `Sport` enum and per-sport `Market` enums (defines all supported markets)
- `sport_league_constants.py` — Maps sports to league slugs and URLs
- `period_constants.py` — Defines match periods per sport

**Storage Layer** (`src/oddsharvester/storage/`):

- `storage_manager.py` — Routes to local or remote storage
- `local_data_storage.py` — JSON/CSV file output
- `remote_data_storage.py` — AWS S3 upload

## Adding a New Sport

1. Add to `Sport` enum in `src/oddsharvester/utils/sport_market_constants.py`
2. Create market enum classes and add to `SPORT_MARKETS_MAPPING` in the same file
3. Add league URLs in `src/oddsharvester/utils/sport_league_constants.py`
4. Add period definitions in `src/oddsharvester/utils/period_constants.py`
5. Register markets in `src/oddsharvester/core/sport_market_registry.py` (create registration methods, add to `register_all_markets`)
6. Add tests

## Adding a New League

1. Find the league URL on oddsportal.com (e.g., `https://www.oddsportal.com/football/croatia/hnl/`)
2. Add an entry to the appropriate sport dictionary in `src/oddsharvester/utils/sport_league_constants.py`:
   ```python
   "league-slug": "https://www.oddsportal.com/{sport}/{country}/{league}/",
   ```
3. The slug should be lowercase with hyphens (e.g., `croatia-hnl`, `japan-j1-league`)

## Integration Tests — HAR Replay

Integration tests under `tests/integration/` run in **HAR replay mode by default** (deterministic, no network). The scraper is exercised against a recorded `<fixture-stem>.har` per JSON fixture instead of hitting `oddsportal.com` live. Two pytest hooks drive this:

- **`har_for_match` fixture** (`tests/integration/conftest.py`): returns the path to `<fixture-stem>.har` next to each JSON fixture, or `None` when the HAR is missing or `--live` is passed. Tests pass it as `har_path=` to `run_scraper`.
- **`PlaywrightManager`** reads `ODDSHARVESTER_HAR_REPLAY` (set by `run_scraper` from `har_path`) and wires `context.route_from_har(...)` with `not_found="abort"`. Symmetric env var `ODDSHARVESTER_HAR_RECORD` is used during capture.

**Run modes:**
- Default (`pytest tests/integration/ -m integration`) — replay only, `live_only` tests skipped.
- `--live` flag — bypasses HAR replay, runs every test against the real OddsPortal (slow, flaky on fixture drift, used for nightly health checks and capturing fresh fixtures).

**Capturing / refreshing fixtures:**
```bash
# Single match (writes both JSON output and the .har sibling)
uv run python -m tests.integration.helpers.capture --sport football --league premier-league \
    --match-url "https://..." --markets "1x2" --period "full_time" --bookies-filter "all" --capture-har

# Bulk re-capture every match dir under tests/integration/fixtures/
uv run python scripts/capture_all_hars.py
```
Recapture when scraper parsing changes, after a Playwright upgrade, or quarterly to refresh against current OddsPortal HTML.

**Known limitation — `live_only` tests:** OddsPortal H2H pages (basketball NBA, real-madrid-barcelona, djokovic-sinner) use URL fragments (`#match_id`) to select which match in an H2H series to render, plus cache-busted AJAX endpoints (`?<runtime-hash>`) to fetch match-specific data. HAR replay can't reproduce both: the fragment is preserved on `location.hash`, but JS computes a new cache-buster at runtime that doesn't match the recorded URL, so the page falls back to a different match in the series. These tests are marked `@pytest.mark.live_only` and skipped in default mode; run them with `--live` when validating against the live site. The 8 fixtures that *don't* trigger the H2H redirect chain (leicester-brentford, djokovic-lehecka, humbert-zverev) replay cleanly. See `tests/integration/helpers/capture.py:_alias_fragmented_redirect_targets` for the workaround that handles the redirect-with-fragment case.

## Code Style

- Python >=3.12, line length 120, double quotes
- Linter/formatter: Ruff (pre-commit hooks enforce this)
- `S101` (assert) and `T201` (print) are allowed

## Development Guidelines

### Testing Requirements

- **Before any code modification**: Run `uv run pytest tests/ -q` to ensure existing tests pass
- **After code changes**:
  - If modifying existing code: update related unit tests if behavior changes
  - If adding new code: create unit tests for new functions/classes
  - Run `uv run pytest tests/ -q` to validate all tests pass
- **Minimum coverage**: New code should have test coverage for critical paths
- **Test location**: Tests mirror the source structure in `tests/` directory

### Code Duplication (DRY Principle)

- **Constants**: Define constants (error patterns, config values, magic strings) in ONE canonical location and import them where needed. Never duplicate tuples/lists of values across files.
  - Error keywords/patterns → `src/oddsharvester/core/retry.py` (`TRANSIENT_ERROR_KEYWORDS`)
  - Sport/market constants → `src/oddsharvester/utils/sport_market_constants.py`
- **Shared logic**: If similar code appears in 2+ places, extract to a utility function. Examples:
  - Retry logic → `src/oddsharvester/core/retry.py`
  - Result handling → create shared helpers rather than copy-pasting
- **Before adding new constants/utilities**: Search the codebase (`grep`/`rg`) to check if similar functionality already exists

## Release Process

This project uses a tag-based release strategy. Publishing to PyPI is automated via GitHub Actions.

### Creating a new release

```bash
# 1. Ensure master is up to date and tests pass
git checkout master
git pull origin master
uv run pytest tests/ -q --ignore=tests/integration/

# 2. Update version in pyproject.toml
# version = "X.Y.Z"

# 3. Commit and tag
git add pyproject.toml
git commit -m "chore: release vX.Y.Z"
git tag vX.Y.Z
git push origin master --tags
```

The GitHub Actions workflow (`release.yml`) triggers automatically on tag push and:
1. Runs tests
2. Builds the package
3. Publishes to PyPI
4. Creates a GitHub Release

### Versioning (SemVer)

- **MAJOR** (`X.0.0`): Breaking changes
- **MINOR** (`0.X.0`): New backward-compatible features
- **PATCH** (`0.0.X`): Bug fixes
