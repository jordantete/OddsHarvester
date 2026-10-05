from collections import Counter
from datetime import UTC, datetime, time
import logging
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from urllib.parse import urldefrag

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page
import pytest
from tests.clock import frozen_clock
from tests.dom_builders import date_header, listing_row, live_section, page, pagination

from oddsharvester.core import base_scraper
from oddsharvester.core.base_scraper import BaseScraper
from oddsharvester.core.exceptions import PageNotFoundError, RateLimitError, SeasonNotFoundError
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import LinkCollectionResult, ListingResult, OddsPortalScraper
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.scrape_result import ScrapeResult, ScrapeStats
from oddsharvester.utils.constants import (
    GOTO_TIMEOUT_LONG_MS,
    GOTO_TIMEOUT_MS,
    LISTING_PAGE_RETRY_DELAY_S,
    MAX_PAGINATION_PAGES,
    ODDSPORTAL_BASE_URL,
    RESULTS_PAGE_SIZE,
)
from oddsharvester.utils.proxy_manager import ProxyManager


@pytest.fixture
def setup_scraper_mocks():
    """Setup common mocks for the OddsPortalScraper tests."""
    # Create mocks for dependencies
    playwright_manager_mock = MagicMock(spec=PlaywrightManager)
    market_extractor_mock = MagicMock(spec=OddsPortalMarketExtractor)

    # Setup page and context mocks
    page_mock = AsyncMock(spec=Page)
    # goto lands on the requested URL: the no-redirect case the season guard expects.
    page_mock.goto.side_effect = lambda url, **kwargs: setattr(page_mock, "url", url)
    context_mock = AsyncMock(spec=BrowserContext)
    # Listings now open their own tab; hand them the same page mock so the
    # existing goto/prepare/extract assertions keep pointing at one object.
    context_mock.new_page = AsyncMock(return_value=page_mock)
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


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status


class _Element:
    """An element handle: the pagination walker reads only its text."""

    def __init__(self, text: str) -> None:
        self._text = text

    async def text_content(self) -> str:
        return self._text


class _Locator:
    def __init__(self, count: int) -> None:
        self._count = count

    async def count(self) -> int:
        return self._count


class ListingTab:
    """A tab of ListingSite: goto renders the next version of the page it names, the other calls read that DOM."""

    def __init__(self, site: "ListingSite") -> None:
        self.site = site
        self.url = "about:blank"
        self.dom: str | Exception = ""
        self.number: int | None = None
        self.gotos: list[tuple[str, dict]] = []
        self.closes = 0

    async def goto(self, url: str, **kwargs) -> _Response:
        self.gotos.append((url, kwargs))
        self.site.gotos.append((url, kwargs))
        if self.site.goto_error is not None:
            raise self.site.goto_error
        self.url = self.site.redirects.get(url, url)
        self.number, self.dom = self.site.render(url)
        return _Response(self.site.status.get(url, 200))

    def _soup(self) -> BeautifulSoup:
        if isinstance(self.dom, Exception):
            raise self.dom
        return BeautifulSoup(self.dom, "lxml")

    async def content(self) -> str:
        self.site.reads.append(self.number)
        if isinstance(self.dom, Exception):
            raise self.dom
        return self.dom

    async def query_selector_all(self, selector: str) -> list[_Element]:
        return [_Element(el.get_text()) for el in self._soup().select(selector)]

    def locator(self, selector: str) -> _Locator:
        self.site.locators.append(selector)
        return _Locator(len(self._soup().select(selector)))

    async def wait_for_timeout(self, timeout: float) -> None:
        self.site.pauses.append(timeout)

    async def close(self) -> None:
        self.closes += 1


class ListingSite:
    """The listing pages a test serves, by page number; a URL without a `#page/N` fragment is page 1.

    Each load of a page renders its next version, the last one repeating; a version that is an exception is a
    page whose DOM cannot be read.
    """

    def __init__(self) -> None:
        self.pages: dict[int, list[str | Exception]] = {}
        self.status: dict[str, int] = {}
        self.redirects: dict[str, str] = {}
        self.goto_error: Exception | None = None
        self.tabs: list[ListingTab] = []
        self.gotos: list[tuple[str, dict]] = []
        self.reads: list[int | None] = []
        self.pauses: list[float] = []
        self.locators: list[str] = []
        self.shared_tab = ListingTab(self)
        self._loads: Counter[int] = Counter()

    def serve(self, number: int, *versions: str | Exception) -> None:
        self.pages[number] = list(versions)

    async def new_page(self) -> ListingTab:
        tab = ListingTab(self)
        self.tabs.append(tab)
        return tab

    def render(self, url: str) -> tuple[int, str | Exception]:
        fragment = urldefrag(url).fragment
        number = int(fragment.removeprefix("page/")) if fragment.startswith("page/") else 1
        versions = self.pages.get(number, [""])
        version = versions[min(self._loads[number], len(versions) - 1)]
        self._loads[number] += 1
        return number, version

    def every_tab_closed_once(self) -> bool:
        return all(tab.closes == 1 for tab in self.tabs)


@pytest.fixture
def site() -> ListingSite:
    return ListingSite()


@pytest.fixture
def scraper(site) -> OddsPortalScraper:
    """A scraper whose browser is `site`; the scroller and the warm-up are the browser boundary, simulated."""
    playwright_manager = MagicMock(spec=PlaywrightManager)
    playwright_manager.context = site
    playwright_manager.page = site.shared_tab
    listing_scraper = OddsPortalScraper(
        playwright_manager=playwright_manager,
        market_extractor=MagicMock(spec=OddsPortalMarketExtractor),
        scroller=AsyncMock(),
        cookie_dismisser=AsyncMock(),
        selection_manager=AsyncMock(),
    )
    listing_scraper.scroller.scroll_until_loaded = AsyncMock(return_value=True)
    listing_scraper._warm_up_page = AsyncMock()
    return listing_scraper


SEASON_URL = "https://www.oddsportal.com/football/england/premier-league-2024-2025/results/"


def hrefs(number: int, count: int, sport: str = "football") -> list[str]:
    """`count` match hrefs of listing page `number`."""
    return [f"/{sport}/h2h/home-p{number}m{i}/away-p{number}m{i}/#e{number}x{i}" for i in range(count)]


