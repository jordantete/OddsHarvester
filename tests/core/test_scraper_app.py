import asyncio
import logging
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from oddsharvester.core import scraper_app
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import ListingResult, OddsPortalScraper
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import TRANSIENT_ERROR_KEYWORDS
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats
from oddsharvester.core.scraper_app import _scrape_combos, retry_scrape, run_scraper
from oddsharvester.utils.command_enum import CommandEnum
from oddsharvester.utils.constants import OPERATION_RETRY_MAX_ATTEMPTS, REQUEST_DELAY_JITTER_FACTOR


@pytest.fixture
def setup_mocks():
    """Set up common mocks for tests."""
    playwright_manager_mock = MagicMock(spec=PlaywrightManager)
    market_extractor_mock = MagicMock(spec=OddsPortalMarketExtractor)
    scraper_mock = MagicMock(spec=OddsPortalScraper)

    # Configure the scraper mock
    scraper_mock.start_playwright = AsyncMock()
    scraper_mock.stop_playwright = AsyncMock()
    scraper_mock.scrape_matches = AsyncMock(return_value={"result": "match_data"})
    scraper_mock.scrape_live = AsyncMock(return_value={"result": "live_data"})
    scraper_mock.collect_historic_links = AsyncMock(
        return_value=ListingResult(rows=[{"match_link": "https://oddsportal.com/m1"}])
    )
    scraper_mock.collect_upcoming_links = AsyncMock(
        return_value=ListingResult(rows=[{"match_link": "https://oddsportal.com/m1"}])
    )
    scraper_mock.extract_match_odds = AsyncMock(
        return_value=ScrapeResult(
            success=[{"match_link": "https://oddsportal.com/m1", "season": None}],
            stats=ScrapeStats(total_urls=1, successful=1),
        )
    )

    return {
        "playwright_manager_mock": playwright_manager_mock,
        "market_extractor_mock": market_extractor_mock,
        "scraper_mock": scraper_mock,
    }


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_historic(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """Test run_scraper with historic command."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock

    proxy_manager_instance = MagicMock()
    proxy_manager_instance.get_current_proxy.return_value = {"server": "test-proxy"}
    proxy_manager_mock.return_value = proxy_manager_instance

    result = await run_scraper(
        command=CommandEnum.HISTORIC,
        sport="football",
        leagues=["premier-league"],
        seasons=["2023"],
        markets=["1x2", "over_under"],
        max_pages=2,
        headless=True,
    )

    # Verify the flow
    sport_market_registrar_mock.register_all_markets.assert_called_once()
    scraper_mock.start_playwright.assert_called_once_with(
        headless=True,
        browser_user_agent=None,
        browser_locale_timezone=None,
        browser_timezone_id=None,
        proxy_manager=proxy_manager_instance,
    )

    scraper_mock.collect_historic_links.assert_awaited_once_with(
        sport="football", league="premier-league", season="2023", max_pages=2
    )
    scraper_mock.extract_match_odds.assert_awaited_once_with(
        match_links=["https://oddsportal.com/m1"],
        sport="football",
        markets=["1x2", "over_under"],
        scrape_odds_history=False,
        target_bookmaker=None,
        concurrent_scraping_task=3,
        preview_submarkets_only=False,
        bookies_filter=ANY,
        period=ANY,
        request_delay=ANY,
    )
    scraper_mock.stop_playwright.assert_called_once()
    assert result.success == [{"match_link": "https://oddsportal.com/m1", "season": "2023"}]
    assert result.combo_stats == [
        {"league": "premier-league", "season": "2023", "successful": 1, "failed": 0, "errored": False}
    ]


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_upcoming(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """Test run_scraper with upcoming_matches command."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock

    proxy_manager_instance = MagicMock()
    proxy_manager_instance.get_current_proxy.return_value = {"server": "test-proxy"}
    proxy_manager_mock.return_value = proxy_manager_instance

    result = await run_scraper(
        command=CommandEnum.UPCOMING_MATCHES,
        sport="basketball",
        date="2023-06-01",
        leagues=["nba"],
        markets=["1x2"],
        browser_user_agent="custom-agent",
        browser_locale_timezone="Europe/Paris",
        headless=False,
    )

    # Verify the flow
    scraper_mock.start_playwright.assert_called_once_with(
        headless=False,
        browser_user_agent="custom-agent",
        browser_locale_timezone="Europe/Paris",
        browser_timezone_id=None,
        proxy_manager=proxy_manager_instance,
    )

    scraper_mock.collect_upcoming_links.assert_awaited_once_with(
        sport="basketball",
        date="2023-06-01",
        league="nba",
        include_started=False,
        kickoff_within_hours=None,
        collect_kickoff=False,
    )
    scraper_mock.extract_match_odds.assert_awaited_once()
    assert scraper_mock.extract_match_odds.await_args.kwargs["match_links"] == ["https://oddsportal.com/m1"]
    assert result.stats.successful == 1


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_match_links(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """Test run_scraper with match_links."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock

    proxy_manager_instance = MagicMock()
    proxy_manager_instance.get_current_proxy.return_value = {"server": "test-proxy"}
    proxy_manager_mock.return_value = proxy_manager_instance

    match_links = ["https://oddsportal.com/match1", "https://oddsportal.com/match2"]

    result = await run_scraper(
        command=CommandEnum.HISTORIC,  # Doesn't matter for this test
        match_links=match_links,
        sport="tennis",
        markets=["1x2"],
        scrape_odds_history=True,
        target_bookmaker="bet365",
    )

    scraper_mock.scrape_matches.assert_called_once_with(
        match_links=match_links,
        sport="tennis",
        markets=["1x2"],
        scrape_odds_history=True,
        target_bookmaker="bet365",
        bookies_filter=ANY,
        period=ANY,
        request_delay=ANY,
        concurrent_scraping_task=ANY,
    )

    assert result == {"result": "match_data"}


@pytest.mark.asyncio
async def test_run_scraper_builds_multi_proxy_manager(monkeypatch):
    """run_scraper(proxy_url=<tuple>) must build a single ProxyManager in multi-proxy mode
    and pass it (not a proxy dict) to start_playwright (issue: multi-proxy rotation)."""
    from oddsharvester.core import scraper_app

    captured = {}

    class DummyScraper:
        def __init__(self, *a, **k):
            pass

        async def start_playwright(self, **kwargs):
            captured["proxy_manager"] = kwargs.get("proxy_manager")

        async def collect_upcoming_links(self, **kwargs):
            return ListingResult()

        async def stop_playwright(self):
            pass

    monkeypatch.setattr(scraper_app, "OddsPortalScraper", DummyScraper)

    await scraper_app.run_scraper(
        command=CommandEnum.UPCOMING_MATCHES,
        sport="football",
        date="20250101",
        markets=["1x2"],
        proxy_url=("http://a.example.com:1", "http://b.example.com:2"),
    )

    assert captured["proxy_manager"].is_multi_proxy() is True


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_upcoming_forwards_concurrency(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """run_scraper(concurrency_tasks=N) must forward concurrent_scraping_task=N to scrape_upcoming (issue #64)."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock
    proxy_manager_mock.return_value.get_current_proxy.return_value = None

    await run_scraper(
        command=CommandEnum.UPCOMING_MATCHES,
        sport="football",
        date="20260601",
        leagues=["premier-league"],
        markets=["1x2"],
        concurrency_tasks=10,
    )

    assert scraper_mock.extract_match_odds.await_args.kwargs["concurrent_scraping_task"] == 10


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_upcoming_forwards_include_started(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """run_scraper(include_started=True) must forward include_started=True to scrape_upcoming (issue #58)."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock
    proxy_manager_mock.return_value.get_current_proxy.return_value = None

    await run_scraper(
        command=CommandEnum.UPCOMING_MATCHES,
        sport="football",
        date="20260601",
        markets=["1x2"],
        include_started=True,
    )

    assert scraper_mock.collect_upcoming_links.await_args.kwargs["include_started"] is True


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_upcoming_forwards_kickoff_within_hours(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """run_scraper(kickoff_within_hours=N) must forward it to scrape_upcoming (issue #77)."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock
    proxy_manager_mock.return_value.get_current_proxy.return_value = None

    await run_scraper(
        command=CommandEnum.UPCOMING_MATCHES,
        sport="football",
        date="20260601",
        markets=["1x2"],
        kickoff_within_hours=6,
    )

    assert scraper_mock.collect_upcoming_links.await_args.kwargs["kickoff_within_hours"] == 6


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_upcoming_multi_league_forwards_kickoff_within_hours(
    registrar_mock, proxy_mock, playwright_mock, extractor_mock, scraper_cls_mock
):
    """The multi-league path must forward kickoff_within_hours to every league (issue #77)."""
    scraper_mock = scraper_cls_mock.return_value
    scraper_mock.start_playwright = AsyncMock()
    scraper_mock.stop_playwright = AsyncMock()
    scraper_mock.collect_upcoming_links = AsyncMock(return_value=ListingResult())

    await run_scraper(
        command="scrape_upcoming",
        sport="football",
        leagues=["england-premier-league", "spain-laliga"],
        kickoff_within_hours=3,
    )

    assert scraper_mock.collect_upcoming_links.await_count == 2
    assert all(c.kwargs["kickoff_within_hours"] == 3 for c in scraper_mock.collect_upcoming_links.await_args_list)


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_historic_forwards_concurrency(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """run_scraper(concurrency_tasks=N) must forward concurrent_scraping_task=N to scrape_historic (issue #64)."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock
    proxy_manager_mock.return_value.get_current_proxy.return_value = None

    await run_scraper(
        command=CommandEnum.HISTORIC,
        sport="football",
        leagues=["premier-league"],
        seasons=["2024"],
        markets=["1x2"],
        concurrency_tasks=7,
    )

    assert scraper_mock.extract_match_odds.await_args.kwargs["concurrent_scraping_task"] == 7


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
    scraper_mock.collect_historic_links = AsyncMock(return_value=ListingResult(rows=[{"match_link": "https://x/m1"}]))
    scraper_mock.extract_match_odds = AsyncMock()

    result = await run_scraper(
        command="scrape_historic",
        sport="football",
        leagues=["england-premier-league"],
        seasons=["2022-2023"],
        links_only=True,
    )

    scraper_mock.extract_match_odds.assert_not_awaited()
    assert result.success == [
        {"match_link": "https://x/m1", "sport": "football", "league": "england-premier-league", "season": "2022-2023"}
    ]


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
    scraper_mock.collect_historic_links = AsyncMock(
        side_effect=[
            ListingResult(rows=[{"match_link": "https://x/m1"}]),
            ListingResult(rows=[{"match_link": "https://x/m2"}]),
        ]
    )
    scraper_mock.extract_match_odds = AsyncMock()

    result = await run_scraper(
        command="scrape_historic",
        sport="football",
        leagues=["england-premier-league", "spain-laliga"],
        seasons=["2022-2023"],
        links_only=True,
    )

    assert scraper_mock.collect_historic_links.await_count == 2
    scraper_mock.extract_match_odds.assert_not_awaited()
    assert [row["league"] for row in result.success] == ["england-premier-league", "spain-laliga"]


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
    scraper_mock.collect_upcoming_links = AsyncMock(
        return_value=ListingResult(rows=[{"match_link": "https://x/m1", "kickoff_utc": None}])
    )
    scraper_mock.extract_match_odds = AsyncMock()

    result = await run_scraper(
        command="scrape_upcoming",
        sport="football",
        date="20991231",
        links_only=True,
    )

    assert scraper_mock.collect_upcoming_links.await_args.kwargs["collect_kickoff"] is True
    scraper_mock.extract_match_odds.assert_not_awaited()
    assert list(result.success[0].keys()) == ["match_link", "sport", "league", "date", "season", "kickoff_utc"]


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_match_links_forwards_concurrency(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """run_scraper(concurrency_tasks=N) must forward concurrent_scraping_task=N to scrape_matches (issue #64)."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock
    proxy_manager_mock.return_value.get_current_proxy.return_value = None

    await run_scraper(
        command=CommandEnum.UPCOMING_MATCHES,
        match_links=["https://oddsportal.com/m1", "https://oddsportal.com/m2"],
        sport="tennis",
        markets=["1x2"],
        concurrency_tasks=5,
    )

    assert scraper_mock.scrape_matches.call_args.kwargs.get("concurrent_scraping_task") == 5


@pytest.mark.asyncio
async def test_retry_scrape_success():
    """Test retry_scrape function with successful first attempt."""
    mock_func = AsyncMock(return_value={"data": "test"})

    result = await retry_scrape(mock_func, "arg1", kwarg1="test")

    mock_func.assert_called_once_with("arg1", kwarg1="test")
    assert result == {"data": "test"}


@pytest.mark.asyncio
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


@pytest.mark.asyncio
@patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_scrape_non_retryable_error(mock_sleep):
    """A non-retryable error is raised at once, as itself."""
    mock_func = AsyncMock(side_effect=ValueError("Invalid input"))

    with pytest.raises(ValueError, match="Invalid input"):
        await retry_scrape(mock_func, "arg1")

    mock_func.assert_called_once()
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock)
async def test_retry_scrape_reraises_the_last_error_when_retries_run_out(mock_sleep):
    """Exhausted retries surface the original exception instead of None, so callers can report it."""
    mock_func = AsyncMock(side_effect=Exception(f"Connection failed: {TRANSIENT_ERROR_KEYWORDS[0]}"))

    with pytest.raises(Exception, match=TRANSIENT_ERROR_KEYWORDS[0]):
        await retry_scrape(mock_func)

    assert mock_func.call_count == OPERATION_RETRY_MAX_ATTEMPTS
    assert mock_sleep.call_count == OPERATION_RETRY_MAX_ATTEMPTS - 1


@pytest.mark.asyncio
async def test_retry_scrape_reraises_the_original_exception_type():
    from oddsharvester.core.exceptions import PageNotFoundError

    error = PageNotFoundError("League page not found", url="https://www.oddsportal.com/football/x/y/results/")
    mock_func = AsyncMock(side_effect=error)

    with pytest.raises(PageNotFoundError) as excinfo:
        await retry_scrape(mock_func)

    assert excinfo.value is error


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_error_handling(sport_market_registrar_mock, proxy_manager_mock, scraper_cls_mock):
    """Test error handling in run_scraper."""
    scraper_mock = AsyncMock()
    scraper_mock.start_playwright = AsyncMock(side_effect=Exception("Playwright error"))
    scraper_mock.stop_playwright = AsyncMock()
    scraper_cls_mock.return_value = scraper_mock

    proxy_manager_instance = MagicMock()
    proxy_manager_instance.get_current_proxy.return_value = {"server": "test-proxy"}
    proxy_manager_mock.return_value = proxy_manager_instance

    result = await run_scraper(
        command=CommandEnum.HISTORIC, sport="football", leagues=["premier-league"], seasons=["2023"]
    )

    scraper_mock.stop_playwright.assert_called_once()
    assert result is None


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_logs_the_error_type_and_traceback(registrar_mock, proxy_mock, scraper_cls_mock, caplog):
    scraper_mock = AsyncMock()
    scraper_mock.start_playwright = AsyncMock(side_effect=RuntimeError("browser crashed"))
    scraper_mock.stop_playwright = AsyncMock()
    scraper_cls_mock.return_value = scraper_mock

    with caplog.at_level(logging.ERROR, logger="ScraperApp"):
        result = await run_scraper(
            command=CommandEnum.HISTORIC, sport="football", leagues=["premier-league"], seasons=["2023"]
        )

    assert result is None
    record = next(r for r in caplog.records if "browser crashed" in r.getMessage())
    assert "RuntimeError" in record.getMessage()
    assert record.exc_info is not None


@pytest.mark.asyncio
async def test_run_scraper_multiple_leagues_historic():
    """Test run_scraper with multiple leagues for historic command."""
    with (
        patch("oddsharvester.core.scraper_app.OddsPortalScraper") as scraper_cls_mock,
        patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor"),
        patch("oddsharvester.core.scraper_app.PlaywrightManager"),
        patch("oddsharvester.core.scraper_app.ProxyManager"),
        patch("oddsharvester.core.scraper_app.SportMarketRegistrar"),
        patch("oddsharvester.core.scraper_app._scrape_combos") as multi_scrape_mock,
    ):
        scraper_mock = MagicMock()
        scraper_mock.start_playwright = AsyncMock()
        scraper_mock.stop_playwright = AsyncMock()
        scraper_cls_mock.return_value = scraper_mock

        multi_scrape_mock.return_value = [{"combined": "data"}]

        result = await run_scraper(
            command=CommandEnum.HISTORIC,
            sport="football",
            leagues=["england-premier-league", "spain-primera-division"],
            seasons=["2023"],
            markets=["1x2"],
        )

        # Verify _scrape_combos was called for multiple leagues
        multi_scrape_mock.assert_called_once()
        call_args = multi_scrape_mock.call_args
        assert call_args.kwargs["combos"] == [("england-premier-league", "2023"), ("spain-primera-division", "2023")]
        assert call_args.kwargs["links_only"] is False
        assert call_args.kwargs["concurrency"] == 3

        assert result == [{"combined": "data"}]


# Separate test cases for validation errors
@pytest.mark.parametrize(
    ("command", "params", "error_message"),
    [
        (CommandEnum.HISTORIC, {}, "Both 'sport', 'league' and 'season' must be provided for historic scraping"),
        (
            CommandEnum.UPCOMING_MATCHES,
            {"sport": "football"},
            "A valid 'date' must be provided for upcoming matches scraping",
        ),
        ("invalid_command", {}, "Unknown command: invalid_command"),
    ],
)
def test_run_scraper_validation(command, params, error_message):
    """
    Test validation errors in run_scraper.

    This test directly extracts and checks validation logic without actually
    running the full function.
    """

    # Create a minimal version of run_scraper that only performs validation
    async def validate_only():
        if command == CommandEnum.HISTORIC:
            sport = params.get("sport")
            league = params.get("league")
            season = params.get("season")
            if not sport or not league or not season:
                raise ValueError("Both 'sport', 'league' and 'season' must be provided for historic scraping.")
        elif command == CommandEnum.UPCOMING_MATCHES:
            date = params.get("date")
            if not date:
                raise ValueError("A valid 'date' must be provided for upcoming matches scraping.")
        elif command not in (CommandEnum.HISTORIC, CommandEnum.UPCOMING_MATCHES):
            raise ValueError(f"Unknown command: {command}. Supported commands are 'upcoming-matches' and 'historic'.")

    # Run the validation function and check for the expected error
    with pytest.raises(ValueError) as exc_info:
        asyncio.run(validate_only())

    assert error_message in str(exc_info.value)


def test_run_scraper_accepts_local_kickoff_param():
    import inspect

    sig = inspect.signature(scraper_app.run_scraper)
    assert "local_kickoff" in sig.parameters
    assert sig.parameters["local_kickoff"].default is False


@pytest.mark.asyncio
async def test_run_scraper_forwards_local_kickoff(monkeypatch):
    captured = {}

    class FakeScraper:
        def __init__(self, *args, local_kickoff=False, **kwargs):
            captured["local_kickoff"] = local_kickoff

        async def start_playwright(self, **kwargs):
            raise RuntimeError("stop here")  # abort before real scraping

        async def stop_playwright(self):
            pass

    monkeypatch.setattr(scraper_app, "OddsPortalScraper", FakeScraper)

    await scraper_app.run_scraper(
        command="scrape_upcoming",
        sport="football",
        date="2025-01-15",
        local_kickoff=True,
    )
    assert captured["local_kickoff"] is True


@pytest.mark.asyncio
async def test_multi_league_historic_none_seasons_lists_each_league_with_season_none():
    """Regression: seasons=None on the multi-league historic path must still pass season=None
    to collect_historic_links (a required param), not omit it and error every combo (issue #78)."""
    with (
        patch("oddsharvester.core.scraper_app.OddsPortalScraper") as scraper_cls_mock,
        patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor"),
        patch("oddsharvester.core.scraper_app.PlaywrightManager"),
        patch("oddsharvester.core.scraper_app.ProxyManager"),
        patch("oddsharvester.core.scraper_app.SportMarketRegistrar"),
    ):
        scraper_mock = MagicMock()
        scraper_mock.start_playwright = AsyncMock()
        scraper_mock.stop_playwright = AsyncMock()
        scraper_mock.collect_historic_links = AsyncMock(return_value=ListingResult())
        scraper_cls_mock.return_value = scraper_mock

        result = await run_scraper(
            command=CommandEnum.HISTORIC,
            sport="football",
            leagues=["england-premier-league", "spain-laliga"],
            seasons=None,
        )

    assert scraper_mock.collect_historic_links.await_count == 2
    for call in scraper_mock.collect_historic_links.await_args_list:
        assert call.kwargs["season"] is None
    assert all(combo["errored"] is False for combo in result.combo_stats)


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_routes_live_command(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """The live command routes to scrape_live with the single league unwrapped."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock

    result = await run_scraper(command="scrape_live", sport="football", markets=["1x2"])

    scraper_mock.scrape_live.assert_awaited_once()
    kwargs = scraper_mock.scrape_live.await_args.kwargs
    assert kwargs["sport"] == "football"
    assert kwargs["league"] is None
    assert kwargs["markets"] == ["1x2"]
    assert result == {"result": "live_data"}


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_live_with_match_links_uses_scrape_live_not_scrape_matches(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """The generic match_links branch must not swallow the live command."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock

    await run_scraper(
        command="scrape_live",
        sport="football",
        match_links=["https://www.oddsportal.com/football/x/y/z-abc/"],
        markets=["1x2"],
    )

    scraper_mock.scrape_live.assert_awaited_once()
    scraper_mock.scrape_matches.assert_not_awaited()
    assert scraper_mock.scrape_live.await_args.kwargs["match_links"] == [
        "https://www.oddsportal.com/football/x/y/z-abc/"
    ]


@pytest.mark.asyncio
@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_live_requires_sport(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    market_extractor_mock,
    scraper_cls_mock,
    setup_mocks,
):
    """Live scraping without a sport has no listing to read; it must not silently succeed."""
    scraper_mock = setup_mocks["scraper_mock"]
    scraper_cls_mock.return_value = scraper_mock

    result = await run_scraper(command="scrape_live", sport=None, markets=["1x2"])

    assert result is None
    scraper_mock.scrape_live.assert_not_awaited()


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


@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_links_only_listing_failure_reaches_library_callers(
    registrar_mock, proxy_mock, playwright_mock, extractor_mock, scraper_cls_mock
):
    """resolve_events_b.py reads res.failed[0] to tell a failed listing from an empty league."""
    scraper_mock = scraper_cls_mock.return_value
    scraper_mock.start_playwright = AsyncMock()
    scraper_mock.stop_playwright = AsyncMock()
    scraper_mock.collect_historic_links = AsyncMock(side_effect=ValueError("Season page redirected"))

    result = await run_scraper(
        command=CommandEnum.HISTORIC,
        sport="football",
        leagues=["england-premier-league"],
        seasons=["2022-2023"],
        links_only=True,
    )

    assert result.success == []
    assert [f.error_type for f in result.failed] == [ErrorType.LISTING_PAGE]
    assert "ValueError: Season page redirected" in result.failed[0].error_message


async def test_scrape_combos_with_no_links_skips_the_odds_phase():
    collect = AsyncMock(return_value=_listing())
    scraper = MagicMock()
    scraper.extract_match_odds = AsyncMock()

    result = await _run_combos(collect, [("epl", None)], scraper=scraper)

    scraper.extract_match_odds.assert_not_called()
    assert result.success == []
    assert result.combo_stats == [{"league": "epl", "season": None, "successful": 0, "failed": 0, "errored": False}]


async def test_run_scraper_builds_combos_league_outer_season_inner():
    """Output stays grouped by league, then by season, deterministically."""
    with (
        patch("oddsharvester.core.scraper_app.OddsPortalScraper") as scraper_cls_mock,
        patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor"),
        patch("oddsharvester.core.scraper_app.PlaywrightManager"),
        patch("oddsharvester.core.scraper_app.ProxyManager"),
        patch("oddsharvester.core.scraper_app.SportMarketRegistrar"),
        patch("oddsharvester.core.scraper_app._scrape_combos", new_callable=AsyncMock) as combos_mock,
    ):
        scraper_mock = MagicMock()
        scraper_mock.start_playwright = AsyncMock()
        scraper_mock.stop_playwright = AsyncMock()
        scraper_cls_mock.return_value = scraper_mock

        await run_scraper(
            command=CommandEnum.HISTORIC,
            sport="football",
            leagues=["epl", "laliga"],
            seasons=["2020-2021", "2021-2022"],
        )

    assert combos_mock.await_args.kwargs["combos"] == [
        ("epl", "2020-2021"),
        ("epl", "2021-2022"),
        ("laliga", "2020-2021"),
        ("laliga", "2021-2022"),
    ]


async def test_run_scraper_single_league_goes_through_the_same_path():
    """One league is one combo: there is no separate direct-call path any more (issue #87)."""
    with (
        patch("oddsharvester.core.scraper_app.OddsPortalScraper") as scraper_cls_mock,
        patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor"),
        patch("oddsharvester.core.scraper_app.PlaywrightManager"),
        patch("oddsharvester.core.scraper_app.ProxyManager"),
        patch("oddsharvester.core.scraper_app.SportMarketRegistrar"),
        patch("oddsharvester.core.scraper_app._scrape_combos", new_callable=AsyncMock) as combos_mock,
    ):
        scraper_mock = MagicMock()
        scraper_mock.start_playwright = AsyncMock()
        scraper_mock.stop_playwright = AsyncMock()
        scraper_cls_mock.return_value = scraper_mock

        await run_scraper(command="scrape_upcoming", sport="football", date="20260601", concurrency_tasks=4)

    combos_mock.assert_awaited_once()
    assert combos_mock.await_args.kwargs["combos"] == [(None, None)]
    assert combos_mock.await_args.kwargs["concurrency"] == 4


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


@patch("oddsharvester.core.scraper_app.OddsPortalScraper")
@patch("oddsharvester.core.scraper_app.OddsPortalMarketExtractor")
@patch("oddsharvester.core.scraper_app.PlaywrightManager")
@patch("oddsharvester.core.scraper_app.ProxyManager")
@patch("oddsharvester.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_single_league_listing_failure_returns_an_errored_result(
    registrar_mock, proxy_mock, playwright_mock, extractor_mock, scraper_cls_mock
):
    """A failing single-league run returns an empty result flagged errored, not None; both CLIs exit 1 on it."""
    scraper_mock = scraper_cls_mock.return_value
    scraper_mock.start_playwright = AsyncMock()
    scraper_mock.stop_playwright = AsyncMock()
    scraper_mock.collect_upcoming_links = AsyncMock(side_effect=ValueError("Season page redirected"))
    scraper_mock.extract_match_odds = AsyncMock()

    result = await run_scraper(command="scrape_upcoming", sport="football", leagues=["england-premier-league"])

    assert isinstance(result, ScrapeResult)
    assert result.success == []
    assert result.combo_stats == [
        {"league": "england-premier-league", "season": None, "successful": 0, "failed": 0, "errored": True}
    ]
    scraper_mock.extract_match_odds.assert_not_awaited()
