# Links-only mode (`--links-only`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--links-only` flag to `historic` and `upcoming` that collects match links without scraping odds, emitting them through the normal storage layer (spec: `docs/specs/2026-07-16-links-only-mode-design.md`, GitHub issue #75).

**Architecture:** A `links_only: bool = False` parameter flows CLI → `run_scraper` → `scrape_historic`/`scrape_upcoming`, which early-return a `ScrapeResult` whose `success` rows are `{match_link, sport, league, season|date}` dicts built by one shared helper. Failed listing pages become `FailedUrl` entries so existing stderr reporting works unchanged. Storage, retry, multi-league merging: untouched.

**Tech Stack:** Python >=3.12, Click, Playwright (mocked in tests), pytest + pytest-asyncio, uv, Ruff.

## Global Constraints

- Branch: `feat/links-only-mode` (already created, off `master`). Never commit to `master`. Linear history.
- Line length 120, double quotes, Ruff formatting (`uv run ruff format .` before committing).
- Unit tests must pass before and after every task: `uv run pytest tests/ -q --ignore=tests/integration/`
- Commit messages: one line, conventional-commit style, no Co-Authored-By trailer.
- TDD: every code task starts with a failing test.
- Row shape (exact key order): historic `{"match_link", "sport", "league", "season"}`; upcoming `{"match_link", "sport", "league", "date"}`.

---

### Task 1: Order-stable dedup in `_collect_match_links`

**Files:**
- Modify: `src/oddsharvester/core/odds_portal_scraper.py:414`
- Test: `tests/core/test_odds_portal_scraper.py`