def listing(row_hrefs: list[str], widget: list[int] | None = None, day: str = "18 May 2025") -> str:
    """A listing page: one date group holding the rows, then the pagination widget when one is given."""
    rows = "".join(listing_row(href, status="15:00") for href in row_hrefs)
    return page(date_header(day) + rows + (pagination(widget) if widget else ""))


def links(row_hrefs: list[str]) -> list[str]:
    return [f"{ODDSPORTAL_BASE_URL}{href}" for href in row_hrefs]


async def walk(scraper, floor: int = 1, **kwargs) -> LinkCollectionResult:
    """The walk of SEASON_URL from a floor of `floor` pages, starting on the season page's tab as the listing does."""
    season_tab = await _season_tab(scraper.playwright_manager.context)
    return await scraper._collect_match_links(season_tab=season_tab, base_url=SEASON_URL, floor=floor, **kwargs)


def _assert_scroll_pace_left_to_the_scroller(scroll_mock):
    """Listing call sites leave the scroll pace to the shared constants (SCROLL_PAUSE_S, MAX_SCROLL_ATTEMPTS)."""
    assert scroll_mock.await_args_list, "the listing never scrolled"
    for call in scroll_mock.await_args_list:
        assert call.args == ()
        assert {"scroll_pause_time", "max_scroll_attempts"}.isdisjoint(call.kwargs), call.kwargs


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


async def test_stop_playwright(setup_scraper_mocks):
    """Test stopping Playwright."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]

    await scraper.stop_playwright()
    mocks["playwright_manager_mock"].cleanup.assert_called_once()


async def test_collect_historic_links_reads_the_season_listing(scraper, site):
    """A season listing is read page by page into a ListingResult of match links, up to --max-pages."""
    page1, page2 = hrefs(1, RESULTS_PAGE_SIZE), hrefs(2, RESULTS_PAGE_SIZE)
    site.serve(1, listing(page1, widget=[1, 2, 3]))
    site.serve(2, listing([*page2, *hrefs(2, 1, sport="hockey")], widget=[1, 2, 3]))
    site.serve(3, listing(hrefs(3, RESULTS_PAGE_SIZE), widget=[1, 2, 3]))

    listing_result = await scraper.collect_historic_links(
        sport="football", league="england-premier-league", season="2024-2025", max_pages=2
    )

    season_tab = site.tabs[0]
    assert season_tab.gotos[0][0] == SEASON_URL
    scraper._warm_up_page.assert_awaited_once_with(season_tab)
    assert site.reads == [1, 2], "the walk stops at --max-pages"
    assert isinstance(listing_result, ListingResult)
    assert [row["match_link"] for row in listing_result.rows] == links(page1 + page2), "the hockey row is dropped"
    assert listing_result.failed_page_urls == []


async def test_collect_historic_links_fails_when_season_url_redirects(scraper, site):
    """A season URL redirected to the league's current fixtures must fail, not be scraped."""
    season_url = "https://www.oddsportal.com/football/mexico/primera-division-2012-2013/results/"
    site.redirects[season_url] = "https://www.oddsportal.com/football/mexico/primera-division/"
    site.serve(1, listing(hrefs(1, 3)))

    with pytest.raises(PageNotFoundError):
        await scraper.collect_historic_links(sport="football", league="mexico-liga-mx", season="2012-2013")

    assert [url for url, _ in site.gotos] == [season_url], "the walk never starts"
    assert site.reads == []


@pytest.mark.parametrize(
    ("requested", "landed"),
    [
        ("https://oddsportal.com/football/spain/laliga-2020-2021/results/", None),
        (
            "https://oddsportal.com/football/spain/laliga-2020-2021/results/",
            "https://oddsportal.com/football/spain/laliga-2020-2021/results",
        ),
        (
            "https://oddsportal.com/football/spain/laliga-2020-2021/results/",
            "https://www.oddsportal.com/football/spain/laliga-2020-2021/results/#page/2",
        ),
    ],
)
def test_season_guard_accepts_the_requested_page(requested, landed):
    OddsPortalScraper._assert_season_page_reached(requested_url=requested, landed_url=landed or requested)


def test_season_guard_raises_season_not_found_on_redirect():
    """A redirected season is a SeasonNotFoundError, which is still a PageNotFoundError."""
    with pytest.raises(SeasonNotFoundError) as excinfo:
        OddsPortalScraper._assert_season_page_reached(
            requested_url="https://oddsportal.com/football/spain/laliga-2010-2011/results/",
            landed_url="https://oddsportal.com/football/spain/laliga/",
        )

    assert isinstance(excinfo.value, PageNotFoundError)


async def test_collect_upcoming_links_reads_the_listing(scraper, site):
    """The upcoming listing is filtered by the requested date and returned as a ListingResult."""
    first_day, second_day = hrefs(1, 2), hrefs(2, 1)
    site.serve(
        1,
        page(
            date_header("01 Jun 2026")
            + "".join(listing_row(href) for href in first_day)
            + date_header("02 Jun 2026")
            + "".join(listing_row(href) for href in second_day)
        ),
    )

    listing_result = await scraper.collect_upcoming_links(
        sport="football", date="20260601", league="england-premier-league"
    )

    assert [url for url, _ in site.gotos] == ["https://www.oddsportal.com/football/england/premier-league"]
    scraper._warm_up_page.assert_awaited_once_with(site.tabs[0])
    assert isinstance(listing_result, ListingResult)
    assert listing_result.rows == [{"match_link": link, "kickoff_utc": None} for link in links(first_day)]


async def test_collect_upcoming_links_keeps_rows_with_unknown_kickoff(scraper, site):
    """A null kickoff must still occupy the column, or CSV writing raises (issue #81)."""
    known, unknown = hrefs(1, 2)
    site.serve(
        1, page(date_header("20 Jul 2026") + listing_row(known, status="18:30") + listing_row(unknown, status=""))
    )

    listing_result = await scraper.collect_upcoming_links(
        sport="football", date="20260720", league=None, collect_kickoff=True
    )

    assert [row["kickoff_utc"] for row in listing_result.rows] == ["2026-07-20 18:30:00 UTC", None]


