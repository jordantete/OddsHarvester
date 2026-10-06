import asyncio
from dataclasses import fields
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from playwright.async_api import BrowserContext, Page
import pytest

from oddsharvester.core.exceptions import SeasonNotFoundError
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import ListingResult, OddsPortalScraper
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import TRANSIENT_ERROR_KEYWORDS
from oddsharvester.core.scrape_options import ScrapeOptions
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats
from oddsharvester.core.scraper_app import _scrape_combos, retry_scrape, run_scraper
from oddsharvester.utils.command_enum import CommandEnum
from oddsharvester.utils.constants import OPERATION_RETRY_MAX_ATTEMPTS, REQUEST_DELAY_JITTER_FACTOR

M1 = "https://www.oddsportal.com/football/h2h/arsenal-hA1Zm19f/leeds-tUxUbLR2/#xtmHKGT0"
M2 = "https://www.oddsportal.com/football/h2h/chelsea-4fGZN2oK/manchester-city-Wtn9Stg0/#lMp9YMye"


async def test_a_historic_run_lists_each_season_then_scrapes_the_listed_matches(fake_scraper):
    fake_scraper.answers["collect_historic_links"] = _listing(M1, M2)
    fake_scraper.answers["extract_match_odds"] = lambda match_links, **_: _odds_result(match_links)

    result = await run_scraper(
        command=CommandEnum.HISTORIC,
        sport="football",
        leagues=["premier-league"],
        seasons=["2023"],
        markets=["1x2", "over_under"],
        max_pages=2,
        concurrency_tasks=7,
    )

    assert fake_scraper.called("collect_historic_links") == [
        {"sport": "football", "league": "premier-league", "season": "2023", "max_pages": 2}
    ]
    [odds] = fake_scraper.called("extract_match_odds")
    assert (odds["match_links"], odds["markets"], odds["concurrent_scraping_task"]) == (
        [M1, M2],
        ["1x2", "over_under"],
        7,
    )
    assert [row["season"] for row in result.success] == ["2023", "2023"]
    assert result.combo_stats == [
        {"league": "premier-league", "season": "2023", "successful": 2, "failed": 0, "errored": False}
    ]
    assert len(fake_scraper.called("stop_playwright")) == 1


async def test_an_upcoming_run_lists_the_date_with_its_filters_then_scrapes_the_listed_matches(fake_scraper):
    fake_scraper.answers["collect_upcoming_links"] = _listing(M1)
    fake_scraper.answers["extract_match_odds"] = lambda match_links, **_: _odds_result(match_links)

    result = await run_scraper(
        command=CommandEnum.UPCOMING_MATCHES,
        sport="basketball",
        date="20991231",
        leagues=["nba"],
        markets=["home_away"],
        include_started=True,
        kickoff_within_hours=6,
        concurrency_tasks=10,
        browser_user_agent="custom-agent",
        browser_locale_timezone="fr-FR",
        headless=False,
    )

    assert fake_scraper.called("collect_upcoming_links") == [
        {
            "sport": "basketball",
            "date": "20991231",
            "league": "nba",
            "include_started": True,
            "kickoff_within_hours": 6,
            "collect_kickoff": False,
        }
    ]
    assert fake_scraper.called("extract_match_odds")[0]["concurrent_scraping_task"] == 10
    [start] = fake_scraper.called("start_playwright")
    assert (start["headless"], start["browser_user_agent"], start["browser_locale_timezone"]) == (
        False,
        "custom-agent",
        "fr-FR",
    )
    assert [row["season"] for row in result.success] == [None]


async def test_every_league_of_an_upcoming_run_is_listed_with_the_same_filters(fake_scraper):
    await run_scraper(
        command="scrape_upcoming",
        sport="football",
        leagues=["england-premier-league", "spain-laliga"],
        kickoff_within_hours=3,
        request_delay=0,
    )

    calls = fake_scraper.called("collect_upcoming_links")
    assert sorted(call["league"] for call in calls) == ["england-premier-league", "spain-laliga"]
    assert all(call["kickoff_within_hours"] == 3 for call in calls)


async def test_the_output_stays_grouped_by_league_then_season(fake_scraper):
    fake_scraper.answers["collect_historic_links"] = lambda league, season, **_: _listing(
        f"https://x/{league}/{season}"
    )
    fake_scraper.answers["extract_match_odds"] = lambda match_links, **_: _odds_result(match_links)

    result = await run_scraper(
        command=CommandEnum.HISTORIC,
        sport="football",
        leagues=["epl", "laliga"],
        seasons=["2020-2021", "2021-2022"],
        request_delay=0,
    )

    combos = [("epl", "2020-2021"), ("epl", "2021-2022"), ("laliga", "2020-2021"), ("laliga", "2021-2022")]
    assert [(combo["league"], combo["season"]) for combo in result.combo_stats] == combos
    assert [row["match_link"] for row in result.success] == [
        f"https://x/{league}/{season}" for league, season in combos
    ]


async def test_a_historic_run_without_seasons_lists_the_current_season_of_each_league(fake_scraper):
    """Issue #78: seasons=None lists every league with season=None instead of erroring each combo."""
    result = await run_scraper(
        command=CommandEnum.HISTORIC,
        sport="football",
        leagues=["england-premier-league", "spain-laliga"],
        seasons=None,
        request_delay=0,
    )

    assert [call["season"] for call in fake_scraper.called("collect_historic_links")] == [None, None]
    assert [combo["errored"] for combo in result.combo_stats] == [False, False]