**Interfaces:**
- Consumes: existing `_collect_match_links(base_url, pages_to_scrape) -> LinkCollectionResult`
- Produces: `LinkCollectionResult.links` in first-seen listing order (later tasks rely on ordered links)

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_odds_portal_scraper.py`, after `test_collect_match_links_error_handling` (line ~478):

```python
@pytest.mark.asyncio
async def test_collect_match_links_preserves_listing_order(setup_scraper_mocks):
    """Dedup must keep first-seen listing order across pages (issue #75)."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    tab_mock = AsyncMock()
    mocks["context_mock"].new_page = AsyncMock(return_value=tab_mock)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)

    page1_links = [f"https://www.oddsportal.com/match{i}" for i in range(1, 6)]
    page2_links = ["https://www.oddsportal.com/match3", "https://www.oddsportal.com/match6"]
    scraper.extract_match_links = AsyncMock(side_effect=[page1_links, page2_links])

    result = await scraper._collect_match_links(base_url="https://base", pages_to_scrape=[1, 2])

    assert result.links == [*page1_links, "https://www.oddsportal.com/match6"]
    assert result.successful_pages == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_odds_portal_scraper.py::test_collect_match_links_preserves_listing_order -q`
Expected: FAIL on the order assertion (`set()` scrambles order; string-hash randomization makes a lucky pass extremely unlikely — if it passes, rerun to confirm the flake, the fix is still required).

- [ ] **Step 3: Write minimal implementation**

In `src/oddsharvester/core/odds_portal_scraper.py:414`, replace:

```python
        result.links = list(set(all_links))
```

with:

```python
        result.links = list(dict.fromkeys(all_links))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_odds_portal_scraper.py -q`
Expected: all PASS (including the two existing `_collect_match_links` tests).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/odds_portal_scraper.py tests/core/test_odds_portal_scraper.py
git commit -m "fix: preserve listing order when deduplicating collected match links"
```

---

### Task 2: `scrape_historic(links_only=True)` + shared result helper

**Files:**
- Modify: `src/oddsharvester/core/odds_portal_scraper.py` (imports line 9, `scrape_historic` lines 62-133, new private helper)
- Test: `tests/core/test_odds_portal_scraper.py`

**Interfaces:**
- Consumes: `LinkCollectionResult` (Task 1 ordering), `ScrapeResult`/`FailedUrl`/`ErrorType`/`ScrapeStats` from `core/scrape_result.py`
- Produces:
  - `scrape_historic(..., links_only: bool = False) -> ScrapeResult`
  - `_links_only_result(links: list[str], context: dict, failed_page_urls: list[str] | None = None) -> ScrapeResult` (reused by Task 3)

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_odds_portal_scraper.py`:

```python
@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_historic_links_only(url_builder_mock, setup_scraper_mocks):
    """links_only=True stops after link collection and returns link rows."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    base = "https://oddsportal.com/football/england/premier-league-2022-2023"
    url_builder_mock.get_historic_matches_url.return_value = base
    scraper._get_pagination_info = AsyncMock(return_value=[1, 2, 3])
    scraper._collect_match_links = AsyncMock(
        return_value=LinkCollectionResult(
            links=["https://oddsportal.com/match1", "https://oddsportal.com/match2"],
            successful_pages=2,
            failed_pages=[3],
        )
    )
    scraper.extract_match_odds = AsyncMock()
    scraper._prepare_page_for_scraping = AsyncMock()

    result = await scraper.scrape_historic(
        sport="football",
        league="england-premier-league",
        season="2022-2023",
        links_only=True,
    )

    scraper.extract_match_odds.assert_not_called()
    assert result.success == [
        {
            "match_link": "https://oddsportal.com/match1",
            "sport": "football",
            "league": "england-premier-league",
            "season": "2022-2023",
        },
        {
            "match_link": "https://oddsportal.com/match2",
            "sport": "football",
            "league": "england-premier-league",
            "season": "2022-2023",
        },
    ]
    assert [f.url for f in result.failed] == [f"{base}#/page/3"]
    assert result.stats.successful == 2
    assert result.stats.failed == 1
    assert result.stats.total_urls == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_odds_portal_scraper.py::test_scrape_historic_links_only -q`
Expected: FAIL with `TypeError: ... unexpected keyword argument 'links_only'`

- [ ] **Step 3: Write minimal implementation**

In `src/oddsharvester/core/odds_portal_scraper.py`:

3a. Extend the import on line 9:

```python
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats
```

3b. Add `links_only` to the `scrape_historic` signature (after `concurrent_scraping_task`):

```python
        concurrent_scraping_task: int = 3,
        links_only: bool = False,
    ) -> ScrapeResult:
```

and document it in the docstring Args:

```python
            links_only (bool): If True, stop after link collection and return the links (no odds scraping).
```

3c. Insert the early return between the link collection (after the `failed_pages` warning, line ~117) and the "Step 3: Extracting odds" block:

```python
        if links_only:
            self.logger.info(f"Links-only mode: returning {len(link_result.links)} match links without odds.")
            return self._links_only_result(
                links=link_result.links,
                context={"sport": sport, "league": league, "season": season},
                failed_page_urls=[f"{base_url}#/page/{p}" for p in link_result.failed_pages],
            )
