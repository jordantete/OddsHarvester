from unittest.mock import AsyncMock, MagicMock, patch

from playwright.async_api import Browser, BrowserContext, Page
import pytest

from src.core.browser_helper import BrowserHelper
from src.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from src.core.odds_portal_scraper import OddsPortalScraper
from src.core.playwright_manager import PlaywrightManager


@pytest.fixture
def setup_scraper_mocks():
    """Setup common mocks for the OddsPortalScraper tests."""
    # Create mocks for dependencies
    playwright_manager_mock = MagicMock(spec=PlaywrightManager)
    browser_helper_mock = MagicMock(spec=BrowserHelper)
    market_extractor_mock = MagicMock(spec=OddsPortalMarketExtractor)

    # Setup page and context mocks
    page_mock = AsyncMock(spec=Page)
    context_mock = AsyncMock(spec=BrowserContext)
    browser_mock = AsyncMock(spec=Browser)

    # Configure playwright manager mock
    playwright_manager_mock.initialize = AsyncMock()
    playwright_manager_mock.cleanup = AsyncMock()
    playwright_manager_mock.page = page_mock
    playwright_manager_mock.context = context_mock
    playwright_manager_mock.browser = browser_mock

    # Configure the browser helper mock
    browser_helper_mock.dismiss_cookie_banner = AsyncMock()

    # Create scraper instance with mocks
    scraper = OddsPortalScraper(
        playwright_manager=playwright_manager_mock,
        browser_helper=browser_helper_mock,
        market_extractor=market_extractor_mock,
    )

    return {
        "scraper": scraper,
        "playwright_manager_mock": playwright_manager_mock,
        "browser_helper_mock": browser_helper_mock,
        "market_extractor_mock": market_extractor_mock,
        "page_mock": page_mock,
        "context_mock": context_mock,
        "browser_mock": browser_mock,
    }


@pytest.mark.asyncio
async def test_start_playwright(setup_scraper_mocks):
    """Test initializing Playwright with various options."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    # Test with default parameters
    await scraper.start_playwright()
    mocks["playwright_manager_mock"].initialize.assert_called_once_with(
        headless=True, user_agent=None, locale=None, timezone_id=None, proxy=None
    )

    # Reset the mock and test with custom parameters
    mocks["playwright_manager_mock"].initialize.reset_mock()

    custom_user_agent = "Mozilla/5.0 CustomAgent"
    custom_locale = "en-US"
    custom_timezone = "Europe/London"
    proxy_config = {"server": "http://proxy.example.com:8080"}

    await scraper.start_playwright(
        headless=False,
        browser_user_agent=custom_user_agent,
        browser_locale_timezone=custom_locale,
        browser_timezone_id=custom_timezone,
        proxy=proxy_config,
    )

    mocks["playwright_manager_mock"].initialize.assert_called_once_with(
        headless=False,
        user_agent=custom_user_agent,
        locale=custom_locale,
        timezone_id=custom_timezone,
        proxy=proxy_config,
    )


@pytest.mark.asyncio
async def test_stop_playwright(setup_scraper_mocks):
    """Test stopping Playwright."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    await scraper.stop_playwright()
    mocks["playwright_manager_mock"].cleanup.assert_called_once()


