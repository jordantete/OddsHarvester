# Seasons List (`--season` comma list) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `--season` accept a comma-separated list on `historic`, scraped as the cartesian product with the existing `--league` list, with a per-combo summary at end of run.

**Architecture:** The existing multi-league fan-out helper in `scraper_app.py` is generalized from a list of leagues to a list of `(league, season)` pairs, iterated sequentially with the league outer. Season stays a per-combo value passed down to `scrape_historic`; the season column on output rows is stamped in `scrape_historic` after odds extraction, because the per-match extraction in `base_scraper.py` has no knowledge of which season it belongs to.

**Tech Stack:** Python >=3.12, Click (CLI), pytest + pytest-asyncio, uv (package manager), Ruff (lint/format).

**Spec:** `docs/specs/2026-07-20-seasons-list-design.md`

## Global Constraints

- Python >=3.12, line length 120, double quotes, Ruff enforced by pre-commit.
- Branch is `feat/seasons-list`, already created off `master`. Never commit to `master`. Never push.
- Commit messages are one line, no `Co-Authored-By` trailer. End each commit message with the session trailer used across this repo's history: `Claude-Session: https://claude.ai/code/session_0115LwmW9Y96q8E1QeLGxwJa` (blank line before it).
- `uv run pytest tests/ -q --ignore=tests/integration/` must pass at the end of every task.
- Run scraper commands with `uv run oddsharvester ...`, tests with `uv run pytest ...`.
- Constants live in one place. Before adding any constant, `rg` for it first.
- `--season` exists only on `historic`. `upcoming` has no season concept and its scraper method has no `season` parameter.

---

### Task 1: `validate_seasons` validator

Pure function, no CLI wiring yet. The existing `validate_season` body is extracted unchanged into a private single-token helper so error messages stay byte-identical.

**Files:**
- Modify: `src/oddsharvester/cli/validators.py:31-53`
- Test: `tests/cli/test_validators_seasons.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `validate_seasons(ctx, param, value: list[str] | None) -> list[str] | None` — a Click callback returning the validated seasons in input order with duplicates removed. Raises `click.BadParameter` on the first invalid token. Also produces `_validate_one_season(value: str) -> str` (private, used only inside this module).

- [ ] **Step 1: Write the failing test**

Create `tests/cli/test_validators_seasons.py`:

```python
import click
import pytest

from oddsharvester.cli.validators import validate_seasons


def test_accepts_list_of_valid_seasons():
    assert validate_seasons(None, None, ["2020", "2021-2022"]) == ["2020", "2021-2022"]


def test_preserves_input_order():
    assert validate_seasons(None, None, ["2022-2023", "2020-2021"]) == ["2022-2023", "2020-2021"]


def test_deduplicates_preserving_first_seen_order():
    assert validate_seasons(None, None, ["2020", "2021", "2020"]) == ["2020", "2021"]


def test_accepts_current_mixed_with_explicit_seasons():
    assert validate_seasons(None, None, ["2021-2022", "current"]) == ["2021-2022", "current"]


def test_accepts_single_season():
    assert validate_seasons(None, None, ["2022-2023"]) == ["2022-2023"]


def test_returns_none_for_empty_value():
    assert validate_seasons(None, None, None) is None
    assert validate_seasons(None, None, []) is None


def test_rejects_invalid_format_with_existing_message():
    with pytest.raises(click.BadParameter, match="Invalid season format"):
        validate_seasons(None, None, ["2020", "invalid"])