```

3d. Add the helper next to `_prepare_page_for_scraping`:

```python
    def _links_only_result(
        self,
        links: list[str],
        context: dict,
        failed_page_urls: list[str] | None = None,
    ) -> ScrapeResult:
        """Builds a ScrapeResult carrying collected match links instead of odds data."""
        failed_page_urls = failed_page_urls or []
        success = [{"match_link": link, **context} for link in links]
        failed = [
            FailedUrl(
                url=url,
                error_type=ErrorType.NAVIGATION,
                error_message="Failed to collect links from listing page",
            )
            for url in failed_page_urls
        ]
        return ScrapeResult(
            success=success,
            failed=failed,
            stats=ScrapeStats(
                total_urls=len(success) + len(failed),
                successful=len(success),
                failed=len(failed),
            ),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_odds_portal_scraper.py -q`
Expected: all PASS (existing `test_scrape_historic` must still pass — default `links_only=False` keeps the odds path).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/odds_portal_scraper.py tests/core/test_odds_portal_scraper.py
git commit -m "feat: links_only early return in scrape_historic with link rows and failed-page urls"
```

---

### Task 3: `scrape_upcoming(links_only=True)`

**Files:**
- Modify: `src/oddsharvester/core/odds_portal_scraper.py` (`scrape_upcoming` lines 135-217)
- Test: `tests/core/test_odds_portal_scraper.py`

**Interfaces:**
- Consumes: `_links_only_result` from Task 2 (exact signature above)
- Produces: `scrape_upcoming(..., links_only: bool = False) -> ScrapeResult` with rows `{"match_link", "sport", "league", "date"}`

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_odds_portal_scraper.py`:

```python
@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_upcoming_links_only(url_builder_mock, setup_scraper_mocks):
    """links_only=True returns link rows with a date column; league may be None."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_upcoming_matches_url.return_value = "https://oddsportal.com/matches/football/20260720/"
    scraper.extract_match_links = AsyncMock(return_value=["https://oddsportal.com/m1"])
    scraper.extract_match_odds = AsyncMock()
    scraper._prepare_page_for_scraping = AsyncMock()

    result = await scraper.scrape_upcoming(sport="football", date="20260720", league=None, links_only=True)

    scraper.extract_match_odds.assert_not_called()
    assert result.success == [
        {"match_link": "https://oddsportal.com/m1", "sport": "football", "league": None, "date": "20260720"}
    ]
    assert result.failed == []
    assert result.stats.successful == 1
    assert result.stats.total_urls == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_odds_portal_scraper.py::test_scrape_upcoming_links_only -q`
Expected: FAIL with `TypeError: ... unexpected keyword argument 'links_only'`

- [ ] **Step 3: Write minimal implementation**

In `scrape_upcoming`:

3a. Add to the signature (after `include_started`):

```python
        include_started: bool = False,
        links_only: bool = False,
    ) -> ScrapeResult:
```

and to the docstring Args:

```python
            links_only (bool): If True, stop after link collection and return the links (no odds scraping).
```

3b. Insert the early return between the `if not match_links:` guard (line ~204) and the `return await self.extract_match_odds(...)`:

```python
        if links_only:
            self.logger.info(f"Links-only mode: returning {len(match_links)} match links without odds.")
            return self._links_only_result(
                links=match_links,
                context={"sport": sport, "league": league, "date": date},
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_odds_portal_scraper.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/odds_portal_scraper.py tests/core/test_odds_portal_scraper.py
git commit -m "feat: links_only early return in scrape_upcoming"
```

---

### Task 4: `run_scraper(links_only=...)` forwarding

**Files:**
- Modify: `src/oddsharvester/core/scraper_app.py` (signature line ~52, four call sites: lines ~158, ~173, ~200/~236, ~215)
- Test: `tests/core/test_scraper_app.py`

**Interfaces:**
- Consumes: `scrape_historic`/`scrape_upcoming` `links_only` kwarg (Tasks 2-3)
- Produces: `run_scraper(..., links_only: bool = False)` — the kwarg the CLI (Task 5) passes

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/test_scraper_app.py`, mirroring the patch stack of `test_run_scraper_upcoming_forwards_concurrency` (line ~244). Reuse this file's existing imports (`run_scraper`, `ScrapeResult`, `AsyncMock`, `patch`); add any of them that are missing.

```python
@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_forwards_links_only_historic(
    registrar_mock, proxy_mock, playwright_mock, extractor_mock, scraper_cls_mock
):
    scraper_mock = scraper_cls_mock.return_value
    scraper_mock.start_playwright = AsyncMock()
    scraper_mock.stop_playwright = AsyncMock()
    scraper_mock.scrape_historic = AsyncMock(return_value=ScrapeResult())

    await run_scraper(
        command="scrape_historic",
        sport="football",
        leagues=["england-premier-league"],
        season="2022-2023",
        links_only=True,
    )

    assert scraper_mock.scrape_historic.call_args.kwargs["links_only"] is True


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_forwards_links_only_historic_multi_league(
    registrar_mock, proxy_mock, playwright_mock, extractor_mock, scraper_cls_mock
):
    scraper_mock = scraper_cls_mock.return_value
    scraper_mock.start_playwright = AsyncMock()
    scraper_mock.stop_playwright = AsyncMock()
    scraper_mock.scrape_historic = AsyncMock(return_value=ScrapeResult())

    await run_scraper(
        command="scrape_historic",
        sport="football",
        leagues=["england-premier-league", "spain-laliga"],
        season="2022-2023",
        links_only=True,
    )

    assert scraper_mock.scrape_historic.call_count == 2
    assert all(c.kwargs["links_only"] is True for c in scraper_mock.scrape_historic.call_args_list)


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_forwards_links_only_upcoming(
    registrar_mock, proxy_mock, playwright_mock, extractor_mock, scraper_cls_mock
):
    scraper_mock = scraper_cls_mock.return_value
    scraper_mock.start_playwright = AsyncMock()
    scraper_mock.stop_playwright = AsyncMock()
    scraper_mock.scrape_upcoming = AsyncMock(return_value=ScrapeResult())

    await run_scraper(
        command="scrape_upcoming",
        sport="football",
        date="20991231",
        links_only=True,
    )

    assert scraper_mock.scrape_upcoming.call_args.kwargs["links_only"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_scraper_app.py -q -k links_only`
Expected: 3 FAIL with `TypeError: run_scraper() got an unexpected keyword argument 'links_only'`

- [ ] **Step 3: Write minimal implementation**

In `src/oddsharvester/core/scraper_app.py`:

3a. Add to the `run_scraper` signature (after `include_started`):

```python
    include_started: bool = False,
    links_only: bool = False,
) -> ScrapeResult | None:
```

3b. Add `links_only=links_only,` to the four scrape call sites (NOT to the `match_links` fast path, which the CLI blocks):

- `retry_scrape(scraper.scrape_historic, ...)` single-league (line ~158): after `concurrent_scraping_task=concurrency_tasks,`
- `_scrape_multiple_leagues(... scrape_func=scraper.scrape_historic ...)` (line ~173): after `concurrent_scraping_task=concurrency_tasks,`
- `retry_scrape(scraper.scrape_upcoming, ...)` single-league (line ~200) and no-league (line ~236): after `include_started=include_started,`
- `_scrape_multiple_leagues(... scrape_func=scraper.scrape_upcoming ...)` (line ~215): after `include_started=include_started,`

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_scraper_app.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/scraper_app.py tests/core/test_scraper_app.py
git commit -m "feat: forward links_only through run_scraper paths"
```

---

### Task 5: CLI flag, validation, and output message

**Files:**
- Modify: `src/oddsharvester/cli/options.py` (after the `--append` option, line ~112)
- Modify: `src/oddsharvester/cli/commands/historic.py`
- Modify: `src/oddsharvester/cli/commands/upcoming.py`
- Test: `tests/cli/test_click_cli.py`

**Interfaces:**
- Consumes: `run_scraper(links_only=...)` from Task 4
- Produces: `--links-only/--no-links-only` flag (kwarg `links_only`, envvar `OH_LINKS_ONLY`), `UsageError` on `--links-only` + `--match-link`, message `Collected N match links (M listing pages failed).`

- [ ] **Step 1: Write the failing tests**

Add to `tests/cli/test_click_cli.py` (module already imports `AsyncMock`, `patch`, `CliRunner`, `cli`; `FUTURE_DATE = "20991231"`):

```python
class TestLinksOnly:
    """Tests for the --links-only flag (issue #75)."""

    MATCH_URL = "https://www.oddsportal.com/football/england/premier-league/arsenal-chelsea-abc123/"

    def test_help_shows_links_only(self, runner):
        for command in ["historic", "upcoming"]:
            result = runner.invoke(cli, [command, "--help"])
            assert result.exit_code == 0
            assert "--links-only" in result.output

    def test_links_only_conflicts_with_match_link_historic(self, runner):
        result = runner.invoke(
            cli,
            ["historic", "-s", "football", "--season", "2024-2025", "--links-only", "--match-link", self.MATCH_URL],
        )
        assert result.exit_code != 0
        assert "--links-only cannot be combined with --match-link" in result.output

    def test_links_only_conflicts_with_match_link_upcoming(self, runner):
        result = runner.invoke(
            cli,
            ["upcoming", "-s", "football", "--links-only", "--match-link", self.MATCH_URL],
        )
        assert result.exit_code != 0
        assert "--links-only cannot be combined with --match-link" in result.output

    def _links_result(self):
        from oddsharvester.core.scrape_result import ScrapeResult, ScrapeStats

        return ScrapeResult(
            success=[
                {
                    "match_link": self.MATCH_URL,
                    "sport": "football",
                    "league": "england-premier-league",
                    "season": "2022-2023",
                }
            ],
            stats=ScrapeStats(total_urls=1, successful=1, failed=0),
        )

    def test_links_only_forwarded_and_message_historic(self, runner):
        with (
            patch(
                "oddsharvester.cli.commands.historic.run_scraper",
                new_callable=AsyncMock,
                return_value=self._links_result(),
            ) as scraper_mock,
            patch("oddsharvester.cli.commands.historic.store_data") as store_mock,
        ):
            result = runner.invoke(
                cli,
                ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2022-2023", "--links-only"],
            )
        assert result.exit_code == 0
        assert scraper_mock.call_args.kwargs["links_only"] is True
        assert "Collected 1 match links (0 listing pages failed)." in result.output
        store_mock.assert_called_once()

    def test_links_only_forwarded_and_message_upcoming(self, runner):
        with (
            patch(
                "oddsharvester.cli.commands.upcoming.run_scraper",
                new_callable=AsyncMock,
                return_value=self._links_result(),
            ) as scraper_mock,
            patch("oddsharvester.cli.commands.upcoming.store_data") as store_mock,
        ):
            result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "--links-only"])
        assert result.exit_code == 0
        assert scraper_mock.call_args.kwargs["links_only"] is True
        assert "Collected 1 match links (0 listing pages failed)." in result.output
        store_mock.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_click_cli.py::TestLinksOnly -q`
Expected: FAIL — `--help` lacks the flag, then `no such option: --links-only` for the others.

- [ ] **Step 3: Write minimal implementation**

3a. `src/oddsharvester/cli/options.py` — insert after the `--append/--no-append` option block (line ~112):

```python
    @click.option(
        "--links-only/--no-links-only",
        "links_only",
        default=False,
        envvar="OH_LINKS_ONLY",
        help="Collect match links only, without scraping odds. Market/odds options are ignored.",
    )