async def test_a_date_without_a_league_is_one_listing_of_all_leagues(fake_scraper):
    """Issue #87: one listing is one combo, on the same path as several."""
    fake_scraper.answers["collect_upcoming_links"] = _listing(M1)
    fake_scraper.answers["extract_match_odds"] = lambda match_links, **_: _odds_result(match_links)

    result = await run_scraper(command="scrape_upcoming", sport="football", date="20991231", concurrency_tasks=4)

    assert [call["league"] for call in fake_scraper.called("collect_upcoming_links")] == [None]
    assert fake_scraper.called("extract_match_odds")[0]["concurrent_scraping_task"] == 4
    assert result.combo_stats == [{"league": None, "season": None, "successful": 1, "failed": 0, "errored": False}]


async def test_match_links_are_scraped_as_given_without_a_listing(fake_scraper):
    fake_scraper.answers["scrape_matches"] = _odds_result([M1, M2])

    result = await run_scraper(
        command=CommandEnum.UPCOMING_MATCHES,
        match_links=[M1, M2],
        sport="tennis",
        markets=["match_winner"],
        scrape_odds_history=True,
        target_bookmaker="bet365",
        concurrency_tasks=5,
    )

    [call] = fake_scraper.called("scrape_matches")
    assert (call["match_links"], call["sport"], call["markets"]) == ([M1, M2], "tennis", ["match_winner"])
    assert (call["scrape_odds_history"], call["target_bookmaker"], call["concurrent_scraping_task"]) == (
        True,
        "bet365",
        5,
    )
    assert fake_scraper.called("collect_upcoming_links") == []
    assert [row["match_link"] for row in result.success] == [M1, M2]


async def test_a_links_only_historic_run_returns_the_listed_rows_without_scraping_odds(fake_scraper):
    fake_scraper.answers["collect_historic_links"] = lambda league, **_: _listing(f"https://x/{league}/m1")

    result = await run_scraper(
        command="scrape_historic",
        sport="football",
        leagues=["england-premier-league", "spain-laliga"],
        seasons=["2022-2023"],
        links_only=True,
        request_delay=0,
    )

    assert fake_scraper.called("extract_match_odds") == []
    assert result.success == [
        {
            "match_link": f"https://x/{league}/m1",
            "sport": "football",
            "league": league,
            "season": "2022-2023",
        }
        for league in ("england-premier-league", "spain-laliga")
    ]


async def test_a_links_only_upcoming_run_returns_rows_with_their_kickoff(fake_scraper):
    fake_scraper.answers["collect_upcoming_links"] = ListingResult(rows=[{"match_link": M1, "kickoff_utc": None}])

    result = await run_scraper(command="scrape_upcoming", sport="football", date="20991231", links_only=True)

    assert fake_scraper.called("collect_upcoming_links")[0]["collect_kickoff"] is True
    assert fake_scraper.called("extract_match_odds") == []
    assert list(result.success[0]) == ["match_link", "sport", "league", "date", "season", "kickoff_utc"]


@pytest.mark.parametrize(
    ("keywords", "error"),
    [({"command": "scrape_everything"}, ValueError), ({"command": "scrape_upcoming", "no_such_option": 1}, TypeError)],
    ids=["unknown command", "unknown keyword"],
)
async def test_run_scraper_raises_on_options_no_run_can_take(fake_scraper, keywords, error):
    with pytest.raises(error):
        await run_scraper(**keywords)

    assert fake_scraper.calls == [], "nothing starts"


async def test_a_links_only_historic_run_appends_the_match_day_last(fake_scraper):
    """A new CSV column goes last, so a file appended across the upgrade keeps its first columns in place."""
    fake_scraper.answers["collect_historic_links"] = ListingResult(rows=[{"match_link": M1, "match_day": "2025-05-18"}])

    result = await run_scraper(
        command="scrape_historic",
        sport="football",
        leagues=["england-premier-league"],
        seasons=["2024-2025"],
        links_only=True,
        request_delay=0,
    )

    assert list(result.success[0]) == ["match_link", "sport", "league", "season", "match_day"]
    assert result.success[0]["match_day"] == "2025-05-18"


async def test_a_live_run_reads_the_live_listing_of_its_one_league(fake_scraper):
    fake_scraper.answers["scrape_live"] = _odds_result([M1])

    result = await run_scraper(
        command="scrape_live", sport="football", leagues=["england-premier-league"], markets=["1x2"]
    )

    [call] = fake_scraper.called("scrape_live")
    assert (call["sport"], call["league"], call["markets"], call["match_links"]) == (
        "football",
        "england-premier-league",
        ["1x2"],
        None,
    )
    assert [row["match_link"] for row in result.success] == [M1]


async def test_a_live_run_with_match_links_stays_on_the_in_play_flow(fake_scraper):
    await run_scraper(command="scrape_live", sport="football", match_links=[M1], markets=["1x2"])

    assert fake_scraper.called("scrape_live")[0]["match_links"] == [M1]
    assert fake_scraper.called("scrape_matches") == []


async def test_a_single_league_whose_listing_failed_returns_an_errored_result(fake_scraper):
    """Not None: both CLIs report the errored combo and exit 1 on it."""
    fake_scraper.answers["collect_upcoming_links"] = ValueError("Season page redirected")

    result = await run_scraper(command="scrape_upcoming", sport="football", leagues=["england-premier-league"])

    assert result.success == []
    assert result.combo_stats == [
        {"league": "england-premier-league", "season": None, "successful": 0, "failed": 0, "errored": True}
    ]
    assert fake_scraper.called("extract_match_odds") == []