async def test_scrape_matches(setup_scraper_mocks):
    """Test scraping specific match links."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock methods
    scraper._warm_up_page = AsyncMock()

    # Mock extract_match_odds to return ScrapeResult
    mock_scrape_result = ScrapeResult(
        success=[{"match": "data1"}, {"match": "data2"}],
        failed=[],
        stats=ScrapeStats(total_urls=2, successful=2, failed=0),
    )
    scraper.extract_match_odds = AsyncMock(return_value=mock_scrape_result)

    match_links = ["https://oddsportal.com/match1", "https://oddsportal.com/match2"]

    # Call the method under test
    result = await scraper.scrape_matches(
        match_links=match_links, sport="tennis", markets=["1x2"], scrape_odds_history=True, target_bookmaker="bwin"
    )

    # Verify the interactions
    scraper._warm_up_page.assert_awaited_once_with(page_mock, home_timeout_ms=GOTO_TIMEOUT_LONG_MS)
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


async def test_collect_upcoming_links_applies_kickoff_within_hours(scraper, site):
    """collect_upcoming_links keeps only the rows kicking off within kickoff_within_hours (issue #77)."""
    soon, late = hrefs(1, 2)
    site.serve(
        1, page(date_header("01 Jun 2026") + listing_row(soon, status="13:00") + listing_row(late, status="20:00"))
    )

    with patch("oddsharvester.core.base_scraper.datetime", frozen_clock(datetime(2026, 6, 1, 12, 0, tzinfo=UTC))):
        listing_result = await scraper.collect_upcoming_links(sport="football", date="20260601", kickoff_within_hours=6)

    assert [row["match_link"] for row in listing_result.rows] == links([soon])


async def test_collect_upcoming_links_runs_on_its_own_tab(scraper, site):
    """Each listing opens and closes its own tab, so several can run at once (issue #87)."""
    on_the_day, next_day = hrefs(1, 1), hrefs(2, 1)
    site.serve(
        1,
        page(
            date_header("01 Jun 2026")
            + listing_row(on_the_day[0])
            + date_header("02 Jun 2026")
            + listing_row(next_day[0])
        ),
    )

    listing_result = await scraper.collect_upcoming_links(
        sport="football", date="20260601", league="england-premier-league"
    )

    [tab] = site.tabs
    assert tab.gotos == [
        (
            "https://www.oddsportal.com/football/england/premier-league",
            {"timeout": GOTO_TIMEOUT_MS, "wait_until": "domcontentloaded"},
        )
    ]
    scraper._warm_up_page.assert_awaited_once_with(tab)
    scraper.scroller.scroll_until_loaded.assert_awaited_once()
    assert scraper.scroller.scroll_until_loaded.await_args.kwargs["page"] is tab
    _assert_scroll_pace_left_to_the_scroller(scraper.scroller.scroll_until_loaded)
    assert tab.closes == 1
    assert site.shared_tab.gotos == []
    assert isinstance(listing_result, ListingResult)
    assert [row["match_link"] for row in listing_result.rows] == links(on_the_day)
    assert listing_result.failed_page_urls == []


async def test_collect_upcoming_links_closes_the_tab_when_the_listing_raises(scraper, site):
    """A listing that fails must not leave its tab open for the rest of the run."""
    site.goto_error = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await scraper.collect_upcoming_links(sport="football", date="20260601", league="england-premier-league")

    assert [tab.closes for tab in site.tabs] == [1]


async def test_collect_upcoming_links_without_a_league_keeps_every_date_of_the_page(scraper, site):
    """The all-leagues date page is not filtered by date headers; the sport and started-row filters still apply."""
    first_day, second_day = hrefs(1, 1), hrefs(2, 1)
    started, hockey = hrefs(3, 1), hrefs(4, 1, sport="hockey")
    site.serve(
        1,
        page(
            date_header("01 Jun 2026")
            + listing_row(first_day[0])
            + listing_row(started[0], status="Finished")
            + listing_row(hockey[0])
            + date_header("02 Jun 2026")
            + listing_row(second_day[0])
        ),
    )

    listing_result = await scraper.collect_upcoming_links(sport="football", date="20260601")

    assert [url for url, _ in site.gotos] == ["https://www.oddsportal.com/matches/football/20260601/"]
    assert [row["match_link"] for row in listing_result.rows] == links(first_day + second_day)
    assert site.locators == [], "a date page has no league to check"


async def _season_tab(site) -> ListingTab:
    tab = await site.new_page()
    await tab.goto(SEASON_URL, timeout=GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
    return tab


async def test_get_pagination_info(scraper, site):
    """_get_pagination_info returns the floor: the widget's highest page, gaps and all, 1 without a widget."""
    site.serve(1, listing(hrefs(1, 3), widget=[1, 2, 3, 27]))
    assert await scraper._get_pagination_info(page=await _season_tab(site)) == 27

    site.serve(1, listing(hrefs(1, 3)))
    assert await scraper._get_pagination_info(page=await _season_tab(site)) == 1


async def test_get_pagination_info_is_not_capped_by_the_page_limit(scraper, site):
    """The page limit bounds the walk once, in _collect_match_links; the floor is the widget's true count."""
    total = MAX_PAGINATION_PAGES + 20
    site.serve(1, listing(hrefs(1, 3), widget=list(range(1, total + 1))))

    assert await scraper._get_pagination_info(page=await _season_tab(site)) == total


def _season_widget_gone_once_scrolled(site, page1_hrefs):
    """A scroller after which the season tab shows page 1 without its pagination widget."""

    async def scroll(page, **_):
        if page is site.tabs[0]:
            page.dom = listing(page1_hrefs)
        return True

    return scroll


async def test_collect_historic_links_fails_a_short_page_below_the_season_widget_s_count(scraper, site):
    """A widget read on the season page keeps the frontier at its count past --max-pages (spec 5c-5c 2.2).

    The season page loses its widget once scrolled and the walked pages show none, so only the floor read before the
    scroll knows the season has 8 pages. A short page 3 below that frontier lost rows: it is fetched again, then
    reported, instead of ending the listing.
    """
    page1, page2, page3 = hrefs(1, RESULTS_PAGE_SIZE), hrefs(2, RESULTS_PAGE_SIZE), hrefs(3, 20)
    site.serve(1, listing(page1, widget=list(range(1, 9))), listing(page1))
    site.serve(2, listing(page2))
    site.serve(3, listing(page3))
    scraper.scroller.scroll_until_loaded = AsyncMock(side_effect=_season_widget_gone_once_scrolled(site, page1))

    listing_result = await scraper.collect_historic_links(
        sport="football", league="england-premier-league", season="2024-2025", max_pages=3
    )

    assert listing_result.failed_page_urls == [f"{SEASON_URL}#page/3"]
    assert [row["match_link"] for row in listing_result.rows] == links(page1 + page2 + page3)
    assert site.reads == [1, 2, 3, 3]


@pytest.fixture(autouse=True)
def instant_listing_retry():
    """Skip the backoff between a failed listing page and its re-fetch.

    asyncio.sleep is the module's only use of asyncio, so nothing else in the walk
    depends on this.
    """
    with patch("oddsharvester.core.odds_portal_scraper.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        yield sleep_mock


async def test_collect_match_links(scraper, site):
    """Test collecting match links from multiple pages."""
    page1 = hrefs(1, RESULTS_PAGE_SIZE)
    site.serve(1, listing(page1))
    site.serve(2, listing([page1[-1], *hrefs(2, 1)]))

    result = await walk(scraper, floor=2)

    assert len(site.tabs) == 2
    assert len(site.gotos) == 2
    assert len(site.pauses) == 2
    assert site.every_tab_closed_once()
    assert site.reads == [1, 2]
    assert isinstance(result, LinkCollectionResult)
    assert result.links == links(page1 + hrefs(2, 1))
    assert result.successful_pages == 2
    assert result.failed_pages == []


async def test_collect_match_links_error_handling(scraper, site):
    """Test error handling in collect_match_links method."""
    page1 = hrefs(1, RESULTS_PAGE_SIZE)
    site.serve(1, listing(page1))
    # The second page cannot be read, twice (it is fetched again once).
    site.serve(2, RuntimeError("Page error"))

    result = await walk(scraper, floor=2)

    assert isinstance(result, LinkCollectionResult)
    assert result.links == links(page1)
    assert result.successful_pages == 1
    assert result.failed_pages == [2]
    assert site.reads == [1, 2, 2]
    assert len(site.tabs) == 3
    assert site.every_tab_closed_once(), "tabs are closed even after an error"


async def test_collect_match_links_preserves_listing_order(scraper, site):
    """Dedup must keep first-seen listing order across pages (issue #75)."""
    page1 = hrefs(1, RESULTS_PAGE_SIZE)
    site.serve(1, listing(page1))
    site.serve(2, listing([page1[2], *hrefs(2, 1)]))

    result = await walk(scraper, floor=2)

    assert result.links == links(page1 + hrefs(2, 1))
    assert result.successful_pages == 2
    _assert_scroll_pace_left_to_the_scroller(scraper.scroller.scroll_until_loaded)


async def test_collect_match_links_counts_an_extraction_crash_as_a_failed_page(scraper, site):
    """B6: a page whose rows cannot be read is a failed page, not a season that ends after page 1."""
    site.serve(1, RuntimeError("renderer crashed"))

    result = await walk(scraper)

    assert result.failed_pages == [1]
    assert result.successful_pages == 0
    assert result.links == []
    assert len(site.tabs) == 2, "the crashed page is fetched once more"
    assert site.every_tab_closed_once()


async def test_collect_match_links_refetches_a_page_that_crashed(scraper, site, instant_listing_retry):
    """A page that raised while it was read gets the same single re-fetch as a truncated page."""
    site.serve(1, RuntimeError("renderer crashed"), listing(hrefs(1, 1)))

    result = await walk(scraper)

    assert (result.failed_pages, result.successful_pages, result.links) == ([], 1, links(hrefs(1, 1)))
    instant_listing_retry.assert_awaited_once_with(LISTING_PAGE_RETRY_DELAY_S)


async def test_collect_match_links_does_not_refetch_a_crashed_page_that_comes_back_truncated(scraper, site):
    """The crash and the truncation share one re-fetch: the page is fetched twice, then reported."""
    page1, page2 = hrefs(1, RESULTS_PAGE_SIZE), hrefs(2, RESULTS_PAGE_SIZE)
    site.serve(1, RuntimeError("renderer crashed"), listing(page1[:5], widget=[1, 2]))
    site.serve(2, listing(page2[:3], widget=[1, 2]))

    result = await walk(scraper, floor=2)

    assert result.failed_pages == [1]
    assert result.links == links(page1[:5] + page2[:3])
    assert site.reads == [1, 1, 2], "page 1 fetched twice, page 2 once"


async def test_collect_match_links_keeps_an_empty_first_page_a_success(scraper, site):
    """A season page that loads with no row is still a complete listing."""
    site.serve(1, "<html><body></body></html>")

    result = await walk(scraper)

    assert (result.failed_pages, result.successful_pages, result.links) == ([], 1, [])


async def test_collect_match_links_drops_the_rows_of_another_sport(scraper, site):
    """The walk passes its sport to the listing guard: rows under another sport's path are not collected."""
    hockey = hrefs(1, 2, sport="hockey")
    site.serve(1, listing([hockey[0], *hrefs(1, 1), hockey[1]]))

    result = await walk(scraper, sport="ice-hockey")

    assert result.links == links(hockey)


async def test_collect_upcoming_links_passes_the_sport_to_the_listing_guard(scraper, site):
    hockey = hrefs(1, 1, sport="hockey")
    site.serve(1, listing([*hrefs(1, 1), *hockey], day="01 Oct 2026"))

    listing_result = await scraper.collect_upcoming_links(sport="ice-hockey", date="20261001")

    assert [url for url, _ in site.gotos] == ["https://www.oddsportal.com/matches/hockey/20261001/"]
    assert [row["match_link"] for row in listing_result.rows] == links(hockey)


def live_now(*sections: tuple[str, list[str]]) -> str:
    """A live-now listing: one section per (league path, in-play hrefs)."""
    return page(
        "".join(
            live_section(league_path, "".join(listing_row(href, status="65'") for href in row_hrefs))
            for league_path, row_hrefs in sections
        )
    )


def inplay(name: str, sport: str = "football") -> str:
    return f"/{sport}/h2h/{name}-home-AAAAAAAA/{name}-away-BBBBBBBB/inplay-odds/#{name}"


LIVE_NOW_URL = "https://www.oddsportal.com/inplay-odds/live-now/football/"


async def test_scrape_live_raises_when_the_listing_cannot_be_read(scraper, site):
    """A live listing that crashes must fail the run, not read as 'no live matches'."""
    site.serve(1, RuntimeError("Target page crashed"))
    scraper.extract_match_odds = AsyncMock()

    with pytest.raises(RuntimeError, match="Target page crashed"):
        await scraper.scrape_live(sport="football")

    scraper.extract_match_odds.assert_not_awaited()


async def test_scrape_live_no_matches_returns_empty_result(scraper, site):
    """No live match is a normal outcome: empty result, no failures."""
    site.serve(1, live_now())
    scraper.extract_match_odds = AsyncMock()

    result = await scraper.scrape_live(sport="football")

    assert site.shared_tab.gotos == [(LIVE_NOW_URL, {"timeout": GOTO_TIMEOUT_MS, "wait_until": "domcontentloaded"})]
    scraper._warm_up_page.assert_awaited_once_with(site.shared_tab)
    assert result.success == []
    assert result.stats.total_urls == 0
    scraper.extract_match_odds.assert_not_awaited()


async def test_scrape_live_links_only(scraper, site):
    """links_only=True returns the collected live links without scraping odds."""
    site.serve(1, live_now(("/football/england/premier-league/", [inplay("a")])))
    scraper.extract_match_odds = AsyncMock()

    result = await scraper.scrape_live(sport="football", links_only=True)

    assert result.success == [{"match_link": links([inplay("a")])[0], "sport": "football", "league": None}]
    # The live links-only rows never carried the listing's period marker.
    assert [list(row) for row in result.success] == [["match_link", "sport", "league"]]
    scraper.extract_match_odds.assert_not_awaited()
    _assert_scroll_pace_left_to_the_scroller(scraper.scroller.scroll_until_loaded)


async def test_scrape_live_keeps_the_section_of_the_requested_league(scraper, site):
    """--league keeps the rows of its own section of the live-now listing, in listing order."""
    site.serve(
        1,
        live_now(
            ("/football/spain/laliga/", [inplay("a")]),
            ("/football/england/premier-league/", [inplay("b"), inplay("c")]),
            ("/tennis/atp-singles/atp-cup/", [inplay("d", sport="tennis")]),
        ),
    )

    result = await scraper.scrape_live(sport="football", league="england-premier-league", links_only=True)

    assert [row["match_link"] for row in result.success] == links([inplay("b"), inplay("c")])


async def test_scrape_live_returns_the_odds_result_as_it_is(scraper, site):
    """Ended matches are dropped where they are detected (B10), so the live flow no longer edits the result."""
    site.serve(1, live_now(("/football/england/premier-league/", [inplay("a"), inplay("b")])))
    odds_result = ScrapeResult(
        success=[{"home_team": "A", "away_team": "B", "live_period": "1H"}],
        stats=ScrapeStats(total_urls=1, successful=1, failed=0),
    )
    scraper.extract_match_odds = AsyncMock(return_value=odds_result)

    result = await scraper.scrape_live(sport="football", markets=["1x2"])

    assert scraper.extract_match_odds.call_args.kwargs["match_links"] == links([inplay("a"), inplay("b")])
    assert result is odds_result
    assert (result.stats.total_urls, result.stats.successful) == (1, 1)


async def test_scrape_live_with_match_links_normalizes_urls(scraper, site):
    """--match-link accepts a classic match URL and is normalized to its in-play form."""
    site.serve(1, live_now(("/football/england/premier-league/", [inplay("a")])))
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_live(
        sport="football",
        markets=["1x2"],
        match_links=["https://www.oddsportal.com/football/spain/laliga/real-betis-abc/"],
    )

    kwargs = scraper.extract_match_odds.call_args.kwargs
    assert kwargs["match_links"] == ["https://www.oddsportal.com/football/spain/laliga/real-betis-abc/inplay-odds/"]
    assert kwargs["live_mode"] is True
    assert site.reads == [], "the listing is never read"


async def test_scrape_live_never_scrapes_odds_history(scraper, site):
    """Live snapshots carry no odds history: the in-play view does not expose it."""
    site.serve(1, live_now(("/football/england/premier-league/", [inplay("a")])))
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_live(sport="football", markets=["1x2"])

    kwargs = scraper.extract_match_odds.call_args.kwargs
    assert kwargs["scrape_odds_history"] is False
    assert kwargs["period"] is None


async def test_collect_match_links_treats_empty_page_as_failure(scraper, site):
    """A page that yields zero links has not been collected, whatever the reason.

    A throttled or blocked page renders no rows at all. Counting it as a successful
    page is how a run silently returns page 1 only while reporting zero failures.
    """
    page1 = hrefs(1, RESULTS_PAGE_SIZE)
    # page 1 renders, pages 2 and 3 come back empty
    site.serve(1, listing(page1))
    site.serve(2, listing([]))
    site.serve(3, listing([]))

    result = await walk(scraper, floor=3)

    assert result.links == links(page1)
    assert result.successful_pages == 1, "an empty page must not count as collected"
    assert result.failed_pages == [2, 3]


async def test_collect_match_links_treats_partial_page_as_failure(scraper, site):
    """A page below the frontier is not the last one, so it must come back full (issue #78).

    A stalled lazy-load renders a handful of rows and the scroll still reports
    success, so fullness is the only signal left. Counting the page as collected
    is how a season loses 3 pages and still reports zero failures.
    """
    widget = [1, 2, 3]
    site.serve(1, listing(hrefs(1, RESULTS_PAGE_SIZE), widget=widget))
    site.serve(2, listing(hrefs(2, 5), widget=widget))  # stalled lazy-load: 5 rows out of 50
    site.serve(3, listing(hrefs(3, 1), widget=widget))

    result = await walk(scraper, floor=3)

    assert result.failed_pages == [2], "a page short of a full listing hides rows that were never discovered"
    assert result.successful_pages == 2, "a truncated page must not count as collected"
    assert links(hrefs(2, 1))[0] in result.links, "the rows it did render are still real data"


async def test_collect_match_links_refetches_a_truncated_page(scraper, site):
    """The truncation is transient, so the page is fetched again before being written off.

    Recovering in place beats losing the page: the alternative costs the user a full
    re-run of the season to recover one page (issue #78).
    """
    page1, page2 = hrefs(1, RESULTS_PAGE_SIZE), hrefs(2, RESULTS_PAGE_SIZE)
    # page 1 stalls at 5 rows, then renders in full on the second attempt
    site.serve(1, listing(page1[:5], widget=[1, 2]), listing(page1, widget=[1, 2]))
    site.serve(2, listing(page2[:3], widget=[1, 2]))

    result = await walk(scraper, floor=2)

    assert result.failed_pages == [], "a page that recovers on the second attempt was not lost"
    assert result.links == links(page1 + page2[:3])
    assert site.reads == [1, 1, 2], "page 1 fetched twice, page 2 once"


async def test_collect_match_links_refetches_a_truncated_page_only_once(scraper, site):
    """A page that stays truncated is reported, not retried forever."""
    page1 = hrefs(1, RESULTS_PAGE_SIZE)
    site.serve(1, listing(page1[:5], widget=[1, 2]))
    site.serve(2, listing(hrefs(2, 3), widget=[1, 2]))

    result = await walk(scraper, floor=2)

    assert result.failed_pages == [1]
    assert site.reads == [1, 1, 2], "page 1 fetched twice, then the walk moves on"


async def test_collect_match_links_keeps_single_empty_page_successful(scraper, site):
    """A genuinely empty season returns zero links on its only page, and that is not an error.

    Documented behaviour: OddsPortal answers HTTP 200 for a dead season URL, so an
    empty single-page result is the normal way to learn a combo is invalid.
    """
    site.serve(1, listing([]))

    result = await walk(scraper)

    assert result.links == []
    assert result.successful_pages == 1
    assert result.failed_pages == []


async def test_collect_match_links_walks_past_an_empty_widget(scraper, site, caplog):
    """Issue 79: an unreadable widget must not cap collection at one page.

    Page 1 shows no widget, so the floor is 1. Page 2's widget reports 8, which is
    when the true count becomes known.
    """
    widget = list(range(1, 9))
    site.serve(1, listing(hrefs(1, RESULTS_PAGE_SIZE)))
    for number in range(2, 8):
        site.serve(number, listing(hrefs(number, RESULTS_PAGE_SIZE), widget=widget))
    site.serve(8, listing(hrefs(8, 30), widget=widget))

    with caplog.at_level(logging.WARNING):
        result = await walk(scraper)

    assert len(result.links) == 380
    assert result.successful_pages == 8
    assert result.failed_pages == []
    assert any("but the walk collected" in r.message for r in caplog.records)


async def test_collect_match_links_walks_past_an_underreporting_widget(scraper, site):
    """A widget that reports fewer pages than exist must not end collection either."""
    for number in range(1, 8):
        site.serve(number, listing(hrefs(number, RESULTS_PAGE_SIZE), widget=[1, 2, 3]))
    site.serve(8, listing(hrefs(8, 30), widget=[1, 2, 3]))

    result = await walk(scraper, floor=3)

    assert len(result.links) == 380
    assert result.successful_pages == 8
    assert result.failed_pages == []


async def test_collect_match_links_fails_empty_page_despite_lower_mid_walk_observed_max(scraper, site):
    """A mid-walk widget read that only sees up to page 3 must not shrink the frontier.

    The base page promised 8 pages (frontier=8). Every in-walk widget read reports only
    [1, 2, 3], so observed_max stays 3, well below the frontier. Page 8 renders nothing.
    Comparing against observed_max instead of frontier would read this as STOP_COMPLETE
    and silently drop page 8; it must be PAGE_FAILED instead.
    """
    for number in range(1, 8):
        site.serve(number, listing(hrefs(number, RESULTS_PAGE_SIZE), widget=[1, 2, 3]))
    site.serve(8, listing([], widget=[1, 2, 3]))

    result = await walk(scraper, floor=8)

    assert result.failed_pages == [8]
    assert len(result.links) == 350
    assert result.successful_pages == 7


async def test_collect_match_links_stops_clean_one_page_past_the_end(scraper, site):
    """A season whose last page is exactly full: page 9 renders nothing but the widget still says 8."""
    widget = list(range(1, 9))
    for number in range(1, 9):
        site.serve(number, listing(hrefs(number, RESULTS_PAGE_SIZE), widget=widget))
    site.serve(9, listing([], widget=widget))

    result = await walk(scraper, floor=8)

    assert len(result.links) == 400
    assert result.successful_pages == 8, "the zero-link confirmation page is not itself collected"
    assert result.failed_pages == [], "walking one past the end is not a failure"


async def test_collect_match_links_flags_an_empty_page_the_widget_says_exists(scraper, site):
    """Gotcha 17: the widget says 8 pages and page 4 renders nothing, so page 4 was degraded."""
    widget = list(range(1, 9))
    for number in (1, 2, 3, 5, 6, 7):
        site.serve(number, listing(hrefs(number, RESULTS_PAGE_SIZE), widget=widget))
    site.serve(4, listing([], widget=widget))  # page 4 stays empty across its re-fetch
    site.serve(8, listing(hrefs(8, 30), widget=widget))

    result = await walk(scraper, floor=8)

    assert result.failed_pages == [4]
    assert len(result.links) == 330, "the run continues past a failed page"


async def test_collect_match_links_fails_a_short_page_with_incomplete_scroll(scraper, site):
    """Issue 79 recreated via scroll failure: a short page at the frontier whose scroll did not
    finish must be flagged as failed, not silently read as a clean, complete season.
    """
    widget = list(range(1, 9))
    scraper.scroller.scroll_until_loaded = AsyncMock(side_effect=[True] * 7 + [False, False])
    for number in range(1, 8):
        site.serve(number, listing(hrefs(number, RESULTS_PAGE_SIZE), widget=widget))
    # page 8 scrolls short on both attempts
    site.serve(8, listing(hrefs(8, 30), widget=widget))

    result = await walk(scraper, floor=8)

    assert result.successful_pages == 7
    assert result.failed_pages == [8], "an incompletely scrolled short page must not read as a clean stop"


async def test_collect_match_links_respects_the_page_limit(scraper, site, caplog):
    """An explicit page limit bounds the walk even when every page is full."""
    for number in range(1, 9):
        site.serve(number, listing(hrefs(number, RESULTS_PAGE_SIZE)))

    with caplog.at_level(logging.WARNING):
        result = await walk(scraper, page_limit=3)

    assert len(result.links) == 150
    assert result.successful_pages == 3
    assert any("raise --max-pages" in r.message for r in caplog.records)


async def test_scrape_matches_honors_regional_base_url(setup_scraper_mocks):
    """Direct match links must use the configured regional base URL."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    scraper.base_url = "https://regional.example"
    scraper.set_odds_format = AsyncMock()
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    match_link = "https://www.oddsportal.com/football/h2h/a-1/b-2/#EV123"

    await scraper.scrape_matches(
        match_links=[match_link],
        sport="football",
        markets=["1x2"],
    )

    page_mock.goto.assert_awaited_once_with(
        "https://regional.example",
        timeout=GOTO_TIMEOUT_LONG_MS,
        wait_until="domcontentloaded",
    )

    assert scraper.extract_match_odds.call_args.kwargs["match_links"] == [
        "https://regional.example/football/h2h/a-1/b-2/#EV123"
    ]


async def test_scrape_live_with_match_links_honors_regional_base_url(setup_scraper_mocks):
    """Direct live match links must use the configured regional base URL."""
    mocks = setup_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    scraper.base_url = "https://regional.example"
    scraper.set_odds_format = AsyncMock()
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_live(
        sport="football",
        markets=["1x2"],
        match_links=["https://www.oddsportal.com/football/h2h/a-1/b-2/#EV123"],
    )

    page_mock.goto.assert_awaited_once_with(
        "https://regional.example",
        timeout=GOTO_TIMEOUT_LONG_MS,
        wait_until="domcontentloaded",
    )

    assert scraper.extract_match_odds.call_args.kwargs["match_links"] == [
        "https://regional.example/football/h2h/a-1/b-2/inplay-odds/#EV123"
    ]


async def test_collect_historic_links_runs_on_its_own_tab_and_reports_failed_pages(scraper, site):
    """The season page, its pagination read and page 1 happen on a dedicated tab; lost pages come back as URLs."""
    widget = [1, 2, 3]
    page1, page2 = hrefs(1, RESULTS_PAGE_SIZE), hrefs(2, RESULTS_PAGE_SIZE)
    site.serve(1, listing(page1, widget=widget))
    site.serve(2, listing(page2, widget=widget))
    site.serve(3, listing([], widget=widget))

    listing_result = await scraper.collect_historic_links(
        sport="football", league="england-premier-league", season="2024-2025", max_pages=None
    )

    season_tab = site.tabs[0]
    assert season_tab.gotos == [(SEASON_URL, {"timeout": GOTO_TIMEOUT_MS, "wait_until": "domcontentloaded"})]
    scraper._warm_up_page.assert_awaited_once_with(season_tab)
    assert site.every_tab_closed_once()
    assert site.shared_tab.gotos == []
    assert listing_result.rows == [{"match_link": link} for link in links(page1 + page2)]
    assert listing_result.failed_page_urls == [f"{SEASON_URL}#page/3"]


async def test_collect_historic_links_closes_the_tab_when_the_season_redirects(scraper, site):
    """A redirected season raises before the walk; the tab must still be released (gotcha 4)."""
    site.redirects[SEASON_URL] = "https://www.oddsportal.com/football/england/premier-league/"

    with pytest.raises(PageNotFoundError):
        await scraper.collect_historic_links(sport="football", league="england-premier-league", season="2024-2025")

    assert [tab.closes for tab in site.tabs] == [1]


async def test_collect_historic_links_does_not_cap_a_single_entry_widget(scraper, site):
    """A widget showing one page number sets the floor even past --max-pages, so a short page below it failed.

    The season page loses its widget once scrolled, so only the floor read before the scroll knows page 3 exists.
    """
    page1 = hrefs(1, RESULTS_PAGE_SIZE)
    site.serve(1, listing(page1, widget=[3]), listing(page1))
    site.serve(2, listing(hrefs(2, 20)))
    scraper.scroller.scroll_until_loaded = AsyncMock(side_effect=_season_widget_gone_once_scrolled(site, page1))

    listing_result = await scraper.collect_historic_links(
        sport="football", league="england-premier-league", season="2024-2025", max_pages=2
    )

    assert listing_result.failed_page_urls == [f"{SEASON_URL}#page/2"]
    assert [row["match_link"] for row in listing_result.rows] == links(page1 + hrefs(2, 20))


async def test_collect_historic_links_refetches_a_truncated_first_page(scraper, site):
    """Page 1 read short of a full page below the frontier is fetched again, and only the full read is kept."""
    page1, page2 = hrefs(1, RESULTS_PAGE_SIZE), hrefs(2, 10)
    site.serve(1, listing(page1[:5], widget=[1, 2]), listing(page1, widget=[1, 2]))
    site.serve(2, listing(page2, widget=[1, 2]))

    listing_result = await scraper.collect_historic_links(
        sport="football", league="england-premier-league", season="2024-2025"
    )

    assert listing_result.failed_page_urls == []
    assert [row["match_link"] for row in listing_result.rows] == links(page1 + page2)
    assert site.every_tab_closed_once()
    assert site.reads == [1, 1, 2], "the short read on the season tab, then page 1 again"
    assert [tab.gotos[0][0] for tab in site.tabs] == [SEASON_URL, f"{SEASON_URL}#page/1", f"{SEASON_URL}#page/2"]


async def test_collect_historic_links_reads_page_one_on_the_season_tab(scraper, site):
    """Page 1 is read where the season page loaded: one load of it per season, the walk's tabs from page 2 on."""
    widget = [1, 2]
    site.serve(1, listing(hrefs(1, RESULTS_PAGE_SIZE), widget=widget))
    site.serve(2, listing(hrefs(2, 10), widget=widget))

    await scraper.collect_historic_links(sport="football", league="england-premier-league", season="2024-2025")

    assert site.gotos == [
        (SEASON_URL, {"timeout": GOTO_TIMEOUT_MS, "wait_until": "domcontentloaded"}),
        (f"{SEASON_URL}#page/2", {"timeout": GOTO_TIMEOUT_MS, "wait_until": "domcontentloaded"}),
    ]
    assert site.reads == [1, 2]
    assert len(site.pauses) == 2, "page 1 waits on the season tab as every walked page does"
    assert site.every_tab_closed_once()


async def test_the_patches_of_resolve_events_b_still_reach_the_historic_walk(scraper, site, monkeypatch):
    """resolve_events_b.py (betting_research, outside this repo) replaces two names to read each row's kickoff.

    It swaps BaseScraper.extract_match_links for a call of extract_match_rows(collect_kickoff=True) that keeps the
    kickoffs in a side dict, and wraps base_scraper._row_kickoff_datetime to fall back to noon of the row's date.
    Both functions below are its code, reformatted. The browser zone is None here, so the noon fallback is naive
    and its UTC value follows the host zone: the test checks only that the fallback ran.
    """
    kickoffs = {}

    async def _links_with_kickoff(
        self, page, date_filter=None, skip_started=False, kickoff_within_hours=None, sport=None
    ):
        rows = await self.extract_match_rows(
            page=page,
            date_filter=date_filter,
            skip_started=skip_started,
            kickoff_within_hours=kickoff_within_hours,
            collect_kickoff=True,
            sport=sport,
        )
        for r in rows:
            kickoffs[r["match_link"]] = r.get("kickoff_utc")
        return [r["match_link"] for r in rows]

    _orig_kick = base_scraper._row_kickoff_datetime

    def _kick_or_noon(row, row_date, tz):
        k = _orig_kick(row, row_date, tz)
        if k is None and row_date is not None:
            k = datetime.combine(row_date, time(12, 0), tzinfo=tz)
        return k

    monkeypatch.setattr(BaseScraper, "extract_match_links", _links_with_kickoff)
    monkeypatch.setattr(base_scraper, "_row_kickoff_datetime", _kick_or_noon)
    played, postponed, hockey = hrefs(1, 1), hrefs(1, 2)[1:], hrefs(1, 1, sport="hockey")
    site.serve(
        1,
        page(
            date_header("18 May 2025")
            + listing_row(played[0], status="15:00")
            + listing_row(postponed[0], status="postp.")
            + listing_row(hockey[0], status="16:00")
        ),
    )

    listing_result = await scraper.collect_historic_links(
        sport="football", league="england-premier-league", season="2024-2025"
    )

    assert [row["match_link"] for row in listing_result.rows] == links(played + postponed)
    assert list(kickoffs) == links(played + postponed)
    assert kickoffs[links(played)[0]] == "2025-05-18 15:00:00 UTC"
    assert kickoffs[links(postponed)[0]] is not None, "the patched _row_kickoff_datetime was not called"


def _page_with_country_links(count):
    page = MagicMock()
    locator = MagicMock()
    locator.count = AsyncMock(return_value=count)
    page.locator = MagicMock(return_value=locator)
    return page


async def test_league_guard_rejects_a_page_without_its_country_breadcrumb():
    """A league path that does not exist answers 200 at the same URL ("Offside — page not found")."""
    page = _page_with_country_links(0)

    with pytest.raises(PageNotFoundError, match="no-such-league"):
        await OddsPortalScraper._assert_league_page_exists(
            page, "https://www.oddsportal.com/football/bhutan/no-such-league/"
        )

    page.locator.assert_called_once_with("a[href='/football/bhutan/']")


async def test_league_guard_accepts_a_real_league_even_without_fixtures():
    await OddsPortalScraper._assert_league_page_exists(
        _page_with_country_links(2), "https://www.oddsportal.com/football/bhutan/premier-league/results/"
    )


BHUTAN = "football/bhutan/premier-league"
BHUTAN_PAGE = page('<a href="/football/bhutan/">Bhutan</a>' + listing_row(hrefs(1, 1)[0]))


async def test_upcoming_league_path_rate_limited_is_not_reported_as_missing(scraper, site):
    """The nginx 429 body has no country breadcrumb: it must not read as an unknown league."""
    site.status["https://www.oddsportal.com/football/bhutan/premier-league/"] = 429

    with pytest.raises(RateLimitError):
        await scraper.collect_upcoming_links(sport="football", date=None, league=BHUTAN)

    assert site.locators == [], "the league check never ran"
    assert [tab.closes for tab in site.tabs] == [1]


async def test_historic_listing_rate_limited_raises_rate_limit(scraper, site):
    site.status["https://www.oddsportal.com/football/bhutan/premier-league/results/"] = 429

    with pytest.raises(RateLimitError):
        await scraper.collect_historic_links(sport="football", league=BHUTAN, season=None)

    assert site.locators == [], "the league check never ran"
    assert site.reads == [], "the walk never started"


@pytest.mark.parametrize(("league", "guarded"), [(BHUTAN, True), ("england-premier-league", False)])
async def test_upcoming_checks_existence_of_league_paths_only(scraper, site, league, guarded):
    site.serve(1, BHUTAN_PAGE)

    await scraper.collect_upcoming_links(sport="football", date=None, league=league)

    assert site.locators == (["a[href='/football/bhutan/']"] if guarded else [])


async def test_historic_checks_existence_of_a_league_path(scraper, site):
    site.serve(1, listing(hrefs(1, 3)))

    with pytest.raises(PageNotFoundError):
        await scraper.collect_historic_links(sport="football", league=BHUTAN, season=None)

    assert site.locators == ["a[href='/football/bhutan/']"]
    assert site.reads == [], "the walk never started"