```

3b. `src/oddsharvester/cli/commands/historic.py` — at the top of the command body (before the `try:` block, after the `sport_value` line), add:

```python
    links_only = kwargs.get("links_only", False)
    if links_only and kwargs.get("match_links"):
        raise click.UsageError("--links-only cannot be combined with --match-link (links are already collected).")
```

Add `links_only=links_only,` to the `run_scraper(...)` call (after `concurrency_tasks=...`).

Replace the success `click.echo` with:

```python
            if links_only:
                click.echo(
                    f"Collected {scraped_data.stats.successful} match links "
                    f"({scraped_data.stats.failed} listing pages failed)."
                )
            else:
                click.echo(
                    f"Successfully scraped {scraped_data.stats.successful} matches "
                    f"({scraped_data.stats.failed} failed, {scraped_data.stats.success_rate:.1f}% success rate)."
                )
```

(The `Failed URLs: [...]` stderr echo stays as is — in links-only mode it lists the failed listing pages.)

3c. `src/oddsharvester/cli/commands/upcoming.py` — same three changes: the `UsageError` guard right after the existing date/league/match-link `UsageError` check, `links_only=links_only,` in the `run_scraper(...)` call (after `include_started=...`), and the same `if links_only:` echo branch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/ -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/cli/options.py src/oddsharvester/cli/commands/historic.py src/oddsharvester/cli/commands/upcoming.py tests/cli/test_click_cli.py
git commit -m "feat: add --links-only CLI flag with match-link conflict guard"
```

