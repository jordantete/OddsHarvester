# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OddsHarvester is a Python web scraper that extracts sports betting odds from oddsportal.com. It uses Playwright for browser automation and BeautifulSoup/lxml for HTML parsing. Supports multiple sports (football, tennis, basketball, rugby, ice hockey, baseball, American football), various betting markets, and stores output locally (JSON/CSV) or remotely (AWS S3).

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

# Run integration tests (requires internet, slower)
uv run pytest tests/integration/ -q -m integration

# Run a single test file
uv run pytest tests/core/test_url_builder.py -q

# Run a specific test
uv run pytest tests/core/test_url_builder.py::TestUrlBuilder::test_method_name -q

# Coverage report
uv run pytest --cov=src/oddsharvester --cov-report=term --ignore=tests/integration/

# Lint and format
uv run ruff format .
uv run ruff check --fix src/
```

## Architecture

Four-layer architecture:

```
CLI Layer (src/oddsharvester/cli/) → Core Layer (src/oddsharvester/core/) → Data Layer (src/oddsharvester/utils/) → Storage Layer (src/oddsharvester/storage/)
```

**Entry points**: `oddsharvester` CLI command (or `python -m oddsharvester`), `src/oddsharvester/lambda_handler.py` (AWS Lambda)

**Core Layer** (`src/oddsharvester/core/`):

- `scraper_app.py` — Top-level orchestrator; initializes browser, scraper, and storage
- `odds_portal_scraper.py` — Navigates pages, extracts match links, coordinates per-match scraping
- `playwright_manager.py` — Browser lifecycle (launch, context, page creation)
- `browser_helper.py` — Page interactions (cookies, scrolling, waiting)
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
