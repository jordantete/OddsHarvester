from datetime import date
import logging
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from playwright.async_api import Browser, BrowserContext, Page
import pytest

from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import LinkCollectionResult, OddsPortalScraper
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.scrape_result import ErrorType, ScrapeResult, ScrapeStats
from oddsharvester.utils.constants import GOTO_TIMEOUT_LONG_MS, MAX_PAGINATION_PAGES, RESULTS_PAGE_SIZE
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
        base_url="https://oddsportal.com/football/england/premier-league-2023",
        pages_to_scrape=[1, 2],
        page_limit=2,
        max_pages=2,
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
    assert list(result.success[0].keys()) == ["match_link", "sport", "league", "season"]
    assert [f.url for f in result.failed] == [f"{base}#page/3"]
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
    scraper.extract_match_rows = AsyncMock(
        return_value=[
            {"match_link": "https://oddsportal.com/match1", "kickoff_utc": None},
            {"match_link": "https://oddsportal.com/match2", "kickoff_utc": None},
        ]
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
    scraper.extract_match_rows.assert_called_once()
    _, extract_kwargs = scraper.extract_match_rows.call_args
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
    """links_only=True returns link rows with a date column; league may be None.

    `season` is always present (None here) so every row of every command carries
    the column. `kickoff_utc` is last and always present (issue #81).
    """
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_upcoming_matches_url.return_value = "https://oddsportal.com/matches/football/20260720/"
    scraper.extract_match_rows = AsyncMock(
        return_value=[{"match_link": "https://oddsportal.com/m1", "kickoff_utc": "2026-07-20 18:30:00 UTC"}]
    )
    scraper.extract_match_odds = AsyncMock()
    scraper._prepare_page_for_scraping = AsyncMock()

    result = await scraper.scrape_upcoming(sport="football", date="20260720", league=None, links_only=True)

    scraper.extract_match_odds.assert_not_called()
    assert result.success == [
        {
            "match_link": "https://oddsportal.com/m1",
            "sport": "football",
            "league": None,
            "date": "20260720",
            "season": None,
            "kickoff_utc": "2026-07-20 18:30:00 UTC",
        }
    ]
    assert list(result.success[0].keys()) == [
        "match_link",
        "sport",
        "league",
        "date",
        "season",
        "kickoff_utc",
    ]
    assert result.failed == []
    assert result.stats.successful == 1
    assert result.stats.total_urls == 1


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_upcoming_links_only_keeps_the_column_when_kickoff_is_unknown(
    url_builder_mock, setup_scraper_mocks
):
    """A null kickoff must still occupy the column, or CSV writing raises (issue #81)."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_upcoming_matches_url.return_value = "https://oddsportal.com/matches/football/20260720/"
    scraper.extract_match_rows = AsyncMock(
        return_value=[
            {"match_link": "https://oddsportal.com/m1", "kickoff_utc": "2026-07-20 18:30:00 UTC"},
            {"match_link": "https://oddsportal.com/m2", "kickoff_utc": None},
        ]
    )
    scraper.extract_match_odds = AsyncMock()
    scraper._prepare_page_for_scraping = AsyncMock()

    result = await scraper.scrape_upcoming(sport="football", date="20260720", league=None, links_only=True)

    assert [row["kickoff_utc"] for row in result.success] == ["2026-07-20 18:30:00 UTC", None]
    assert all("kickoff_utc" in row for row in result.success)


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_upcoming_requests_kickoff_only_in_links_only_mode(url_builder_mock, setup_scraper_mocks):
    """Odds runs get the match date from the match page, so they pay nothing here."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_upcoming_matches_url.return_value = "https://oddsportal.com/matches/football/20260720/"
    scraper.extract_match_rows = AsyncMock(
        return_value=[{"match_link": "https://oddsportal.com/m1", "kickoff_utc": None}]
    )
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())
    scraper._prepare_page_for_scraping = AsyncMock()

    await scraper.scrape_upcoming(sport="football", date="20260720", links_only=False)

    assert scraper.extract_match_rows.call_args.kwargs.get("collect_kickoff") is False


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
    scraper.extract_match_rows = AsyncMock(
        return_value=[{"match_link": "https://oddsportal.com/m1", "kickoff_utc": None}]
    )
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_upcoming(sport="football", date="20260601", concurrent_scraping_task=10)

    assert scraper.extract_match_odds.call_args.kwargs.get("concurrent_scraping_task") == 10


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_upcoming_forwards_kickoff_within_hours(url_builder_mock, setup_scraper_mocks):
    """scrape_upcoming must forward kickoff_within_hours to extract_match_rows (issue #77)."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_upcoming_matches_url.return_value = "https://oddsportal.com/football/matches/20260601"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper.extract_match_rows = AsyncMock(
        return_value=[{"match_link": "https://oddsportal.com/m1", "kickoff_utc": None}]
    )
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_upcoming(sport="football", date="20260601", kickoff_within_hours=6)

    assert scraper.extract_match_rows.call_args.kwargs.get("kickoff_within_hours") == 6


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
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
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
    """_get_pagination_info returns a floor: gaps filled, capped, never a verdict."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[1, 3])

    assert await scraper._get_pagination_info(page=page_mock, max_pages=None) == [1, 2, 3]
    assert await scraper._get_pagination_info(page=page_mock, max_pages=1) == [1]

    scraper.pagination_walker.read_widget = AsyncMock(return_value=[])
    assert await scraper._get_pagination_info(page=page_mock, max_pages=None) == [1]