@pytest.mark.asyncio
@patch("src.core.odds_portal_scraper.URLBuilder")
async def test_scrape_historic(url_builder_mock, setup_scraper_mocks):
    """Test scraping historic odds data."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock the URLBuilder
    url_builder_mock.get_historic_matches_url.return_value = (
        "https://oddsportal.com/football/england/premier-league-2023"
    )

    # Mock the _get_pagination_info and _collect_match_links methods
    scraper._get_pagination_info = AsyncMock(return_value=[1, 2])
    scraper._collect_match_links = AsyncMock(
        return_value=["https://oddsportal.com/match1", "https://oddsportal.com/match2"]
    )
    scraper.extract_match_odds = AsyncMock(return_value=[{"match": "data1"}, {"match": "data2"}])
    scraper._prepare_page_for_scraping = AsyncMock()

    # Call the method under test
    result = await scraper.scrape_historic(
        sport="football",
        league="premier-league",
        season="2023",
        markets=["1x2"],
        scrape_odds_history=True,
        target_bookmaker="bet365",
        max_pages=2,
    )

    # Verify the interactions
    url_builder_mock.get_historic_matches_url.assert_called_once_with(
        sport="football", league="premier-league", season="2023"
    )
    page_mock.goto.assert_called_once()
    scraper._prepare_page_for_scraping.assert_called_once_with(page=page_mock)
    scraper._get_pagination_info.assert_called_once_with(page=page_mock, max_pages=2)
    scraper._collect_match_links.assert_called_once_with(
        base_url="https://oddsportal.com/football/england/premier-league-2023", pages_to_scrape=[1, 2]
    )
    scraper.extract_match_odds.assert_called_once_with(
        sport="football",
        match_links=["https://oddsportal.com/match1", "https://oddsportal.com/match2"],
        markets=["1x2"],
        scrape_odds_history=True,
        target_bookmaker="bet365",
    )

    # Verify the result
    assert result == [{"match": "data1"}, {"match": "data2"}]


@pytest.mark.asyncio
@patch("src.core.odds_portal_scraper.URLBuilder")
async def test_scrape_upcoming(url_builder_mock, setup_scraper_mocks):
    """Test scraping upcoming matches odds data."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock the URLBuilder
    url_builder_mock.get_upcoming_matches_url.return_value = (
        "https://oddsportal.com/football/england/premier-league/matches/20230601"
    )

    # Mock methods
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper.extract_match_links = AsyncMock(
        return_value=["https://oddsportal.com/match1", "https://oddsportal.com/match2"]
    )
    scraper.extract_match_odds = AsyncMock(return_value=[{"match": "data1"}, {"match": "data2"}])

    # Call the method under test
    result = await scraper.scrape_upcoming(
        sport="football",
        date="2023-06-01",
        league="premier-league",
        markets=["1x2", "over_under"],
        scrape_odds_history=False,
    )

    # Verify the interactions
    url_builder_mock.get_upcoming_matches_url.assert_called_once_with(
        sport="football", date="2023-06-01", league="premier-league"
    )
    page_mock.goto.assert_called_once()
    scraper._prepare_page_for_scraping.assert_called_once_with(page=page_mock)
    scraper.extract_match_links.assert_called_once_with(page=page_mock)
    scraper.extract_match_odds.assert_called_once_with(
        sport="football",
        match_links=["https://oddsportal.com/match1", "https://oddsportal.com/match2"],
        markets=["1x2", "over_under"],
        scrape_odds_history=False,
        target_bookmaker=None,
    )

    # Verify the result
    assert result == [{"match": "data1"}, {"match": "data2"}]


@pytest.mark.asyncio
@patch("src.core.odds_portal_scraper.ODDSPORTAL_BASE_URL", "https://oddsportal.com")
async def test_scrape_matches(setup_scraper_mocks):
    """Test scraping specific match links."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock methods
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper.extract_match_odds = AsyncMock(return_value=[{"match": "data1"}, {"match": "data2"}])

    match_links = ["https://oddsportal.com/match1", "https://oddsportal.com/match2"]

    # Call the method under test
    result = await scraper.scrape_matches(
        match_links=match_links, sport="tennis", markets=["1x2"], scrape_odds_history=True, target_bookmaker="bwin"
    )

    # Verify the interactions
    page_mock.goto.assert_called_once_with("https://oddsportal.com", timeout=20000, wait_until="domcontentloaded")
    scraper._prepare_page_for_scraping.assert_called_once_with(page=page_mock)
    scraper.extract_match_odds.assert_called_once_with(
        sport="tennis",
        match_links=match_links,
        markets=["1x2"],
        scrape_odds_history=True,
        target_bookmaker="bwin",
        concurrent_scraping_task=2,
    )

    # Verify the result
    assert result == [{"match": "data1"}, {"match": "data2"}]


@pytest.mark.asyncio
async def test_prepare_page_for_scraping(setup_scraper_mocks):
    """Test preparing the page for scraping."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock methods
    scraper.set_odds_format = AsyncMock()

    # Call the method under test
    await scraper._prepare_page_for_scraping(page=page_mock)

    # Verify the interactions
    scraper.set_odds_format.assert_called_once_with(page=page_mock)
    mocks["browser_helper_mock"].dismiss_cookie_banner.assert_called_once_with(page=page_mock)