def test_rejects_non_consecutive_range_with_existing_message():
    with pytest.raises(click.BadParameter, match="Second year must be exactly one year after the first"):
        validate_seasons(None, None, ["2020-2025"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_validators_seasons.py -q`
Expected: FAIL, `ImportError: cannot import name 'validate_seasons'`

- [ ] **Step 3: Write minimal implementation**

In `src/oddsharvester/cli/validators.py`, replace the whole `validate_season` function (lines 31-53) with:

```python
def _validate_one_season(value: str) -> str:
    """Validate a single season token (YYYY, YYYY-YYYY, or 'current')."""
    if value.lower() == "current":
        return value

    single_year = re.compile(r"^\d{4}$")
    range_pattern = re.compile(r"^\d{4}-\d{4}$")

    if single_year.match(value):
        return value

    if range_pattern.match(value):
        start_year, end_year = map(int, value.split("-"))
        if end_year != start_year + 1:
            raise click.BadParameter(
                f"Invalid season range '{value}'. Second year must be exactly one year after the first."
            )
        return value

    raise click.BadParameter(f"Invalid season format '{value}'. Expected YYYY, YYYY-YYYY, or 'current'.")


def validate_seasons(ctx, param, value):
    """Validate a list of seasons, preserving order and dropping duplicates."""
    if not value:
        return None

    seen: dict[str, None] = {}
    for item in value:
        seen[_validate_one_season(item)] = None
    return list(seen)
```

Keep `validate_season` (singular) as a thin wrapper so the tree stays green at
every commit. Its only importer is `cli/commands/historic.py:10`, which Task 3
updates; Task 3 also deletes this wrapper.

```python
def validate_season(ctx, param, value):
    """Deprecated, superseded by validate_seasons. Removed once historic.py migrates."""
    return _validate_one_season(value) if value else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_validators_seasons.py -q`
Expected: PASS, 8 passed

Then confirm nothing else broke: `uv run pytest tests/ -q --ignore=tests/integration/`
Expected: PASS (the `validate_season` wrapper keeps `historic.py` importable).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/cli/validators.py tests/cli/test_validators_seasons.py
git commit -m "$(cat <<'EOF'
feat: add validate_seasons for comma-separated season lists

Claude-Session: https://claude.ai/code/session_0115LwmW9Y96q8E1QeLGxwJa
EOF
)"
```

---

### Task 2: `combo_stats` on `ScrapeResult`

A per-combo breakdown carried from the core layer to the CLI layer, so the CLI can render the summary table without reaching into core internals.

**Files:**
- Modify: `src/oddsharvester/core/scrape_result.py:96-117`
- Test: `tests/core/test_scrape_result.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ScrapeResult.combo_stats: list[dict[str, Any]]`, default empty. Each entry has exactly these keys: `league: str`, `season: str | None`, `successful: int`, `failed: int`, `errored: bool`. `merge()` deliberately does NOT touch it, so only the combo helper in Task 3 writes it.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_scrape_result.py`:

```python
def test_combo_stats_defaults_to_empty_list():
    result = ScrapeResult()
    assert result.combo_stats == []


def test_combo_stats_included_in_to_dict():
    result = ScrapeResult()
    result.combo_stats.append(
        {"league": "england-premier-league", "season": "2021-2022", "successful": 380, "failed": 0, "errored": False}
    )
    assert result.to_dict()["combo_stats"] == [
        {"league": "england-premier-league", "season": "2021-2022", "successful": 380, "failed": 0, "errored": False}
    ]


def test_merge_does_not_propagate_combo_stats():
    """Only the combo helper writes combo_stats; merging per-combo results must not duplicate entries."""
    target = ScrapeResult()
    other = ScrapeResult()
    other.combo_stats.append(
        {"league": "spain-laliga", "season": "2020", "successful": 1, "failed": 0, "errored": False}
    )
    target.merge(other)
    assert target.combo_stats == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_scrape_result.py -q -k combo_stats`
Expected: FAIL, `AttributeError: 'ScrapeResult' object has no attribute 'combo_stats'`

- [ ] **Step 3: Write minimal implementation**

In `src/oddsharvester/core/scrape_result.py`, add the field to `ScrapeResult` (after `stats`, line 108):

```python
    stats: ScrapeStats = field(default_factory=ScrapeStats)
    combo_stats: list[dict[str, Any]] = field(default_factory=list)
```

And add it to `to_dict` (after the `stats` key, line 116):

```python
            "stats": self.stats.to_dict(),
            "combo_stats": self.combo_stats,
```

Leave `merge()` untouched.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_scrape_result.py -q`
Expected: PASS, all tests in the file

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/scrape_result.py tests/core/test_scrape_result.py
git commit -m "$(cat <<'EOF'
feat: carry per-combo breakdown on ScrapeResult

Claude-Session: https://claude.ai/code/session_0115LwmW9Y96q8E1QeLGxwJa
EOF
)"
```

---

### Task 3: Seasons plumbing end to end

The signature change spans CLI and core atomically, so it is one task. Splitting it would leave the tree broken between commits.

**The trap:** `scrape_upcoming` has **no** `season` parameter (`odds_portal_scraper.py`, signature ends at `links_only`). The shared helper must inject `season` into the call kwargs only when it actually has one, otherwise the `upcoming` path raises `TypeError: scrape_upcoming() got an unexpected keyword argument 'season'`.

**Files:**
- Modify: `src/oddsharvester/cli/commands/historic.py:10,20-25,39,57`
- Modify: `src/oddsharvester/cli/commands/upcoming.py:67`
- Modify: `src/oddsharvester/core/scraper_app.py:34,70,153-193,223-239,274-328`
- Test: `tests/core/test_scraper_app.py` (existing `_scrape_multiple_leagues` tests need renaming)
- Test: `tests/cli/test_click_cli.py`

**Interfaces:**
- Consumes: `validate_seasons` (Task 1), `ScrapeResult.combo_stats` (Task 2).
- Produces:
  - `run_scraper(..., seasons: list[str] | None = None, ...)` — replaces the `season: str | None = None` parameter.
  - `_scrape_league_season_combos(scraper, scrape_func, leagues: list[str], sport: str, seasons: list[str] | None = None, **kwargs) -> ScrapeResult` — replaces `_scrape_multiple_leagues`. With `seasons=None` it runs one pass per league and passes no `season` kwarg at all.

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_scraper_app.py` (the file already imports `ScrapeResult`, `ScrapeStats`, `AsyncMock`, `MagicMock`, `patch`, `pytest`; add `_scrape_league_season_combos` to the existing import from `oddsharvester.core.scraper_app`):

```python
@pytest.mark.asyncio
async def test_combos_iterate_league_outer_season_inner():
    """Output must be grouped by league, then by season, deterministically."""
    scraper_mock = MagicMock()
    scrape_func_mock = AsyncMock()
    scrape_func_mock.return_value = ScrapeResult(success=[{"m": "x"}], stats=ScrapeStats(total_urls=1, successful=1))

    with patch("oddsharvester.core.scraper_app.retry_scrape", scrape_func_mock):
        await _scrape_league_season_combos(
            scraper=scraper_mock,
            scrape_func=scrape_func_mock,
            leagues=["epl", "laliga"],
            sport="football",
            seasons=["2020-2021", "2021-2022"],
        )

    ordered = [(c.kwargs["league"], c.kwargs["season"]) for c in scrape_func_mock.call_args_list]
    assert ordered == [
        ("epl", "2020-2021"),
        ("epl", "2021-2022"),
        ("laliga", "2020-2021"),
        ("laliga", "2021-2022"),
    ]


@pytest.mark.asyncio
async def test_no_seasons_passes_no_season_kwarg():
    """The upcoming path shares this helper and scrape_upcoming has no season parameter."""
    scraper_mock = MagicMock()
    scrape_func_mock = AsyncMock()
    scrape_func_mock.return_value = ScrapeResult(success=[{"m": "x"}], stats=ScrapeStats(total_urls=1, successful=1))

    with patch("oddsharvester.core.scraper_app.retry_scrape", scrape_func_mock):
        await _scrape_league_season_combos(
            scraper=scraper_mock,
            scrape_func=scrape_func_mock,
            leagues=["epl", "laliga"],
            sport="football",
            seasons=None,
        )

    assert len(scrape_func_mock.call_args_list) == 2
    for call in scrape_func_mock.call_args_list:
        assert "season" not in call.kwargs


@pytest.mark.asyncio
async def test_combo_stats_records_zero_link_combo():
    """A combo returning nothing is recorded with a zero count, not as an error."""
    scraper_mock = MagicMock()
    scrape_func_mock = AsyncMock()
    scrape_func_mock.side_effect = [
        ScrapeResult(success=[{"m": "x"}], stats=ScrapeStats(total_urls=1, successful=1)),
        ScrapeResult(success=[], stats=ScrapeStats(total_urls=0, successful=0)),
    ]

    with patch("oddsharvester.core.scraper_app.retry_scrape", scrape_func_mock):
        result = await _scrape_league_season_combos(
            scraper=scraper_mock,
            scrape_func=scrape_func_mock,
            leagues=["russia-premier-league"],
            sport="football",
            seasons=["2011-2012", "2011"],
        )

    assert result.combo_stats == [
        {"league": "russia-premier-league", "season": "2011-2012", "successful": 1, "failed": 0, "errored": False},
        {"league": "russia-premier-league", "season": "2011", "successful": 0, "failed": 0, "errored": False},
    ]


@pytest.mark.asyncio
async def test_combo_stats_distinguishes_errored_from_empty():
    """An errored combo is worth re-running; an empty one usually is not."""
    scraper_mock = MagicMock()
    scrape_func_mock = AsyncMock()
    scrape_func_mock.side_effect = [
        ScrapeResult(success=[], stats=ScrapeStats(total_urls=0, successful=0)),
        Exception("Network error"),
    ]

    with patch("oddsharvester.core.scraper_app.retry_scrape", scrape_func_mock):
        result = await _scrape_league_season_combos(
            scraper=scraper_mock,
            scrape_func=scrape_func_mock,
            leagues=["epl"],
            sport="football",
            seasons=["2020", "2021"],
        )

    assert [c["errored"] for c in result.combo_stats] == [False, True]
    assert result.stats.successful == 0


async def test_single_league_single_season_skips_the_combo_helper():
    """One league and one season must keep the direct single-call path (no behaviour drift)."""
    scraper_mock = MagicMock()
    scraper_mock.scrape_historic = AsyncMock(return_value=ScrapeResult())
    scraper_mock.start_playwright = AsyncMock()
    scraper_mock.stop_playwright = AsyncMock()

    with (
        patch("oddsharvester.core.scraper_app.OddsPortalScraper", return_value=scraper_mock),
        patch("oddsharvester.core.scraper_app._scrape_league_season_combos") as combos_mock,
    ):
        await run_scraper(
            command="scrape_historic",
            sport="football",
            leagues=["england-premier-league"],
            seasons=["2024"],
        )

    assert not combos_mock.called
```

Match the surrounding tests' construction of `run_scraper` and its scraper patching; the file already exercises `run_scraper` several times, so reuse whatever fixture or patch target those tests use rather than the sketch above. The assertion that matters is `not combos_mock.called`.

Note: `asyncio_mode = "auto"` is set in `pyproject.toml`, so `@pytest.mark.asyncio` is optional. The existing file uses it inconsistently; follow whichever style the neighbouring tests use.

Append to `tests/cli/test_click_cli.py`, inside the same class as `test_historic_concurrency_flag_forwarded_to_run_scraper`:

```python
    def test_historic_single_season_forwarded_as_list(self, runner, mock_run_scraper):
        """Backward compatibility: a single --season value still works, now as a one-element list."""
        runner.invoke(cli, ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2024"])
        assert mock_run_scraper["historic"].call_args.kwargs["seasons"] == ["2024"]

    def test_historic_season_list_forwarded(self, runner, mock_run_scraper):
        """--season accepts a comma-separated list (issue #78)."""
        runner.invoke(
            cli,
            ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2021-2022,2022-2023"],
        )
        assert mock_run_scraper["historic"].call_args.kwargs["seasons"] == ["2021-2022", "2022-2023"]

    def test_historic_season_list_deduplicated(self, runner, mock_run_scraper):
        runner.invoke(cli, ["historic", "-s", "football", "--season", "2024,2024,2023"])
        assert mock_run_scraper["historic"].call_args.kwargs["seasons"] == ["2024", "2023"]

    def test_historic_season_list_rejects_invalid_element(self, runner, mock_run_scraper):
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024,invalid"])
        assert result.exit_code != 0
        assert "Invalid season format" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_scraper_app.py tests/cli/test_click_cli.py -q`
Expected: FAIL. Collection errors on `ImportError: cannot import name 'validate_season'` (broken by Task 1) and `cannot import name '_scrape_league_season_combos'`.

- [ ] **Step 3: Replace the fan-out helper**

In `src/oddsharvester/core/scraper_app.py`, replace `_scrape_multiple_leagues` (lines 274-328) entirely with:

```python
async def _scrape_league_season_combos(
    scraper,
    scrape_func,
    leagues: list[str],
    sport: str,
    seasons: list[str] | None = None,
    **kwargs,
) -> ScrapeResult:
    """
    Scrape every (league, season) combination sequentially, league outer.

    `seasons=None` degenerates to one pass per league with no `season` kwarg,
    which is the upcoming-matches behaviour (`scrape_upcoming` has no such parameter).

    Args:
        scraper: The scraper instance
        scrape_func: scrape_historic or scrape_upcoming
        leagues: Leagues to scrape
        sport: The sport being scraped
        seasons: Seasons to scrape per league, or None for a seasonless run
        **kwargs: Additional arguments forwarded to the scrape function

    Returns:
        ScrapeResult: Merged results, with a per-combo breakdown in `combo_stats`.
    """
    combined_result = ScrapeResult()
    combos = [(league, season) for league in leagues for season in (seasons or [None])]

    logger.info(f"Starting scraping for {len(combos)} league/season combo(s)")

    for i, (league, season) in enumerate(combos, 1):
        label = f"{league} {season}" if season is not None else league
        combo_kwargs = {**kwargs, "season": season} if season is not None else kwargs

        try:
            logger.info(f"[{i}/{len(combos)}] Processing: {label}")

            combo_result = await retry_scrape(scrape_func, sport=sport, league=league, **combo_kwargs)

            if combo_result is None:
                logger.warning(f"No data returned for {label}")
                combined_result.combo_stats.append(
                    {"league": league, "season": season, "successful": 0, "failed": 0, "errored": True}
                )
                continue

            combined_result.merge(combo_result)
            combined_result.combo_stats.append(
                {
                    "league": league,
                    "season": season,
                    "successful": combo_result.stats.successful,
                    "failed": combo_result.stats.failed,
                    "errored": False,
                }
            )

            if combo_result.success:
                logger.info(
                    f"Successfully scraped {combo_result.stats.successful} matches from {label} "
                    f"({combo_result.stats.failed} failed)"
                )
            else:
                logger.warning(f"No successful matches for {label} ({combo_result.stats.failed} failed)")

        except Exception as e:
            logger.error(f"Failed to scrape {label}: {e}")
            combined_result.combo_stats.append(
                {"league": league, "season": season, "successful": 0, "failed": 0, "errored": True}
            )
            continue

    errored = [c for c in combined_result.combo_stats if c["errored"]]
    if errored:
        logger.warning(f"Failed to scrape {len(errored)} combo(s)")

    logger.info(
        f"Scraping completed: {len(combos) - len(errored)}/{len(combos)} combos successful, "
        f"{combined_result.stats.successful} total matches scraped, "
        f"{combined_result.stats.failed} failed ({combined_result.stats.success_rate:.1f}% success rate)"
    )

    return combined_result
```

- [ ] **Step 4: Update `run_scraper`**

In `src/oddsharvester/core/scraper_app.py`:

Line 34, change the parameter:

```python
    seasons: list[str] | None = None,
```

Line 70, change the log line to use it:

```python
        f"sport={sport}, date={date}, leagues={leagues}, seasons={seasons}, markets={markets}, "
```

Lines 153-193, replace the historic branch body:

```python
            printable_seasons = ", ".join(seasons) if seasons else "current"
            logger.info(
                "\n                Scraping historical odds for "
                f"sport={sport}, leagues={leagues}, seasons={printable_seasons}, "
                f"markets={markets}, scrape_odds_history={scrape_odds_history}, "
                f"target_bookmaker={target_bookmaker}, max_pages={max_pages}\n            "
            )

            if len(leagues) == 1 and len(seasons or [None]) == 1:
                return await retry_scrape(
                    scraper.scrape_historic,
                    sport=sport,
                    league=leagues[0],
                    season=seasons[0] if seasons else None,
                    markets=markets,
                    scrape_odds_history=scrape_odds_history,
                    target_bookmaker=target_bookmaker,
                    max_pages=max_pages,
                    bookies_filter=bookies_filter_enum,
                    period=period_enum,
                    request_delay=request_delay,
                    concurrent_scraping_task=concurrency_tasks,
                    links_only=links_only,
                )
            else:
                return await _scrape_league_season_combos(
                    scraper=scraper,
                    scrape_func=scraper.scrape_historic,
                    leagues=leagues,
                    seasons=seasons,
                    sport=sport,
                    markets=markets,
                    scrape_odds_history=scrape_odds_history,
                    target_bookmaker=target_bookmaker,
                    max_pages=max_pages,
                    bookies_filter=bookies_filter_enum,
                    period=period_enum,
                    request_delay=request_delay,
                    concurrent_scraping_task=concurrency_tasks,
                    links_only=links_only,
                )
```

Note the `season=` kwarg is gone from the combo call: the helper supplies it per combo.

Lines 223-239, in the upcoming branch, rename the call only (no `seasons` kwarg, so it degenerates):

```python
                    return await _scrape_league_season_combos(
                        scraper=scraper,
                        scrape_func=scraper.scrape_upcoming,
                        leagues=leagues,
                        sport=sport,
                        date=date,
                        markets=markets,
                        scrape_odds_history=scrape_odds_history,
                        target_bookmaker=target_bookmaker,
                        bookies_filter=bookies_filter_enum,
                        period=period_enum,
                        request_delay=request_delay,
                        concurrent_scraping_task=concurrency_tasks,
                        include_started=include_started,
                        kickoff_within_hours=kickoff_within_hours,
                        links_only=links_only,
                    )
```

- [ ] **Step 5: Update the CLI call sites**

In `src/oddsharvester/cli/validators.py`, delete the `validate_season` wrapper
that Task 1 left behind. Nothing imports it after this step.

In `src/oddsharvester/cli/commands/historic.py`:

Line 10, fix the import:

```python
from oddsharvester.cli.validators import validate_max_pages, validate_seasons
```

Lines 20-25, the option:

```python
@click.option(
    "--season",
    "seasons",
    required=True,
    type=COMMA_LIST,
    callback=validate_seasons,
    help="Comma-separated seasons to scrape (YYYY, YYYY-YYYY, or 'current').",
)
```

Add `COMMA_LIST` to the imports at the top of the file:

```python
from oddsharvester.cli.types import COMMA_LIST
```

Line 39, the local:

```python
    seasons = kwargs.get("seasons")
```

Line 57, the forward:

```python
                seasons=seasons,
```

In `src/oddsharvester/cli/commands/upcoming.py` line 67, rename the argument:

```python
                seasons=None,
```

- [ ] **Step 6: Update the existing helper tests**

In `tests/core/test_scraper_app.py`, the existing tests call the old name with a `season="2023"` kwarg that used to flow through `**kwargs`. Update every occurrence:

- Rename `_scrape_multiple_leagues` to `_scrape_league_season_combos` in the import and in all call sites (12 references).
- Rename `test_scrape_multiple_leagues_*` test functions to `test_scrape_league_season_combos_*`.
- Change every `season="2023"` argument in those calls to `seasons=["2023"]`.

Run `rg -n "_scrape_multiple_leagues|season=\"2023\"" tests/` to confirm none remain.

- [ ] **Step 7: Run the full suite**

Run: `uv run pytest tests/ -q --ignore=tests/integration/`
Expected: PASS, no failures. This is the first point since Task 1 where the tree is consistent.

- [ ] **Step 8: Verify the upcoming path really has no season kwarg**

Run: `uv run pytest tests/core/test_scraper_app.py -q -k "upcoming or no_season"`
Expected: PASS. If any test raises `TypeError: ... unexpected keyword argument 'season'`, the conditional in `combo_kwargs` is wrong.

- [ ] **Step 9: Commit**

```bash
git add src/oddsharvester/cli/commands/historic.py src/oddsharvester/cli/commands/upcoming.py \
        src/oddsharvester/core/scraper_app.py tests/core/test_scraper_app.py tests/cli/test_click_cli.py
git commit -m "$(cat <<'EOF'
feat: scrape the cartesian product of leagues and seasons (issue #78)

Claude-Session: https://claude.ai/code/session_0115LwmW9Y96q8E1QeLGxwJa
EOF
)"
```

---

### Task 4: `season` column on output rows

**This is the breaking change.** A column is inserted mid-row, so `--append` onto a file produced by an earlier version yields a heterogeneous file.

The per-match extraction in `base_scraper.py` does not know its season, so the column is declared there with a `None` default (giving every command a stable schema at a stable position) and stamped in `scrape_historic`, which does know.

**Files:**
- Modify: `src/oddsharvester/core/base_scraper.py:1066-1084`
- Modify: `src/oddsharvester/core/odds_portal_scraper.py:132-140`
- Test: `tests/core/test_odds_portal_scraper.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: every row emitted by `extract_match_odds` has a `season` key, positioned directly after `match_date`. `scrape_historic` overwrites it with its combo's season; `scrape_upcoming` and the `--match-link` path leave it `None`.

- [ ] **Step 1: Write the failing test**

Two tests at two levels: the column must *exist* for every command (declared in
`base_scraper`), and it must be *filled* for historic (stamped in
`scrape_historic`).

Append to `tests/core/test_odds_portal_scraper.py`, following the exact fixture
pattern of `test_scrape_historic_forwards_concurrent_scraping_task`:

```python
async def test_scrape_historic_stamps_season_on_rows(url_builder_mock, setup_scraper_mocks):
    """Historic rows carry the season of their combo (issue #78)."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_historic_matches_url.return_value = "https://oddsportal.com/football/england/premier-league"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper._get_pagination_info = AsyncMock(return_value=[1])
    scraper._collect_match_links = AsyncMock(
        return_value=LinkCollectionResult(links=["https://oddsportal.com/m1"], successful_pages=1, failed_pages=[])
    )
    scraper.extract_match_odds = AsyncMock(
        return_value=ScrapeResult(
            success=[{"match_date": "2022-04-09 14:00:00 UTC", "season": None}],
            stats=ScrapeStats(total_urls=1, successful=1),
        )
    )

    result = await scraper.scrape_historic(sport="football", league="premier-league", season="2021-2022")

    assert result.success[0]["season"] == "2021-2022"
```

Append to `tests/core/test_base_scraper.py`, following the exact fixture pattern
of `test_extract_match_details_extracts_match_info`:

```python
async def test_extract_match_details_declares_null_season(setup_base_scraper_mocks):
    """Every row carries a season column; commands with no season leave it null (issue #78)."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    json_blob = '{"eventBody": {"startDate": 1681753200}, "eventData": {"home": "Arsenal", "away": "Chelsea"}}'
    page_mock.content = AsyncMock(
        return_value=f"<html><body><div id=\"react-event-header\" data='{json_blob}'></div></body></html>"
    )

    result = await scraper._extract_match_details_event_header(
        page=page_mock,
        match_link="https://www.oddsportal.com/football/england/arsenal-chelsea-123456",
    )

    assert "season" in result
    assert result["season"] is None
```

`LinkCollectionResult`, `ScrapeResult`, `ScrapeStats` and `AsyncMock` are already
imported at the top of `test_odds_portal_scraper.py`. `asyncio_mode = "auto"` is
set in `pyproject.toml`, so no decorator is required.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_odds_portal_scraper.py tests/core/test_base_scraper.py -q -k season`
Expected: both FAIL. `test_scrape_historic_stamps_season_on_rows` with `assert None == '2021-2022'`, and `test_extract_match_details_declares_null_season` with `assert 'season' in result`.

- [ ] **Step 3: Declare the column at the source**

In `src/oddsharvester/core/base_scraper.py`, in the `details` literal (line 1066), insert the key directly after `match_date`:

```python
            details = {
                "scraped_date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S %Z"),
                "match_date": match_date,
                "season": None,
                "match_link": match_link,
```

- [ ] **Step 4: Stamp the season where it is known**

In `src/oddsharvester/core/odds_portal_scraper.py`, replace the `return await self.extract_match_odds(...)` at the end of `scrape_historic` (line 132) with:

```python
        result = await self.extract_match_odds(
            sport=sport,
            match_links=link_result.links,
            markets=markets,
            scrape_odds_history=scrape_odds_history,
            target_bookmaker=target_bookmaker,
            concurrent_scraping_task=concurrent_scraping_task,
            preview_submarkets_only=self.preview_submarkets_only,
            bookies_filter=bookies_filter,
            period=period,
            request_delay=request_delay,
        )

        for row in result.success:
            row["season"] = season

        return result
```

Keep the existing keyword arguments exactly as they were; only the assignment, the loop, and the return are new.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_odds_portal_scraper.py tests/core/test_base_scraper.py -q`
Expected: PASS. If `test_base_scraper.py` has assertions comparing whole `details` dicts, they will fail on the new key. Update those expected dicts to include `"season": None` at the correct position.

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest tests/ -q --ignore=tests/integration/`
Expected: PASS

- [ ] **Step 7: Run the integration replay as the backward-compatibility guard**

Run: `uv run pytest tests/integration/ -q -m integration`
Expected: PASS. These replay real captured HAR fixtures, so they are the honest check that a single-season historic run still behaves. If a fixture comparison fails only on the new `season` key, update the fixture's expected JSON.

- [ ] **Step 8: Commit**

```bash
git add src/oddsharvester/core/base_scraper.py src/oddsharvester/core/odds_portal_scraper.py tests/
git commit -m "$(cat <<'EOF'
feat!: add season column to every output row

Claude-Session: https://claude.ai/code/session_0115LwmW9Y96q8E1QeLGxwJa
EOF
)"
```

---

### Task 5: Per-combo summary table

**Files:**
- Modify: `src/oddsharvester/cli/commands/historic.py:88-99`
- Test: `tests/cli/test_click_cli.py`

**Interfaces:**
- Consumes: `ScrapeResult.combo_stats` (Task 2), populated by `_scrape_league_season_combos` (Task 3).
- Produces: `_format_combo_summary(combo_stats: list[dict], links_only: bool) -> str`, private to `historic.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/cli/test_click_cli.py`:

```python
from oddsharvester.cli.commands.historic import _format_combo_summary


def test_combo_summary_lists_every_combo_with_counts():
    out = _format_combo_summary(
        [
            {"league": "russia-premier-league", "season": "2010", "successful": 380, "failed": 0, "errored": False},
            {"league": "russia-premier-league", "season": "2011", "successful": 0, "failed": 0, "errored": False},
        ],
        links_only=True,
    )
    assert "russia-premier-league 2010" in out
    assert "380" in out
    assert "1 combo(s) returned nothing." in out


def test_combo_summary_marks_errored_combos_separately():
    out = _format_combo_summary(
        [
            {"league": "epl", "season": "2020", "successful": 0, "failed": 0, "errored": False},
            {"league": "epl", "season": "2021", "successful": 0, "failed": 0, "errored": True},
        ],
        links_only=False,
    )
    assert "error" in out
    assert "1 combo(s) errored." in out
    assert "1 combo(s) returned nothing." in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_click_cli.py -q -k combo_summary`
Expected: FAIL, `ImportError: cannot import name '_format_combo_summary'`

- [ ] **Step 3: Write the formatter**

Add to `src/oddsharvester/cli/commands/historic.py`, above the `historic` command:

```python
def _format_combo_summary(combo_stats: list[dict], links_only: bool) -> str:
    """Render the per-combo breakdown shown at the end of a multi-combo run."""
    unit = "links" if links_only else "matches"
    labels = [f"{c['league']} {c['season']}".strip() if c["season"] else c["league"] for c in combo_stats]
    width = max(len(label) for label in labels)

    lines = [f"Collected {unit} across {len(combo_stats)} combos:"]
    empty = errored = 0

    for label, combo in zip(labels, combo_stats, strict=True):
        if combo["errored"]:
            lines.append(f"  {label:<{width}}  error")
            errored += 1
        else:
            lines.append(f"  {label:<{width}}  {combo['successful']}")
            if combo["successful"] == 0:
                empty += 1

    if empty:
        lines.append(f"{empty} combo(s) returned nothing.")
    if errored:
        lines.append(f"{errored} combo(s) errored.")

    return "\n".join(lines)
```

- [ ] **Step 4: Wire it into the end-of-run output**

In `src/oddsharvester/cli/commands/historic.py`, after the existing `click.echo` block (line 97) and before the `if scraped_data.failed:` line:

```python
            if len(scraped_data.combo_stats) > 1:
                click.echo(_format_combo_summary(scraped_data.combo_stats, links_only=links_only))
```

Single-combo runs have at most one entry, so their output is unchanged.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_click_cli.py -q`
Expected: PASS

- [ ] **Step 6: Run the full suite and lint**

Run: `uv run pytest tests/ -q --ignore=tests/integration/ && uv run ruff format . && uv run ruff check --fix src/`
Expected: tests PASS, ruff clean

- [ ] **Step 7: Commit**

```bash
git add src/oddsharvester/cli/commands/historic.py tests/cli/test_click_cli.py
git commit -m "$(cat <<'EOF'
feat: print per-combo summary at the end of multi-combo runs

Claude-Session: https://claude.ai/code/session_0115LwmW9Y96q8E1QeLGxwJa
EOF
)"
```

---

### Task 6: Documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/agentic-gotchas.md`

**Interfaces:**
- Consumes: the finished behaviour from Tasks 1-5.
- Produces: nothing consumed by code.

- [ ] **Step 1: Update the README options table**

Replace the `--season` row's description with:

> Comma-separated seasons to scrape (`YYYY`, `YYYY-YYYY`, or `current`). Scraped as the cartesian product with `--league`. Duplicates are ignored.

Append to the `--max-pages` row's description:

> Applies per league/season combo, not per run.

- [ ] **Step 2: Add a bulk-scraping section**

Add a section after the existing two-pass workflow section, with these three examples verbatim:

```bash
# Several seasons of one league
oddsharvester historic --sport football --league england-premier-league \
    --season 2020-2021,2021-2022,2022-2023 --links-only --format csv --output links.csv

# Cartesian product: every league by every season
oddsharvester historic --sport football \
    --league england-premier-league,spain-laliga \
    --season 2021-2022,2022-2023 --links-only

# A league that changed season format mid-history: pass both formats and
# let the invalid pairs report zero
oddsharvester historic --sport football --league russia-premier-league \
    --season 2010,2010-2011,2011,2011-2012 --links-only
```

Explain that a combo returning zero is normal for a wrong-format pair, that the end-of-run table distinguishes it from an errored combo, and that only errored combos are worth re-running.

- [ ] **Step 3: Document the breaking change**

Add this note to the README, near the output-format documentation, and reuse it verbatim in the release notes when the version is cut:

> **Breaking change:** every output row now carries a `season` column, inserted
> directly after `match_date`. It holds the scraped season for `historic` and is
> empty for `upcoming` and `--match-link` runs. Appending to a file produced by
> an earlier version yields a file with two different column layouts, so start a
> new output file rather than appending across the upgrade.

- [ ] **Step 4: Append the OddsPortal behaviour to the gotchas**

`docs/agentic-gotchas.md` already records that HTTP 200 is not validation (a dead season URL returns 200 with zero `eventRow` links). Add a short entry noting that this is exactly why the cartesian product cannot pre-filter invalid `(league, season)` pairs, and why zero links is reported rather than treated as an error. Follow the criteria listed at the bottom of that file.

- [ ] **Step 5: Verify the documented commands parse**

Run each example with `--help`-level validation only, so nothing hits the network:

```bash
uv run oddsharvester historic --sport football --league russia-premier-league \
    --season 2010,2010-2011,2011,2011-2012 --links-only --max-pages 0
```

Expected: exits non-zero on `--max-pages` validation, which proves the `--season` list parsed and validated before it. If it instead fails on the season, the list is not parsing.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/agentic-gotchas.md
git commit -m "$(cat <<'EOF'
docs: document --season lists and the season column schema change

Claude-Session: https://claude.ai/code/session_0115LwmW9Y96q8E1QeLGxwJa
EOF
)"
```

---

## Final verification

- [ ] `uv run pytest tests/ -q --ignore=tests/integration/` passes
- [ ] `uv run pytest tests/integration/ -q -m integration` passes
- [ ] `uv run ruff format . && uv run ruff check --fix src/` clean
- [ ] `rg -n "_scrape_multiple_leagues|validate_season\b" src/ tests/` returns nothing
- [ ] A real single-league single-season run still produces the pre-change one-line output, plus the new `season` column
- [ ] Exit code contract unchanged: a run where every combo returns zero still exits 1 (the existing `if scraped_data and scraped_data.success` branch in `historic.py` already gives this, since the merged success list is empty only when all combos are). Confirm no task altered it.