@pytest.mark.asyncio
async def test_get_pagination_info_max_pages_overrides_safety_cap(setup_scraper_mocks):
    """When --max-pages exceeds MAX_PAGINATION_PAGES, the user value is respected."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    total = MAX_PAGINATION_PAGES + 20
    scraper.pagination_walker.read_widget = AsyncMock(return_value=list(range(1, total + 1)))

    # Without max_pages: safety cap applies
    result = await scraper._get_pagination_info(page=page_mock, max_pages=None)
    assert len(result) == MAX_PAGINATION_PAGES

    # With max_pages > safety cap: user value wins
    result = await scraper._get_pagination_info(page=page_mock, max_pages=total)
    assert len(result) == total
    assert result == list(range(1, total + 1))


def full_page(prefix: str) -> list[str]:
    """A listing page that is not the last one renders RESULTS_PAGE_SIZE links (issue #78)."""
    return [f"https://oddsportal.com/{prefix}m{i}" for i in range(RESULTS_PAGE_SIZE)]


@pytest.fixture(autouse=True)
def instant_listing_retry():
    """Skip the backoff between a failed listing page and its re-fetch.

    asyncio.sleep is the module's only use of asyncio, so nothing else in the walk
    depends on this.
    """
    with patch("oddsharvester.core.odds_portal_scraper.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        yield sleep_mock


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
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[])

    # Mock extract_match_links method
    page1 = full_page("page1")
    scraper.extract_match_links = AsyncMock()
    scraper.extract_match_links.side_effect = [
        page1,
        [page1[-1], "https://oddsportal.com/match3"],
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
    assert sorted(result.links) == sorted([*page1, "https://oddsportal.com/match3"])
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
    page1 = full_page("page1")
    scraper.extract_match_links = AsyncMock()
    scraper.extract_match_links.side_effect = [page1, Exception("Page error")]

    # Call the method under test
    result = await scraper._collect_match_links(
        base_url="https://oddsportal.com/football/england/premier-league-2023", pages_to_scrape=[1, 2]
    )

    # Verify the result is LinkCollectionResult with successful page links and tracked failure
    assert isinstance(result, LinkCollectionResult)
    assert result.links == page1
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

    page1_links = full_page("page1")
    page2_links = [page1_links[2], "https://www.oddsportal.com/match6"]
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


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_live_no_matches_returns_empty_result(url_builder_mock, setup_scraper_mocks):
    """No live match is a normal outcome: empty result, no failures."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_live_matches_url.return_value = "https://oddsportal.com/inplay-odds/live-now/football/"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper.extract_live_match_links = AsyncMock(return_value=[])
    scraper.extract_match_odds = AsyncMock()

    result = await scraper.scrape_live(sport="football")

    assert result.success == []
    assert result.stats.total_urls == 0
    scraper.extract_match_odds.assert_not_awaited()


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_live_links_only(url_builder_mock, setup_scraper_mocks):
    """links_only=True returns the collected live links without scraping odds."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_live_matches_url.return_value = "https://oddsportal.com/inplay-odds/live-now/football/"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper.extract_live_match_links = AsyncMock(
        return_value=[{"match_link": "https://www.oddsportal.com/x/inplay-odds/#a", "live_period": "1H"}]
    )
    scraper.extract_match_odds = AsyncMock()

    result = await scraper.scrape_live(sport="football", links_only=True)

    assert result.success == [
        {"match_link": "https://www.oddsportal.com/x/inplay-odds/#a", "sport": "football", "league": None}
    ]
    scraper.extract_match_odds.assert_not_awaited()


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_live_drops_ended_matches(url_builder_mock, setup_scraper_mocks):
    """A match that ended between listing and visit is dropped, not counted as scraped."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_live_matches_url.return_value = "https://oddsportal.com/inplay-odds/live-now/football/"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper.extract_live_match_links = AsyncMock(
        return_value=[
            {"match_link": "https://www.oddsportal.com/x/inplay-odds/#a", "live_period": "1H"},
            {"match_link": "https://www.oddsportal.com/y/inplay-odds/#b", "live_period": "2H"},
        ]
    )
    live_match = {"home_team": "A", "away_team": "B", "live_period": "1H"}
    ended_marker = {"_live_ended": True, "match_link": "https://www.oddsportal.com/y/inplay-odds/#b"}
    scraper.extract_match_odds = AsyncMock(
        return_value=ScrapeResult(
            success=[live_match, ended_marker],
            stats=ScrapeStats(total_urls=2, successful=2, failed=0),
        )
    )

    result = await scraper.scrape_live(sport="football", markets=["1x2"])

    assert result.success == [live_match]
    assert result.stats.successful == 1
    assert result.stats.total_urls == 1


@pytest.mark.asyncio
async def test_scrape_live_with_match_links_normalizes_urls(setup_scraper_mocks):
    """--match-link accepts a classic match URL and is normalized to its in-play form."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    scraper._prepare_page_for_scraping = AsyncMock()
    scraper.extract_live_match_links = AsyncMock()
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_live(
        sport="football",
        markets=["1x2"],
        match_links=["https://www.oddsportal.com/football/spain/laliga/real-betis-abc/"],
    )

    kwargs = scraper.extract_match_odds.call_args.kwargs
    assert kwargs["match_links"] == ["https://www.oddsportal.com/football/spain/laliga/real-betis-abc/inplay-odds/"]
    assert kwargs["live_mode"] is True
    scraper.extract_live_match_links.assert_not_awaited()


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_live_never_scrapes_odds_history(url_builder_mock, setup_scraper_mocks):
    """Live snapshots carry no odds history: the in-play view does not expose it."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_live_matches_url.return_value = "https://oddsportal.com/inplay-odds/live-now/football/"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper.extract_live_match_links = AsyncMock(
        return_value=[{"match_link": "https://www.oddsportal.com/x/inplay-odds/#a", "live_period": "1H"}]
    )
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_live(sport="football", markets=["1x2"])

    kwargs = scraper.extract_match_odds.call_args.kwargs
    assert kwargs["scrape_odds_history"] is False
    assert kwargs["period"] is None


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_historic_surfaces_failed_listing_pages_in_odds_path(url_builder_mock, setup_scraper_mocks):
    """A failed listing page silently loses ~50 unknown matches, so it must reach the result.

    Without this the odds path reports 100% success on a dataset missing entire
    pages, which is undetectable downstream.
    """
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_historic_matches_url.return_value = "https://oddsportal.com/football/epl/results/"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper._get_pagination_info = AsyncMock(return_value=[1, 2, 3])
    scraper._collect_match_links = AsyncMock(
        return_value=LinkCollectionResult(links=["https://oddsportal.com/m1"], successful_pages=1, failed_pages=[2, 3])
    )
    scraper.extract_match_odds = AsyncMock(
        return_value=ScrapeResult(
            success=[{"home_team": "A"}],
            stats=ScrapeStats(total_urls=1, successful=1, failed=0),
        )
    )

    result = await scraper.scrape_historic(
        sport="football", league="england-premier-league", season="2022-2023", markets=["1x2"]
    )

    listing_failures = [f for f in result.failed if f.error_type is ErrorType.LISTING_PAGE]
    assert len(listing_failures) == 2, "both failed listing pages must be reported"
    assert result.stats.failed == 2
    assert result.stats.total_urls == 3
    assert result.success == [{"home_team": "A", "season": "2022-2023"}]


@pytest.mark.asyncio
@patch("oddsharvester.core.odds_portal_scraper.URLBuilder")
async def test_scrape_historic_clean_run_reports_no_listing_failures(url_builder_mock, setup_scraper_mocks):
    """A complete collection must not be polluted with phantom failures."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    url_builder_mock.get_historic_matches_url.return_value = "https://oddsportal.com/football/epl/results/"
    scraper._prepare_page_for_scraping = AsyncMock()
    scraper._get_pagination_info = AsyncMock(return_value=[1])
    scraper._collect_match_links = AsyncMock(
        return_value=LinkCollectionResult(links=["https://oddsportal.com/m1"], successful_pages=1, failed_pages=[])
    )
    scraper.extract_match_odds = AsyncMock(
        return_value=ScrapeResult(success=[{"home_team": "A"}], stats=ScrapeStats(total_urls=1, successful=1))
    )

    result = await scraper.scrape_historic(
        sport="football", league="england-premier-league", season="2022-2023", markets=["1x2"]
    )

    assert result.failed == []
    assert result.stats.failed == 0


@pytest.mark.asyncio
async def test_collect_match_links_treats_empty_page_as_failure(setup_scraper_mocks):
    """A page that yields zero links has not been collected, whatever the reason.

    extract_match_links swallows its exceptions and returns [], and a throttled
    or blocked page renders no rows at all. Counting either as a successful page
    is how a run silently returns page 1 only while reporting zero failures.
    """
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    tab = AsyncMock()
    mocks["playwright_manager_mock"].context.new_page = AsyncMock(return_value=tab)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[])
    # page 1 renders, pages 2 and 3 come back empty
    page1 = full_page("page1")
    scraper.extract_match_links = AsyncMock(side_effect=[page1, [], []])

    result = await scraper._collect_match_links(base_url="https://oddsportal.com/x/results/", pages_to_scrape=[1, 2, 3])

    assert result.links == page1
    assert result.successful_pages == 1, "an empty page must not count as collected"
    assert result.failed_pages == [2, 3]


