from datetime import date
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from playwright.async_api import Browser, BrowserContext, Page
import pytest

from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import LinkCollectionResult, OddsPortalScraper
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.scrape_result import ScrapeResult, ScrapeStats
from oddsharvester.utils.constants import GOTO_TIMEOUT_LONG_MS, MAX_PAGINATION_PAGES
from oddsharvester.utils.proxy_manager import ProxyManager


@pytest.fixture
def setup_scraper_mocks():
    """Setup common mocks for the OddsPortalScraper tests."""
    # Create mocks for dependencies
    playwright_manager_mock = MagicMock(spec=PlaywrightManager)
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

    cookie_dismisser_mock = AsyncMock()

    # Create scraper instance with mocks
    scraper = OddsPortalScraper(
        playwright_manager=playwright_manager_mock,
        market_extractor=market_extractor_mock,
        scroller=AsyncMock(),
        cookie_dismisser=cookie_dismisser_mock,
        selection_manager=AsyncMock(),
    )

    return {
        "scraper": scraper,
        "playwright_manager_mock": playwright_manager_mock,
        "market_extractor_mock": market_extractor_mock,
        "cookie_dismisser_mock": cookie_dismisser_mock,
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
        headless=True, user_agent=None, locale=None, timezone_id=None, proxy_manager=None
    )

    # Reset the mock and test with custom parameters
    mocks["playwright_manager_mock"].initialize.reset_mock()

    custom_user_agent = "Mozilla/5.0 CustomAgent"
    custom_locale = "en-US"
    custom_timezone = "Europe/London"
    proxy_manager = ProxyManager(proxy_urls=["http://proxy.example.com:8080"])

    await scraper.start_playwright(
        headless=False,
        browser_user_agent=custom_user_agent,
        browser_locale_timezone=custom_locale,
        browser_timezone_id=custom_timezone,
        proxy_manager=proxy_manager,
    )

    mocks["playwright_manager_mock"].initialize.assert_called_once_with(
        headless=False,
        user_agent=custom_user_agent,
        locale=custom_locale,
        timezone_id=custom_timezone,
        proxy_manager=proxy_manager,
    )