async def test_a_browser_that_fails_to_start_returns_none_and_logs_why(fake_scraper, caplog):
    fake_scraper.answers["start_playwright"] = RuntimeError("browser crashed")

    with caplog.at_level(logging.ERROR, logger="ScraperApp"):
        result = await run_scraper(
            command=CommandEnum.HISTORIC, sport="football", leagues=["premier-league"], seasons=["2023"]
        )

    assert result is None
    record = next(r for r in caplog.records if "browser crashed" in r.getMessage())
    assert "RuntimeError" in record.getMessage()
    assert record.exc_info is not None
    assert len(fake_scraper.called("stop_playwright")) == 1


async def test_several_proxy_urls_start_the_browser_with_a_rotating_pool(fake_scraper):
    await run_scraper(
        command=CommandEnum.UPCOMING_MATCHES,
        sport="football",
        date="20991231",
        proxy_url=("http://a.example.com:1", "http://b.example.com:2"),
    )

    assert fake_scraper.called("start_playwright")[0]["proxy_manager"].is_multi_proxy() is True


async def test_the_scraper_is_built_with_the_run_page_options(fake_scraper):
    streamed = []

    await run_scraper(
        command="scrape_upcoming",
        sport="football",
        date="20991231",
        local_kickoff=True,
        preview_submarkets_only=True,
        base_url="https://www.centroquote.it",
        on_match=streamed.append,
    )

    built = fake_scraper.built_with
    assert (built["local_kickoff"], built["preview_submarkets_only"], built["base_url"]) == (
        True,
        True,
        "https://www.centroquote.it",
    )
    built["on_match"]({"match_link": M1, "season": None})
    assert streamed == [{"match_link": M1, "season": None}]


async def test_retry_scrape_success():
    """Test retry_scrape function with successful first attempt."""
    mock_func = AsyncMock(return_value={"data": "test"})

    result = await retry_scrape(mock_func, "arg1", kwarg1="test")

    mock_func.assert_called_once_with("arg1", kwarg1="test")
    assert result == {"data": "test"}


@patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_scrape_transient_error(mock_sleep):
    """Test retry_scrape function with transient error that succeeds on retry."""
    mock_func = AsyncMock()

    # Fail with a transient error on first call, succeed on second
    mock_func.side_effect = [Exception(f"Connection failed: {TRANSIENT_ERROR_KEYWORDS[0]}"), {"data": "retry_success"}]

    result = await retry_scrape(mock_func, "arg1")

    assert mock_func.call_count == 2
    mock_sleep.assert_called_once()
    assert result == {"data": "retry_success"}


@patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_scrape_non_retryable_error(mock_sleep):
    """A non-retryable error is raised at once, as itself."""
    mock_func = AsyncMock(side_effect=ValueError("Invalid input"))

    with pytest.raises(ValueError, match="Invalid input"):
        await retry_scrape(mock_func, "arg1")

    mock_func.assert_called_once()
    mock_sleep.assert_not_called()


@patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_scrape_reraises_the_last_error_when_retries_run_out(mock_sleep):
    """Exhausted retries surface the original exception instead of None, so callers can report it."""
    mock_func = AsyncMock(side_effect=Exception(f"Connection failed: {TRANSIENT_ERROR_KEYWORDS[0]}"))

    with pytest.raises(Exception, match=TRANSIENT_ERROR_KEYWORDS[0]):
        await retry_scrape(mock_func)

    assert mock_func.call_count == OPERATION_RETRY_MAX_ATTEMPTS
    assert mock_sleep.call_count == OPERATION_RETRY_MAX_ATTEMPTS - 1


async def test_retry_scrape_reraises_the_original_exception_type():
    from oddsharvester.core.exceptions import PageNotFoundError

    error = PageNotFoundError("League page not found", url="https://www.oddsportal.com/football/x/y/results/")
    mock_func = AsyncMock(side_effect=error)

    with pytest.raises(PageNotFoundError) as excinfo:
        await retry_scrape(mock_func)

    assert excinfo.value is error


def _listing(*links: str, failed_page_urls: list[str] | None = None) -> ListingResult:
    return ListingResult(rows=[{"match_link": link} for link in links], failed_page_urls=failed_page_urls or [])


def _odds_result(links: list[str], failed: list[str] | None = None) -> ScrapeResult:
    success = [{"match_link": link, "season": None} for link in links]
    failures = [FailedUrl(url=url, error_type=ErrorType.NAVIGATION, error_message="Timeout") for url in (failed or [])]
    return ScrapeResult(
        success=success,
        failed=failures,
        stats=ScrapeStats(total_urls=len(success) + len(failures), successful=len(success), failed=len(failures)),
    )


def _links_only_context(league, season):
    return {"sport": "football", "league": league, "season": season}


async def _run_combos(collect, combos, scraper=None, **overrides) -> ScrapeResult:
    scraper = scraper or MagicMock()
    kwargs = {
        "scraper": scraper,
        "combos": combos,
        "collect": collect,
        "links_only_context": _links_only_context,
        "concurrency": 3,
        "request_delay": 0,
        "links_only": False,
        "odds_kwargs": {},
    }
    kwargs.update(overrides)
    return await _scrape_combos(**kwargs)