@pytest.mark.asyncio
async def test_collect_match_links_treats_partial_page_as_failure(setup_scraper_mocks):
    """A page below the frontier is not the last one, so it must come back full (issue #78).

    A stalled lazy-load renders a handful of rows and the scroll still reports
    success, so fullness is the only signal left. Counting the page as collected
    is how a season loses 3 pages and still reports zero failures.
    """
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    tab = AsyncMock()
    mocks["playwright_manager_mock"].context.new_page = AsyncMock(return_value=tab)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[1, 2, 3])
    page1 = [f"https://p1m{i}" for i in range(RESULTS_PAGE_SIZE)]
    page2 = [f"https://p2m{i}" for i in range(5)]  # stalled lazy-load: 5 rows out of 50
    page3 = ["https://p3m1"]
    scraper.extract_match_links = AsyncMock(side_effect=[page1, page2, page2, page3])

    result = await scraper._collect_match_links(base_url="https://oddsportal.com/x/results/", pages_to_scrape=[1, 2, 3])

    assert result.failed_pages == [2], "a page short of a full listing hides rows that were never discovered"
    assert result.successful_pages == 2, "a truncated page must not count as collected"
    assert "https://p2m0" in result.links, "the rows it did render are still real data"


@pytest.mark.asyncio
async def test_collect_match_links_refetches_a_truncated_page(setup_scraper_mocks):
    """The truncation is transient, so the page is fetched again before being written off.

    Recovering in place beats losing the page: the alternative costs the user a full
    re-run of the season to recover one page (issue #78).
    """
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    tab = AsyncMock()
    mocks["playwright_manager_mock"].context.new_page = AsyncMock(return_value=tab)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[1, 2])
    page1 = full_page("page1")
    page2 = full_page("page2")
    # page 1 stalls at 5 rows, then renders in full on the second attempt
    scraper.extract_match_links = AsyncMock(side_effect=[page1[:5], page1, page2[:3]])

    result = await scraper._collect_match_links(base_url="https://oddsportal.com/x/results/", pages_to_scrape=[1, 2])

    assert result.failed_pages == [], "a page that recovers on the second attempt was not lost"
    assert result.links == [*page1, *page2[:3]]
    assert scraper.extract_match_links.call_count == 3, "page 1 fetched twice, page 2 once"