@pytest.mark.asyncio
async def test_stop_playwright(setup_scraper_mocks):
    """Test stopping Playwright."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    await scraper.stop_playwright()
    mocks["playwright_manager_mock"].cleanup.assert_called_once()


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
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
    link_result = LinkCollectionResult(
        links=["https://oddsportal.com/match1", "https://oddsportal.com/match2"],
        successful_pages=2,
        failed_pages=[],
    )
    scraper._collect_match_links = AsyncMock(return_value=link_result)

    # Mock extract_match_odds to return ScrapeResult
    mock_scrape_result = ScrapeResult(
        success=[{"match": "data1"}, {"match": "data2"}],
        failed=[],
        partial=[],
        stats=ScrapeStats(total_urls=2, successful=2, failed=0, partial=0),
    )
    scraper.extract_match_odds = AsyncMock(return_value=mock_scrape_result)
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
        sport="football", league="premier-league", season="2023", base_url=None
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
        concurrent_scraping_task=ANY,
        preview_submarkets_only=False,
        bookies_filter=ANY,
        period=ANY,
        request_delay=ANY,
    )

    # Verify the result is a ScrapeResult
    assert isinstance(result, ScrapeResult)
    assert len(result.success) == 2
    assert result.stats.successful == 2


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


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
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

    # Mock extract_match_odds to return ScrapeResult
    mock_scrape_result = ScrapeResult(
        success=[{"match": "data1"}, {"match": "data2"}],
        failed=[],
        partial=[],
        stats=ScrapeStats(total_urls=2, successful=2, failed=0, partial=0),
    )
    scraper.extract_match_odds = AsyncMock(return_value=mock_scrape_result)

    # Call the method under test
    result = await scraper.scrape_upcoming(
        sport="football",
        date="20260601",
        league="premier-league",
        markets=["1x2", "over_under"],
        scrape_odds_history=False,
    )

    # Verify the interactions
    url_builder_mock.get_upcoming_matches_url.assert_called_once_with(
        sport="football", date="20260601", league="premier-league", base_url=None
    )
    page_mock.goto.assert_called_once()
    scraper._prepare_page_for_scraping.assert_called_once_with(page=page_mock)
    scraper.extract_match_links.assert_called_once()
    _, extract_kwargs = scraper.extract_match_links.call_args
    assert extract_kwargs["page"] is page_mock
    assert extract_kwargs["date_filter"] == date(2026, 6, 1)
    scraper.extract_match_odds.assert_called_once_with(
        sport="football",
        match_links=["https://oddsportal.com/match1", "https://oddsportal.com/match2"],
        markets=["1x2", "over_under"],
        scrape_odds_history=False,
        target_bookmaker=None,
        concurrent_scraping_task=ANY,
        preview_submarkets_only=False,
        bookies_filter=ANY,
        period=ANY,
        request_delay=ANY,
    )

    # Verify the result is a ScrapeResult
    assert isinstance(result, ScrapeResult)
    assert len(result.success) == 2
    assert result.stats.successful == 2


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


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.ODDSPORTAL_BASE_URL", "https://oddsportal.com")
async def test_scrape_matches(setup_scraper_mocks):
    """Test scraping specific match links."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock methods
    scraper._prepare_page_for_scraping = AsyncMock()

    # Mock extract_match_odds to return ScrapeResult
    mock_scrape_result = ScrapeResult(
        success=[{"match": "data1"}, {"match": "data2"}],
        failed=[],
        partial=[],
        stats=ScrapeStats(total_urls=2, successful=2, failed=0, partial=0),
    )
    scraper.extract_match_odds = AsyncMock(return_value=mock_scrape_result)

    match_links = ["https://oddsportal.com/match1", "https://oddsportal.com/match2"]

    # Call the method under test
    result = await scraper.scrape_matches(
        match_links=match_links, sport="tennis", markets=["1x2"], scrape_odds_history=True, target_bookmaker="bwin"
    )

    # Verify the interactions
    page_mock.goto.assert_called_once_with(
        "https://oddsportal.com", timeout=GOTO_TIMEOUT_LONG_MS, wait_until="domcontentloaded"
    )
    scraper._prepare_page_for_scraping.assert_called_once_with(page=page_mock)
    scraper.extract_match_odds.assert_called_once_with(
        sport="tennis",
        match_links=match_links,
        markets=["1x2"],
        scrape_odds_history=True,
        target_bookmaker="bwin",
        concurrent_scraping_task=3,
        preview_submarkets_only=False,
        bookies_filter=ANY,
        period=ANY,
        request_delay=ANY,
    )

    # Verify the result is a ScrapeResult
    assert isinstance(result, ScrapeResult)
    assert len(result.success) == 2
    assert result.stats.successful == 2


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_upcoming_forwards_concurrent_scraping_task(url_builder_mock, setup_scraper_mocks):
    """scrape_upcoming must forward concurrent_scraping_task to extract_match_odds (issue #64)."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_upcoming_matches_url.return_value = "https://oddsportal.com/football/matches/20260601"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper.extract_match_links = AsyncMock(return_value=["https://oddsportal.com/m1"])
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_upcoming(sport="football", date="20260601", concurrent_scraping_task=10)

    assert scraper.extract_match_odds.call_args.kwargs.get("concurrent_scraping_task") == 10


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_historic_forwards_concurrent_scraping_task(url_builder_mock, setup_scraper_mocks):
    """scrape_historic must forward concurrent_scraping_task to extract_match_odds (issue #64)."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_historic_matches_url.return_value = "https://oddsportal.com/football/england/premier-league"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper._get_pagination_info = AsyncMock(return_value=[1])
    scraper._collect_match_links = AsyncMock(
        return_value=LinkCollectionResult(links=["https://oddsportal.com/m1"], successful_pages=1, failed_pages=[])
    )
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_historic(sport="football", league="premier-league", season="2024", concurrent_scraping_task=7)

    assert scraper.extract_match_odds.call_args.kwargs.get("concurrent_scraping_task") == 7


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
    mocks["cookie_dismisser_mock"].dismiss.assert_called_once_with(page=page_mock)


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
async def test_get_pagination_info_max_pages_overrides_safety_cap(setup_scraper_mocks):
    """When --max-pages exceeds MAX_PAGINATION_PAGES, the user value is respected."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    total = MAX_PAGINATION_PAGES + 20
    links = []
    for i in range(1, total + 1):
        link = AsyncMock()
        link.inner_text = AsyncMock(return_value=str(i))
        links.append(link)

    page_mock.query_selector_all.return_value = links

    # Without max_pages: safety cap applies
    result = await scraper._get_pagination_info(page=page_mock, max_pages=None)
    assert len(result) == MAX_PAGINATION_PAGES

    # With max_pages > safety cap: user value wins
    result = await scraper._get_pagination_info(page=page_mock, max_pages=total)
    assert len(result) == total
    assert result == list(range(1, total + 1))


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

    # Verify the result is LinkCollectionResult with unique links
    assert isinstance(result, LinkCollectionResult)
    assert sorted(result.links) == sorted(
        ["https://oddsportal.com/match1", "https://oddsportal.com/match2", "https://oddsportal.com/match3"]
    )
    assert result.successful_pages == 2
    assert result.failed_pages == []


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

    # Verify the result is LinkCollectionResult with successful page links and tracked failure
    assert isinstance(result, LinkCollectionResult)
    assert result.links == ["https://oddsportal.com/match1"]
    assert result.successful_pages == 1
    assert result.failed_pages == [2]
    assert tab_mock.close.call_count == 2  # Should still close tabs even after error


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


class TestFillPaginationGaps:
    """Tests for _fill_pagination_gaps behavior."""

    @pytest.fixture
    def scraper(self, setup_scraper_mocks):
        return setup_scraper_mocks["scraper"]

    def test_single_page(self, scraper):
        """Single page returns as-is."""
        assert scraper._fill_pagination_gaps([1]) == [1]

    def test_empty_list(self, scraper):
        """Empty list returns as-is."""
        assert scraper._fill_pagination_gaps([]) == []

    def test_consecutive_pages(self, scraper):
        """Consecutive pages are returned sorted."""
        assert scraper._fill_pagination_gaps([3, 1, 2]) == [1, 2, 3]

    def test_gap_filling(self, scraper):
        """Gaps between discovered pages are filled (OddsPortal ellipsis)."""
        result = scraper._fill_pagination_gaps([1, 2, 3, 27])
        assert result == list(range(1, 28))

    def test_deduplication(self, scraper):
        """Duplicate pages are deduplicated via max()."""
        assert scraper._fill_pagination_gaps([1, 2, 2, 3, 3]) == [1, 2, 3]

    def test_large_page_list(self, scraper):
        """Large page lists are returned in full (cap is applied in _get_pagination_info)."""
        pages = list(range(1, MAX_PAGINATION_PAGES + 20))
        result = scraper._fill_pagination_gaps(pages)
        assert result == pages

    def test_under_safety_cap(self, scraper):
        """Pages under the safety cap are returned in full."""
        pages = list(range(1, 11))
        result = scraper._fill_pagination_gaps(pages)
        assert result == list(range(1, 11))