---

### Task 6: README documentation

**Files:**
- Modify: `README.md` (options table ~line 152, preview-only paragraph ~line 211, env vars table ~line 233)

**Interfaces:**
- Consumes: final CLI behavior from Task 5
- Produces: user-facing docs only (no code)

- [ ] **Step 1: Add the option row**

In the CLI Options Reference table, after the `--append` row (line ~152), add (match the surrounding column alignment):

```markdown
| `--links-only` |       | Collect match links only, without scraping odds (`--no-links-only` to opt out explicitly) | `--no-links-only` |
```

- [ ] **Step 2: Add the two-pass workflow section**

After the `--preview-only` explanation paragraph (line ~211), add:

````markdown
### Two-pass workflow: collect links, then scrape

For large runs it can be safer to collect all match links first, then scrape odds per link and re-run only the failures (see issue #75):

```bash
# Pass 1 - collect the season's match links (no odds scraped)
oddsharvester historic -s football -l england-premier-league --season 2022-2023 \
    --links-only -f csv -o links.csv

# Pass 2 - scrape odds per link (repeat --match-link; --append fills recovered failures)
oddsharvester historic -s football --season 2022-2023 -m 1x2 -f csv -o odds.csv --append \
    --match-link "https://www.oddsportal.com/football/england/premier-league-2022-2023/..."
```

Output rows contain `match_link`, `sport`, `league`, and `season` (`date` for `upcoming`), in the site's listing order. Options that only affect odds scraping (`--market`, `--period`, `--odds-history`, `--preview-only`, `--target-bookmaker`, `--bookies-filter`) are ignored when `--links-only` is set. `--links-only` cannot be combined with `--match-link`.
````

- [ ] **Step 3: Add the environment variable row**

In the Environment Variables table (line ~233), after the `OH_APPEND` row, add (match the column alignment):

```markdown
| `OH_LINKS_ONLY`    | `--links-only`    | Collect match links only, without scraping odds |
```

- [ ] **Step 4: Verify rendering and commit**

Run: `uv run pytest tests/ -q --ignore=tests/integration/` (unchanged code, must stay green)

```bash
git add README.md
git commit -m "docs: document --links-only two-pass workflow"
```

---

### Task 7: Final verification

**Files:**
- No new changes (verification only; fix anything found)

- [ ] **Step 1: Full unit suite**

Run: `uv run pytest tests/ -q --ignore=tests/integration/`
Expected: all PASS.

- [ ] **Step 2: Integration replay suite (regression check)**

Run: `uv run pytest tests/integration/ -q -m integration`
Expected: all PASS (links-only touches no parsing; HAR replay must be unaffected).

- [ ] **Step 3: Lint / format**

Run: `uv run ruff format . && uv run ruff check --fix src/`
Expected: no diffs, no errors. If formatting changed files, re-run the unit suite, then:

```bash
git add -u
git commit -m "style: ruff formatting"
```

- [ ] **Step 4: Manual smoke test (optional, needs network)**

Run: `uv run oddsharvester historic -s football -l england-premier-league --season 2022-2023 --links-only --max-pages 1 -f csv -o /tmp/links-smoke.csv --headless`
Expected: `Collected N match links (0 listing pages failed).` and a CSV with `match_link,sport,league,season` header, ~50 rows, listing order.