@pytest.mark.asyncio
async def test_collect_match_links_refetches_a_truncated_page_only_once(setup_scraper_mocks):
    """A page that stays truncated is reported, not retried forever."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    tab = AsyncMock()
    mocks["playwright_manager_mock"].context.new_page = AsyncMock(return_value=tab)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[1, 2])
    page1 = full_page("page1")
    scraper.extract_match_links = AsyncMock(side_effect=[page1[:5], page1[:5], page1[:3]])

    result = await scraper._collect_match_links(base_url="https://oddsportal.com/x/results/", pages_to_scrape=[1, 2])

    assert result.failed_pages == [1]
    assert scraper.extract_match_links.call_count == 3, "page 1 fetched twice, then the walk moves on"


@pytest.mark.asyncio
async def test_collect_match_links_keeps_single_empty_page_successful(setup_scraper_mocks):
    """A genuinely empty season returns zero links on its only page, and that is not an error.

    Documented behaviour: OddsPortal answers HTTP 200 for a dead season URL, so an
    empty single-page result is the normal way to learn a combo is invalid.
    """
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    tab = AsyncMock()
    mocks["playwright_manager_mock"].context.new_page = AsyncMock(return_value=tab)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[])
    scraper.extract_match_links = AsyncMock(return_value=[])

    result = await scraper._collect_match_links(base_url="https://oddsportal.com/x/results/", pages_to_scrape=[1])

    assert result.links == []
    assert result.successful_pages == 1
    assert result.failed_pages == []


def _walk_tab(mocks):
    tab = AsyncMock()
    mocks["playwright_manager_mock"].context.new_page = AsyncMock(return_value=tab)
    return tab


@pytest.mark.asyncio
async def test_collect_match_links_walks_past_an_empty_widget(setup_scraper_mocks, caplog):
    """Issue 79: an unreadable widget must not cap collection at one page.

    Page 1's widget read comes back empty, so the floor is [1]. Page 2's widget
    reports 8, which is when the true count becomes known.
    """
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    _walk_tab(mocks)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(side_effect=[[], *([list(range(1, 9))] * 7)])
    pages = [[f"https://m{p}-{i}" for i in range(50)] for p in range(1, 8)] + [[f"https://m8-{i}" for i in range(30)]]
    scraper.extract_match_links = AsyncMock(side_effect=pages)

    with caplog.at_level(logging.WARNING):
        result = await scraper._collect_match_links(base_url="https://oddsportal.com/x/results/", pages_to_scrape=[1])

    assert len(result.links) == 380
    assert result.successful_pages == 8
    assert result.failed_pages == []
    assert any("but the walk collected" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_collect_match_links_walks_past_an_underreporting_widget(setup_scraper_mocks):
    """A widget that reports fewer pages than exist must not end collection either."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    _walk_tab(mocks)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[1, 2, 3])
    pages = [[f"https://m{p}-{i}" for i in range(50)] for p in range(1, 8)] + [[f"https://m8-{i}" for i in range(30)]]
    scraper.extract_match_links = AsyncMock(side_effect=pages)

    result = await scraper._collect_match_links(base_url="https://oddsportal.com/x/results/", pages_to_scrape=[1, 2, 3])

    assert len(result.links) == 380
    assert result.successful_pages == 8
    assert result.failed_pages == []


