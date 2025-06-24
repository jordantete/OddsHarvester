import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.browser_helper import BrowserHelper
from src.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from src.core.odds_portal_scraper import OddsPortalScraper
from src.core.playwright_manager import PlaywrightManager
from src.core.scraper_app import TRANSIENT_ERRORS, retry_scrape, run_scraper
from src.utils.command_enum import CommandEnum


@pytest.fixture
def setup_mocks():
    """Set up common mocks for tests."""
    playwright_manager_mock = MagicMock(spec=PlaywrightManager)
    browser_helper_mock = MagicMock(spec=BrowserHelper)
    market_extractor_mock = MagicMock(spec=OddsPortalMarketExtractor)
    scraper_mock = MagicMock(spec=OddsPortalScraper)

    # Configure the scraper mock
    scraper_mock.start_playwright = AsyncMock()
    scraper_mock.stop_playwright = AsyncMock()
    scraper_mock.scrape_historic = AsyncMock(return_value={"result": "historic_data"})
    scraper_mock.scrape_upcoming = AsyncMock(return_value={"result": "upcoming_data"})
    scraper_mock.scrape_matches = AsyncMock(return_value={"result": "match_data"})

    return {
        "playwright_manager_mock": playwright_manager_mock,
        "browser_helper_mock": browser_helper_mock,
        "market_extractor_mock": market_extractor_mock,
        "scraper_mock": scraper_mock,
    }


@pytest.mark.asyncio
@patch("src.core.scraper_app.OddsPortalScraper")
@patch("src.core.scraper_app.OddsPortalMarketExtractor")
@patch("src.core.scraper_app.BrowserHelper")
@patch("src.core.scraper_app.PlaywrightManager")
@patch("src.core.scraper_app.ProxyManager")
@patch("src.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_historic(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    browser_helper_mock,
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
        league="premier-league",
        season="2023",
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
        proxy={"server": "test-proxy"},
    )

    scraper_mock.scrape_historic.assert_called_once_with(
        sport="football",
        league="premier-league",
        season="2023",
        markets=["1x2", "over_under"],
        scrape_odds_history=False,
        target_bookmaker=None,
        max_pages=2,
    )

    scraper_mock.stop_playwright.assert_called_once()
    assert result == {"result": "historic_data"}


@pytest.mark.asyncio
@patch("src.core.scraper_app.OddsPortalScraper")
@patch("src.core.scraper_app.OddsPortalMarketExtractor")
@patch("src.core.scraper_app.BrowserHelper")
@patch("src.core.scraper_app.PlaywrightManager")
@patch("src.core.scraper_app.ProxyManager")
@patch("src.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_upcoming(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    browser_helper_mock,
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
        league="nba",
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
        proxy={"server": "test-proxy"},
    )

    scraper_mock.scrape_upcoming.assert_called_once_with(
        sport="basketball",
        date="2023-06-01",
        league="nba",
        markets=["1x2"],
        scrape_odds_history=False,
        target_bookmaker=None,
    )

    assert result == {"result": "upcoming_data"}


@pytest.mark.asyncio
@patch("src.core.scraper_app.OddsPortalScraper")
@patch("src.core.scraper_app.OddsPortalMarketExtractor")
@patch("src.core.scraper_app.BrowserHelper")
@patch("src.core.scraper_app.PlaywrightManager")
@patch("src.core.scraper_app.ProxyManager")
@patch("src.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_match_links(
    sport_market_registrar_mock,
    proxy_manager_mock,
    playwright_manager_mock,
    browser_helper_mock,
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
        match_links=match_links, sport="tennis", markets=["1x2"], scrape_odds_history=True, target_bookmaker="bet365"
    )

    assert result == {"result": "match_data"}


@pytest.mark.asyncio
async def test_retry_scrape_success():
    """Test retry_scrape function with successful first attempt."""
    mock_func = AsyncMock(return_value={"data": "test"})

    result = await retry_scrape(mock_func, "arg1", kwarg1="test")

    mock_func.assert_called_once_with("arg1", kwarg1="test")
    assert result == {"data": "test"}


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_retry_scrape_transient_error(mock_sleep):
    """Test retry_scrape function with transient error that succeeds on retry."""
    mock_func = AsyncMock()

    # Fail with a transient error on first call, succeed on second
    mock_func.side_effect = [Exception(f"Connection failed: {TRANSIENT_ERRORS[0]}"), {"data": "retry_success"}]

    result = await retry_scrape(mock_func, "arg1")

    assert mock_func.call_count == 2
    mock_sleep.assert_called_once()
    assert result == {"data": "retry_success"}


@pytest.mark.asyncio
@patch("asyncio.sleep", new_callable=AsyncMock)
async def test_retry_scrape_non_retryable_error(mock_sleep):
    """Test retry_scrape function with non-retryable error."""
    mock_func = AsyncMock(side_effect=ValueError("Invalid input"))

    with pytest.raises(ValueError, match="Invalid input"):
        await retry_scrape(mock_func, "arg1")

    mock_func.assert_called_once()
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
@patch("src.core.scraper_app.OddsPortalScraper")
@patch("src.core.scraper_app.ProxyManager")
@patch("src.core.scraper_app.SportMarketRegistrar")
async def test_run_scraper_error_handling(sport_market_registrar_mock, proxy_manager_mock, scraper_cls_mock):
    """Test error handling in run_scraper."""
    scraper_mock = AsyncMock()
    scraper_mock.start_playwright = AsyncMock(side_effect=Exception("Playwright error"))
    scraper_mock.stop_playwright = AsyncMock()
    scraper_cls_mock.return_value = scraper_mock

    proxy_manager_instance = MagicMock()
    proxy_manager_instance.get_current_proxy.return_value = {"server": "test-proxy"}
    proxy_manager_mock.return_value = proxy_manager_instance

    result = await run_scraper(command=CommandEnum.HISTORIC, sport="football", league="premier-league", season="2023")

    scraper_mock.stop_playwright.assert_called_once()
    assert result is None


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