async def test_scrape_combos_lists_in_parallel_under_the_concurrency_cap():
    """Listings overlap, but never more than `concurrency` at once (issue #87)."""
    in_flight = {"now": 0, "max": 0}

    async def collect(league, season):
        in_flight["now"] += 1
        in_flight["max"] = max(in_flight["max"], in_flight["now"])
        await asyncio.sleep(0.01)
        in_flight["now"] -= 1
        return _listing(f"https://x/{league}/m1")

    combos = [(f"league-{i}", None) for i in range(5)]

    result = await _run_combos(collect, combos, concurrency=2, links_only=True)

    assert in_flight["max"] == 2
    assert result.stats.successful == 5


@patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock)
async def test_scrape_combos_paces_listings_after_the_first(mock_sleep):
    """Listings follow the match-page rule: no delay first, then request_delay plus jitter."""
    collect = AsyncMock(side_effect=lambda league, season: _listing(f"https://x/{league}/m1"))

    await _run_combos(
        collect, [("a", None), ("b", None), ("c", None)], concurrency=1, request_delay=2.0, links_only=True
    )

    assert mock_sleep.await_count == 2
    assert all(2.0 <= call.args[0] <= 3.0 for call in mock_sleep.await_args_list)


async def test_scrape_combos_scrapes_all_links_in_one_flat_batch():
    """One extract_match_odds call over the deduplicated links; rows go back to their combo."""
    listings = {
        "epl": _listing("https://x/epl/m1", "https://x/epl/m2"),
        "laliga": _listing("https://x/laliga/m1", "https://x/epl/m2"),
    }
    collect = AsyncMock(side_effect=lambda league, season: listings[league])
    scraper = MagicMock()
    scraper.extract_match_odds = AsyncMock(
        return_value=_odds_result(["https://x/epl/m1", "https://x/epl/m2", "https://x/laliga/m1"])
    )

    result = await _run_combos(
        collect,
        [("epl", "2023"), ("laliga", "2023")],
        scraper=scraper,
        odds_kwargs={"sport": "football", "markets": ["1x2"]},
    )

    scraper.extract_match_odds.assert_awaited_once_with(
        match_links=["https://x/epl/m1", "https://x/epl/m2", "https://x/laliga/m1"], sport="football", markets=["1x2"]
    )
    assert collect.await_args_list[0].kwargs == {"league": "epl", "season": "2023"}
    assert result.combo_stats == [
        {"league": "epl", "season": "2023", "successful": 2, "failed": 0, "errored": False},
        {"league": "laliga", "season": "2023", "successful": 1, "failed": 0, "errored": False},
    ]
    assert [row["season"] for row in result.success] == ["2023", "2023", "2023"]


async def test_scrape_combos_attributes_failures_and_listing_pages_to_their_combo():
    listings = {
        ("epl", "2022"): _listing("https://x/epl/m1", failed_page_urls=["https://x/epl/results/#page/2"]),
        ("epl", "2023"): _listing("https://x/epl/m2", "https://x/epl/m3"),
    }
    collect = AsyncMock(side_effect=lambda league, season: listings[(league, season)])
    scraper = MagicMock()
    scraper.extract_match_odds = AsyncMock(
        return_value=_odds_result(["https://x/epl/m1", "https://x/epl/m3"], failed=["https://x/epl/m2"])
    )

    result = await _run_combos(collect, [("epl", "2022"), ("epl", "2023")], scraper=scraper)

    assert result.combo_stats == [
        {"league": "epl", "season": "2022", "successful": 1, "failed": 1, "errored": False},
        {"league": "epl", "season": "2023", "successful": 1, "failed": 1, "errored": False},
    ]
    listing_failures = [f for f in result.failed if f.error_type is ErrorType.LISTING_PAGE]
    assert [f.url for f in listing_failures] == ["https://x/epl/results/#page/2"]
    assert (result.stats.successful, result.stats.failed, result.stats.total_urls) == (2, 2, 4)
    assert {row["match_link"]: row["season"] for row in result.success} == {
        "https://x/epl/m1": "2022",
        "https://x/epl/m3": "2023",
    }


async def test_scrape_combos_keeps_going_when_one_listing_errors():
    """A non-retryable listing error marks its combo errored and leaves the others alone."""

    async def collect(league, season):
        if league == "broken":
            raise ValueError("Season page redirected")
        return _listing(f"https://x/{league}/m1")

    scraper = MagicMock()
    scraper.extract_match_odds = AsyncMock(return_value=_odds_result(["https://x/epl/m1", "https://x/laliga/m1"]))

    result = await _run_combos(collect, [("epl", None), ("broken", None), ("laliga", None)], scraper=scraper)

    assert [c["errored"] for c in result.combo_stats] == [False, True, False]
    assert result.stats.successful == 2


async def test_scrape_combos_counts_a_redirected_season_as_zero_links():
    """A season OddsPortal redirects away is an empty combo, not a failed listing."""

    async def collect(league, season):
        if league == "broken":
            raise SeasonNotFoundError(
                "Season page redirected to https://x/; the season does not exist under this league slug.",
                url="https://x/epl-2010/results/",
            )
        return _listing(f"https://x/{league}/m1")

    scraper = MagicMock()
    scraper.extract_match_odds = AsyncMock(return_value=_odds_result(["https://x/epl/m1"]))

    result = await _run_combos(collect, [("epl", "2023"), ("broken", "2010")], scraper=scraper)

    assert result.failed == []
    assert result.combo_stats == [
        {"league": "epl", "season": "2023", "successful": 1, "failed": 0, "errored": False},
        {"league": "broken", "season": "2010", "successful": 0, "failed": 0, "errored": False},
    ]