@pytest.mark.asyncio
async def test_collect_match_links_fails_empty_page_despite_lower_mid_walk_observed_max(setup_scraper_mocks):
    """A mid-walk widget read that only sees up to page 3 must not shrink the frontier.

    The base page promised 8 pages (frontier=8). Every in-walk widget read reports only
    [1, 2, 3], so observed_max stays 3, well below the frontier. Page 8 renders nothing.
    Comparing against observed_max instead of frontier would read this as STOP_COMPLETE
    and silently drop page 8; it must be PAGE_FAILED instead.
    """
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    _walk_tab(mocks)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[1, 2, 3])
    pages = [[f"https://m{p}-{i}" for i in range(50)] for p in range(1, 8)] + [[], []]
    scraper.extract_match_links = AsyncMock(side_effect=pages)

    result = await scraper._collect_match_links(
        base_url="https://oddsportal.com/x/results/", pages_to_scrape=list(range(1, 9))
    )

    assert result.failed_pages == [8]
    assert len(result.links) == 350
    assert result.successful_pages == 7


@pytest.mark.asyncio
async def test_collect_match_links_stops_clean_one_page_past_the_end(setup_scraper_mocks):
    """A season whose last page is exactly full: page 9 renders nothing but the widget still says 8."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    _walk_tab(mocks)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=list(range(1, 9)))
    pages = [[f"https://m{p}-{i}" for i in range(50)] for p in range(1, 9)] + [[]]
    scraper.extract_match_links = AsyncMock(side_effect=pages)

    result = await scraper._collect_match_links(
        base_url="https://oddsportal.com/x/results/", pages_to_scrape=list(range(1, 9))
    )

    assert len(result.links) == 400
    assert result.successful_pages == 8, "the zero-link confirmation page is not itself collected"
    assert result.failed_pages == [], "walking one past the end is not a failure"


@pytest.mark.asyncio
async def test_collect_match_links_flags_an_empty_page_the_widget_says_exists(setup_scraper_mocks):
    """Gotcha 17: the widget says 8 pages and page 4 renders nothing, so page 4 was degraded."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    _walk_tab(mocks)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=list(range(1, 9)))
    pages = (
        [[f"https://m{p}-{i}" for i in range(50)] for p in range(1, 4)]
        + [[], []]  # page 4 stays empty across its re-fetch
        + [[f"https://m{p}-{i}" for i in range(50)] for p in range(5, 8)]
        + [[f"https://m8-{i}" for i in range(30)]]
    )
    scraper.extract_match_links = AsyncMock(side_effect=pages)

    result = await scraper._collect_match_links(
        base_url="https://oddsportal.com/x/results/", pages_to_scrape=list(range(1, 9))
    )

    assert result.failed_pages == [4]
    assert len(result.links) == 330, "the run continues past a failed page"