@pytest.mark.asyncio
async def test_get_pagination_info(setup_scraper_mocks):
    """Test extracting pagination information."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock the pagination links
    pagination_link1 = AsyncMock()
    pagination_link1.inner_text = AsyncMock(return_value="1")

    pagination_link2 = AsyncMock()
    pagination_link2.inner_text = AsyncMock(return_value="2")

    pagination_link3 = AsyncMock()
    pagination_link3.inner_text = AsyncMock(return_value="Next")

    page_mock.query_selector_all.return_value = [pagination_link1, pagination_link2, pagination_link3]

    # Test with no max_pages
    result = await scraper._get_pagination_info(page=page_mock, max_pages=None)
    page_mock.query_selector_all.assert_called_with("a.pagination-link:not([rel='next'])")
    assert result == [1, 2]

    # Test with max_pages=1
    result = await scraper._get_pagination_info(page=page_mock, max_pages=1)
    assert result == [1]

    # Test with no pagination
    page_mock.query_selector_all.return_value = []
    result = await scraper._get_pagination_info(page=page_mock, max_pages=None)
    assert result == [1]


@pytest.mark.asyncio
async def test_collect_match_links(setup_scraper_mocks):
    """Test collecting match links from multiple pages."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    context_mock = mocks["context_mock"]

    # Create a mock tab
    tab_mock = AsyncMock(spec=Page)
    tab_mock.goto = AsyncMock()
    tab_mock.wait_for_timeout = AsyncMock()
    tab_mock.close = AsyncMock()
    context_mock.new_page.return_value = tab_mock

    # Mock extract_match_links method
    scraper.extract_match_links = AsyncMock()
    scraper.extract_match_links.side_effect = [
        ["https://oddsportal.com/match1", "https://oddsportal.com/match2"],
        ["https://oddsportal.com/match2", "https://oddsportal.com/match3"],
    ]

    # Call the method under test
    result = await scraper._collect_match_links(
        base_url="https://oddsportal.com/football/england/premier-league-2023", pages_to_scrape=[1, 2]
    )

    # Verify the interactions
    assert context_mock.new_page.call_count == 2
    assert tab_mock.goto.call_count == 2
    assert tab_mock.wait_for_timeout.call_count == 2
    assert tab_mock.close.call_count == 2
    assert scraper.extract_match_links.call_count == 2

    # Verify the result (should be unique links)
    assert sorted(result) == sorted(
        ["https://oddsportal.com/match1", "https://oddsportal.com/match2", "https://oddsportal.com/match3"]
    )


@pytest.mark.asyncio
async def test_collect_match_links_error_handling(setup_scraper_mocks):
    """Test error handling in collect_match_links method."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    context_mock = mocks["context_mock"]

    # Create a mock tab
    tab_mock = AsyncMock(spec=Page)
    tab_mock.goto = AsyncMock()
    tab_mock.wait_for_timeout = AsyncMock()
    tab_mock.close = AsyncMock()
    context_mock.new_page.return_value = tab_mock

    # Mock extract_match_links method with error on second page
    scraper.extract_match_links = AsyncMock()
    scraper.extract_match_links.side_effect = [["https://oddsportal.com/match1"], Exception("Page error")]

    # Call the method under test
    result = await scraper._collect_match_links(
        base_url="https://oddsportal.com/football/england/premier-league-2023", pages_to_scrape=[1, 2]
    )

    # Verify the result still contains successful page links
    assert result == ["https://oddsportal.com/match1"]
    assert tab_mock.close.call_count == 2  # Should still close tabs even after error