async def test_scrape_combos_links_only_counts_a_redirected_season_as_zero_links():
    """Same as the odds-mode case, but for links_only."""

    async def collect(league, season):
        if league == "broken":
            raise SeasonNotFoundError(
                "Season page redirected to https://x/; the season does not exist under this league slug.",
                url="https://x/epl-2010/results/",
            )
        return _listing(f"https://x/{league}/m1")

    result = await _run_combos(collect, [("epl", "2023"), ("broken", "2010")], links_only=True)

    assert result.failed == []
    assert result.combo_stats == [
        {"league": "epl", "season": "2023", "successful": 1, "failed": 0, "errored": False},
        {"league": "broken", "season": "2010", "successful": 0, "failed": 0, "errored": False},
    ]


@patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock)
async def test_scrape_combos_records_exhausted_retries_as_errored(mock_sleep):
    """A transient error is retried with the operation backoff; giving up marks the combo errored."""
    collect = AsyncMock(side_effect=Exception("Navigation timeout"))

    result = await _run_combos(collect, [("epl", None)], concurrency=1, links_only=True)

    assert collect.await_count == OPERATION_RETRY_MAX_ATTEMPTS
    assert result.combo_stats == [{"league": "epl", "season": None, "successful": 0, "failed": 0, "errored": True}]
    assert result.success == []
    assert [(f.error_type, f.url, f.is_retryable) for f in result.failed] == [(ErrorType.LISTING_PAGE, "epl", True)]
    assert result.failed[0].error_message == "Listing failed for epl: Exception: Navigation timeout"


async def test_scrape_combos_links_only_never_scrapes_odds_and_keeps_the_row_shape():
    def listing_for(league, season):
        failed = ["https://x/epl/results/#page/2"] if league == "epl" else None
        return _listing(f"https://x/{league}/m1", failed_page_urls=failed)

    collect = AsyncMock(side_effect=listing_for)
    scraper = MagicMock()
    scraper.extract_match_odds = AsyncMock()

    result = await _run_combos(collect, [("epl", "2023"), ("laliga", "2023")], scraper=scraper, links_only=True)

    scraper.extract_match_odds.assert_not_called()
    assert result.success == [
        {"match_link": "https://x/epl/m1", "sport": "football", "league": "epl", "season": "2023"},
        {"match_link": "https://x/laliga/m1", "sport": "football", "league": "laliga", "season": "2023"},
    ]
    assert result.combo_stats == [
        {"league": "epl", "season": "2023", "successful": 1, "failed": 1, "errored": False},
        {"league": "laliga", "season": "2023", "successful": 1, "failed": 0, "errored": False},
    ]
    assert (result.stats.successful, result.stats.failed, result.stats.total_urls) == (2, 1, 3)


async def test_scrape_combos_reports_an_errored_combo_as_a_listing_failure():
    """B3: a combo whose listing failed must show up in `failed`, or a multi-combo run looks complete."""

    async def collect(league, season):
        if league == "broken":
            raise ValueError("Season page redirected")
        return _listing(f"https://x/{league}/m1")

    scraper = MagicMock()
    scraper.extract_match_odds = AsyncMock(return_value=_odds_result(["https://x/epl/m1"]))

    result = await _run_combos(collect, [("epl", "2023"), ("broken", "2023")], scraper=scraper)

    [failure] = result.failed
    assert failure.error_type is ErrorType.LISTING_PAGE
    assert failure.url == "broken 2023"
    assert failure.error_message == "Listing failed for broken 2023: ValueError: Season page redirected"
    assert failure.is_retryable is False
    assert (result.stats.successful, result.stats.failed, result.stats.total_urls) == (1, 1, 2)
    assert result.combo_stats[1] == {
        "league": "broken",
        "season": "2023",
        "successful": 0,
        "failed": 0,
        "errored": True,
    }


async def test_scrape_combos_records_a_none_listing_and_scrapes_the_other_combos():
    """A collector that returns None is one LISTING_PAGE failure; the other combos are still scraped."""
    listings = {"epl": _listing("https://x/epl/m1"), "empty": None, "laliga": _listing("https://x/laliga/m1")}
    collect = AsyncMock(side_effect=lambda league, season: listings[league])
    scraper = MagicMock()
    scraper.extract_match_odds = AsyncMock(return_value=_odds_result(["https://x/epl/m1", "https://x/laliga/m1"]))

    result = await _run_combos(collect, [("epl", "2023"), ("empty", "2023"), ("laliga", "2023")], scraper=scraper)

    scraper.extract_match_odds.assert_awaited_once_with(match_links=["https://x/epl/m1", "https://x/laliga/m1"])
    [failure] = result.failed
    assert failure.error_type is ErrorType.LISTING_PAGE
    assert failure.url == "empty 2023"
    assert failure.error_message == "Listing failed for empty 2023: no listing returned"
    assert failure.is_retryable is False
    assert [combo["errored"] for combo in result.combo_stats] == [False, True, False]
    assert (result.stats.successful, result.stats.failed, result.stats.total_urls) == (2, 1, 3)