@pytest.mark.asyncio
async def test_collect_match_links_fails_a_short_page_with_incomplete_scroll(setup_scraper_mocks):
    """Issue 79 recreated via scroll failure: a short page at the frontier whose scroll did not
    finish must be flagged as failed, not silently read as a clean, complete season.
    """
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    _walk_tab(mocks)
    scraper.scroller.scroll_until_loaded = AsyncMock(side_effect=[True] * 7 + [False, False])
    scraper.pagination_walker.read_widget = AsyncMock(return_value=list(range(1, 9)))
    page8 = [f"https://m8-{i}" for i in range(30)]
    # page 8 scrolls short on both attempts
    pages = [[f"https://m{p}-{i}" for i in range(50)] for p in range(1, 8)] + [page8, page8]
    scraper.extract_match_links = AsyncMock(side_effect=pages)

    result = await scraper._collect_match_links(
        base_url="https://oddsportal.com/x/results/", pages_to_scrape=list(range(1, 9))
    )

    assert result.successful_pages == 7
    assert result.failed_pages == [8], "an incompletely scrolled short page must not read as a clean stop"


@pytest.mark.asyncio
async def test_collect_match_links_respects_the_page_limit(setup_scraper_mocks, caplog):
    """An explicit --max-pages bounds the walk even when every page is full."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    _walk_tab(mocks)
    scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    scraper.pagination_walker.read_widget = AsyncMock(return_value=[])
    scraper.extract_match_links = AsyncMock(side_effect=[[f"https://m{p}-{i}" for i in range(50)] for p in range(1, 9)])

    with caplog.at_level(logging.WARNING):
        result = await scraper._collect_match_links(
            base_url="https://oddsportal.com/x/results/", pages_to_scrape=[1], page_limit=3
        )

    assert len(result.links) == 150
    assert result.successful_pages == 3
    assert any("raise --max-pages" in r.message for r in caplog.records)