async def test_scrape_combos_ignores_the_url_of_a_non_scraper_error():
    """Only a ScraperError's url is trustworthy; an unrelated exception's url is not the failed listing's."""

    class _HttpError(Exception):
        def __init__(self, message):
            super().__init__(message)
            self.url = "https://elsewhere/"

    async def collect(league, season):
        if league == "broken":
            raise _HttpError("boom")
        return _listing(f"https://x/{league}/m1")

    result = await _run_combos(collect, [("epl", "2023"), ("broken", "2023")], links_only=True)

    [failure] = result.failed
    assert failure.url == "broken 2023"


async def test_scrape_combos_links_only_reports_an_errored_combo_with_its_url():
    from oddsharvester.core.exceptions import PageNotFoundError

    async def collect(league, season):
        if league == "gone":
            raise PageNotFoundError("League page not found", url="https://www.oddsportal.com/football/x/gone/results/")
        return _listing(f"https://x/{league}/m1")

    result = await _run_combos(collect, [("epl", None), ("gone", None)], links_only=True)

    [failure] = result.failed
    assert failure.error_type is ErrorType.LISTING_PAGE
    assert failure.url == "https://www.oddsportal.com/football/x/gone/results/"
    assert failure.error_message.startswith("Listing failed for gone: PageNotFoundError: League page not found")
    assert (result.stats.successful, result.stats.failed, result.stats.total_urls) == (1, 1, 2)


@patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock)
async def test_scrape_combos_keeps_a_rate_limited_listing_retryable(mock_sleep):
    from oddsharvester.core.exceptions import RateLimitError

    listing_url = "https://www.oddsportal.com/football/england/premier-league-2023-2024/results/"
    collect = AsyncMock(
        side_effect=RateLimitError("rate limited by OddsPortal: HTTP 429", url=listing_url, retry_after=0)
    )

    result = await _run_combos(collect, [("epl", "2023")], concurrency=1, links_only=True)

    [failure] = result.failed
    assert failure.url == listing_url
    assert failure.is_retryable is True
    assert "RateLimitError" in failure.error_message


async def test_scrape_combos_with_no_links_skips_the_odds_phase():
    collect = AsyncMock(return_value=_listing())
    scraper = MagicMock()
    scraper.extract_match_odds = AsyncMock()

    result = await _run_combos(collect, [("epl", None)], scraper=scraper)

    scraper.extract_match_odds.assert_not_called()
    assert result.success == []
    assert result.combo_stats == [{"league": "epl", "season": None, "successful": 0, "failed": 0, "errored": False}]


@patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock)
async def test_scrape_combos_paces_every_listing_after_the_first_under_concurrency(mock_sleep):
    """At concurrency 2 the shape is unchanged: one listing starts at once, each later one waits once.

    The wait is delay plus jitter, bounded by REQUEST_DELAY_JITTER_FACTOR; with the default
    -c 3 and --request-delay 1.0 that is one request at t=0 and the next two about a second later.
    """
    collect = AsyncMock(side_effect=lambda league, season: _listing(f"https://x/{league}/m1"))

    result = await _run_combos(
        collect,
        [("a", None), ("b", None), ("c", None), ("d", None)],
        concurrency=2,
        request_delay=1.0,
        links_only=True,
    )

    assert mock_sleep.await_count == 3
    assert all(1.0 <= call.args[0] <= 1.0 * (1 + REQUEST_DELAY_JITTER_FACTOR) for call in mock_sleep.await_args_list)
    assert result.stats.successful == 4


def _upcoming_scraper(tab) -> OddsPortalScraper:
    """A scraper whose listing tab is `tab`; everything but the listing read is mocked."""
    playwright_manager = MagicMock(spec=PlaywrightManager)
    playwright_manager.context = AsyncMock(spec=BrowserContext)
    playwright_manager.context.new_page = AsyncMock(return_value=tab)
    scraper = OddsPortalScraper(
        playwright_manager=playwright_manager,
        market_extractor=MagicMock(spec=OddsPortalMarketExtractor),
        scroller=AsyncMock(),
        cookie_dismisser=AsyncMock(),
        selection_manager=AsyncMock(),
    )
    scraper._warm_up_page = AsyncMock()
    scraper.extract_match_odds = AsyncMock()
    return scraper


async def _list_upcoming(scraper: OddsPortalScraper) -> ScrapeResult:
    async def collect(league, season):
        return await scraper.collect_upcoming_links(sport="football", date="20260601", league=league)

    return await _run_combos(collect, [("england-premier-league", None)], scraper=scraper)


async def test_scrape_combos_errors_an_upcoming_listing_whose_rows_cannot_be_read():
    """B6: an extraction crash errors the combo, which the CLI reports as a failed listing and exits 1 on."""
    tab = AsyncMock(spec=Page)
    tab.content.side_effect = RuntimeError("renderer crashed")
    scraper = _upcoming_scraper(tab)

    result = await _list_upcoming(scraper)

    assert result.combo_stats == [
        {"league": "england-premier-league", "season": None, "successful": 0, "failed": 0, "errored": True}
    ]
    [failure] = result.failed
    assert failure.error_type is ErrorType.LISTING_PAGE
    assert failure.error_message == "Listing failed for england-premier-league: RuntimeError: renderer crashed"
    scraper.extract_match_odds.assert_not_awaited()


async def test_scrape_combos_keeps_an_upcoming_listing_without_rows_a_success():
    """A league with no match on the date is an empty listing, not a failed one."""
    tab = AsyncMock(spec=Page)
    tab.content.return_value = "<html><body></body></html>"
    scraper = _upcoming_scraper(tab)

    result = await _list_upcoming(scraper)

    assert result.combo_stats == [
        {"league": "england-premier-league", "season": None, "successful": 0, "failed": 0, "errored": False}
    ]
    assert result.failed == []


async def test_run_scraper_passes_every_keyword_to_the_options():
    keywords = {
        "match_links": [M1],
        "sport": "football",
        "date": "20991231",
        "leagues": ["england-premier-league"],
        "seasons": ["2024-2025"],
        "markets": ["1x2"],
        "max_pages": 2,
        "proxy_url": "http://proxy.example:8080",
        "proxy_user": "user",
        "proxy_pass": "pass",
        "browser_user_agent": "UA/1",
        "browser_locale_timezone": "en-GB",
        "browser_timezone_id": "Europe/London",
        "base_url": "https://www.centroquote.it",
        "target_bookmaker": "bet365",
        "scrape_odds_history": True,
        "headless": False,
        "preview_submarkets_only": True,
        "bookies_filter": "crypto",
        "period": "1st_half",
        "request_delay": 2.5,
        "concurrency_tasks": 5,
        "include_started": True,
        "kickoff_within_hours": 6.0,
        "links_only": True,
        "local_kickoff": True,
        "on_match": print,
    }
    assert {"command", *keywords} == {field.name for field in fields(ScrapeOptions)}

    with patch("oddsharvester.core.scraper_app.run_scrape", new_callable=AsyncMock, return_value="result") as run:
        result = await run_scraper(command=CommandEnum.HISTORIC, **keywords)

    assert result == "result"
    assert run.await_args.args == (ScrapeOptions(command=CommandEnum.HISTORIC, **keywords),)


@pytest.mark.parametrize("outcome", ["links", "failed listing", "crash"])
async def test_the_keyword_call_of_resolve_events_b_still_works(fake_scraper, outcome):
    """The call at betting_research/strategies/telegram-value-ai-clv/resolve_events_b.py:110-111, verbatim."""
    key, season, oh_sport = "football__england_premier-league__2024-2025", "2024-2025", "football"
    answers = {
        "links": ListingResult(rows=[{"match_link": M1}, {"match_link": M2}]),
        "failed listing": ValueError("Season page redirected"),
    }
    if outcome == "crash":
        fake_scraper.answers["start_playwright"] = RuntimeError("browser crashed")
    else:
        fake_scraper.answers["collect_historic_links"] = answers[outcome]

    res = await run_scraper(command=CommandEnum.HISTORIC, sport=oh_sport, leagues=[key], seasons=[season],
                            links_only=True, headless=True, request_delay=2.0, concurrency_tasks=1)  # fmt: skip

    if outcome == "crash":
        assert res is None
        return
    assert fake_scraper.called("start_playwright")[0]["headless"] is True
    assert fake_scraper.called("collect_historic_links") == [
        {"sport": "football", "league": key, "season": season, "max_pages": None}
    ]
    assert fake_scraper.called("extract_match_odds") == []
    if outcome == "links":
        assert [r["match_link"] for r in res.success] == [M1, M2]
        assert res.failed == []
    else:
        assert res.success == []
        assert res.failed[0].error_type is ErrorType.LISTING_PAGE
        assert "ValueError: Season page redirected" in res.failed[0].error_message


@pytest.mark.parametrize(
    ("keywords", "message"),
    [
        ({"command": "scrape_live"}, "'sport' must be provided for live scraping."),
        (
            {"command": "scrape_historic", "sport": "football", "seasons": ["2024"]},
            "Both 'sport' and 'leagues' must be provided for historic scraping.",
        ),
        (
            {"command": "scrape_historic", "match_links": [M1], "leagues": ["england-premier-league"]},
            "Both 'sport' and 'leagues' must be provided for historic scraping.",
        ),
        (
            {"command": "scrape_upcoming", "sport": "football"},
            "Either 'date' or 'leagues' must be provided for upcoming matches scraping.",
        ),
    ],
    ids=["live without sport", "historic without league", "match links without sport", "upcoming without date"],
)
async def test_an_impossible_run_is_refused_before_the_browser_starts(fake_scraper, caplog, keywords, message):
    with caplog.at_level(logging.ERROR, logger="ScraperApp"):
        result = await run_scraper(**keywords)

    assert result is None
    assert f"Scraping failed: ValueError: {message}" in caplog.text
    assert fake_scraper.called("start_playwright") == []
    assert len(fake_scraper.called("stop_playwright")) == 1


async def test_the_proxy_urls_are_logged_without_their_credentials(fake_scraper, caplog):
    proxies = ("http://user:secret@proxy.example:8080", "socks5://name:hunter2@other.example:1080")

    with caplog.at_level(logging.INFO):
        await run_scraper(command="scrape_upcoming", sport="football", date="20991231", proxy_url=proxies)

    assert "proxy_url=['http://proxy.example:8080', 'socks5://other.example:1080']" in caplog.text
    assert "secret" not in caplog.text
    assert "hunter2" not in caplog.text


LISTED = ListingResult(rows=[{"match_link": M1}])


@pytest.mark.parametrize(
    ("base", "ignored", "methods"),
    [
        (
            {"command": "scrape_live", "sport": "football"},
            {"date": "20991231", "seasons": ["2024"], "max_pages": 2, "period": "1st_half",
             "scrape_odds_history": True, "include_started": True, "kickoff_within_hours": 6},
            ["scrape_live"],
        ),
        (
            {"command": "scrape_upcoming", "sport": "football", "match_links": [M1]},
            {"date": "20991231", "leagues": ["england-premier-league"], "max_pages": 2, "include_started": True,
             "kickoff_within_hours": 6, "links_only": True},
            ["scrape_matches"],
        ),
        (
            {"command": "scrape_historic", "sport": "football", "leagues": ["england-premier-league"]},
            {"date": "20991231", "include_started": True, "kickoff_within_hours": 6},
            ["collect_historic_links", "extract_match_odds"],
        ),
        (
            {"command": "scrape_upcoming", "sport": "football", "date": "20991231"},
            {"seasons": ["2024"], "max_pages": 2},
            ["collect_upcoming_links", "extract_match_odds"],
        ),
    ],
    ids=["live", "match links", "historic listing", "upcoming listing"],
)  # fmt: skip
async def test_each_branch_reads_only_its_own_options(fake_scraper, base, ignored, methods):
    fake_scraper.answers["collect_historic_links"] = fake_scraper.answers["collect_upcoming_links"] = LISTED

    await run_scraper(**base)
    without = [fake_scraper.called(method) for method in methods]
    fake_scraper.calls.clear()
    await run_scraper(**base, **ignored)

    assert [fake_scraper.called(method) for method in methods] == without
    assert all(without)


@pytest.mark.parametrize(
    ("seasons", "season"),
    [(["2025-2026"], "2025-2026"), (["current"], "current"), (None, None), (["2024-2025", "2025-2026"], None)],
    ids=["one season", "current", "no season", "two seasons"],
)
async def test_match_link_records_carry_the_one_season_given(fake_scraper, seasons, season):
    fake_scraper.answers["scrape_matches"] = lambda **_: ScrapeResult(
        success=[{"match_link": M1, "season": None}, {"match_link": M2, "season": None}],
        stats=ScrapeStats(total_urls=2, successful=2),
    )

    result = await run_scraper(command=CommandEnum.HISTORIC, sport="football", match_links=[M1, M2], seasons=seasons)

    assert [record["season"] for record in result.success] == [season, season]


def _streaming(fake_scraper, odds_result):
    """An answer that streams each record through the run's callback, as the scraper does, then returns them."""

    def answer(**kwargs):
        result = odds_result(**kwargs)
        for record in result.success:
            fake_scraper.built_with["on_match"](record)
        return result

    return answer


@pytest.mark.parametrize(
    ("seasons", "season"),
    [(["2025-2026"], "2025-2026"), (["current"], "current"), (None, None), (["2024-2025", "2025-2026"], None)],
    ids=["one season", "current", "no season", "two seasons"],
)
async def test_a_streamed_match_link_record_carries_the_season_of_the_stored_one(fake_scraper, seasons, season):
    streamed = []
    fake_scraper.answers["scrape_matches"] = _streaming(
        fake_scraper, lambda match_links, **_: _odds_result(match_links)
    )

    result = await run_scraper(
        command=CommandEnum.HISTORIC,
        sport="football",
        match_links=[M1, M2],
        seasons=seasons,
        on_match=lambda record: streamed.append(dict(record)),
    )

    assert streamed == result.success
    assert [record["season"] for record in streamed] == [season, season]


async def test_a_streamed_listing_record_carries_the_season_of_its_combo(fake_scraper):
    streamed = []
    fake_scraper.answers["collect_historic_links"] = lambda season, **_: _listing(f"https://x/{season}")
    fake_scraper.answers["extract_match_odds"] = _streaming(
        fake_scraper, lambda match_links, **_: _odds_result(match_links)
    )

    result = await run_scraper(
        command=CommandEnum.HISTORIC,
        sport="football",
        leagues=["epl"],
        seasons=["2020-2021", "2021-2022"],
        request_delay=0,
        on_match=lambda record: streamed.append(dict(record)),
    )

    assert streamed == result.success
    assert [record["season"] for record in streamed] == ["2020-2021", "2021-2022"]


class _ListSink(list):
    """A stream callback that is falsy until it has received a record."""

    def __call__(self, record):
        self.append(dict(record))


async def test_a_falsy_stream_callback_still_receives_every_record(fake_scraper):
    sink = _ListSink()
    fake_scraper.answers["scrape_matches"] = _streaming(
        fake_scraper, lambda match_links, **_: _odds_result(match_links)
    )

    await run_scraper(command=CommandEnum.HISTORIC, sport="football", match_links=[M1, M2], on_match=sink)

    assert [record["match_link"] for record in sink] == [M1, M2]


@pytest.mark.parametrize(
    "proxy_url",
    [
        "http://alice:pa#s3cret@p1.example:8080",
        "http://alice:pa?s3cret@p1.example:8080",
        "alice:s3cret@p1.example:8080",
    ],
    ids=["hash in password", "question mark in password", "no scheme"],
)
async def test_a_proxy_password_urlparse_cannot_see_stays_out_of_the_logs(fake_scraper, caplog, proxy_url):
    with caplog.at_level(logging.DEBUG):
        await run_scraper(command=CommandEnum.UPCOMING_MATCHES, sport="football", date="20991231", proxy_url=proxy_url)

    assert "s3cret" not in caplog.text
