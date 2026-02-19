from dataclasses import dataclass, field
from enum import Enum
import random

from playwright.async_api import Page

from oddsharvester.core.base_scraper import BaseScraper
from oddsharvester.core.scrape_result import ScrapeResult
from oddsharvester.core.url_builder import URLBuilder
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.constants import (
    DEFAULT_REQUEST_DELAY_S,
    GOTO_TIMEOUT_LONG_MS,
    GOTO_TIMEOUT_MS,
    MAX_PAGINATION_PAGES,
    ODDSPORTAL_BASE_URL,
    PAGE_COLLECTION_DELAY_MAX_MS,
    PAGE_COLLECTION_DELAY_MIN_MS,
)


@dataclass
class LinkCollectionResult:
    """Result of collecting match links from pages."""

    links: list[str] = field(default_factory=list)
    successful_pages: int = 0
    failed_pages: list[int] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        return self.successful_pages + len(self.failed_pages)


class OddsPortalScraper(BaseScraper):
    """
    Main class that manages the scraping workflow from OddsPortal.
    """

    async def start_playwright(
        self,
        headless: bool = True,
        browser_user_agent: str | None = None,
        browser_locale_timezone: str | None = None,
        browser_timezone_id: str | None = None,
        proxy: dict[str, str] | None = None,
    ):
        """
        Initializes Playwright using PlaywrightManager.

        Args:
            headless (bool): Whether to run Playwright in headless mode.
            proxy (Optional[Dict[str, str]]): Proxy configuration if needed.
        """
        await self.playwright_manager.initialize(
            headless=headless,
            user_agent=browser_user_agent,
            locale=browser_locale_timezone,
            timezone_id=browser_timezone_id,
            proxy=proxy,
        )

    async def stop_playwright(self):
        """Stops Playwright and cleans up resources."""
        await self.playwright_manager.cleanup()

    async def scrape_historic(
        self,
        sport: str,
        league: str,
        season: str,
        markets: list[str] | None = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        max_pages: int | None = None,
        bookies_filter: BookiesFilter = BookiesFilter.ALL,
        period: Enum | None = None,
        request_delay: float = DEFAULT_REQUEST_DELAY_S,
    ) -> ScrapeResult:
        """
        Scrapes historical odds data.

        Args:
            sport (str): The sport to scrape.
            league (str): The league to scrape.
            season (str): The season to scrape.
            markets (Optional[List[str]]): List of markets.
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.
            max_pages (Optional[int]): Maximum number of pages to scrape (default is None for all pages).

        Returns:
            ScrapeResult: Contains successful results, failed URLs, and statistics.
        """
        current_page = self.playwright_manager.page
        if not current_page:
            raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")

        base_url = URLBuilder.get_historic_matches_url(sport=sport, league=league, season=season)
        self.logger.info(f"Starting historic scraping for {sport} - {league} - {season}")
        self.logger.info(f"Base URL: {base_url}")
        self.logger.info(f"Max pages parameter: {max_pages}")

        # Navigate to the base URL
        self.logger.info("Navigating to base URL...")
        await current_page.goto(base_url)
        await self._prepare_page_for_scraping(page=current_page)

        # Analyze pagination and determine pages to scrape
        self.logger.info("Step 1: Analyzing pagination information...")
        pages_to_scrape = await self._get_pagination_info(page=current_page, max_pages=max_pages)

        # Collect match links from all pages
        self.logger.info("Step 2: Collecting match links from all pages...")
        link_result = await self._collect_match_links(base_url=base_url, pages_to_scrape=pages_to_scrape)

        if link_result.failed_pages:
            self.logger.warning(f"Failed to collect links from pages: {link_result.failed_pages}")

        # Extract odds from all collected links
        self.logger.info("Step 3: Extracting odds from collected match links...")
        self.logger.info(f"Total unique matches to process: {len(link_result.links)}")

        return await self.extract_match_odds(
            sport=sport,
            match_links=link_result.links,
            markets=markets,
            scrape_odds_history=scrape_odds_history,
            target_bookmaker=target_bookmaker,
            preview_submarkets_only=self.preview_submarkets_only,
            bookies_filter=bookies_filter,
            period=period,
            request_delay=request_delay,
        )

    async def scrape_upcoming(
        self,
        sport: str,
        date: str,
        league: str | None = None,
        markets: list[str] | None = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        bookies_filter: BookiesFilter = BookiesFilter.ALL,
        period: Enum | None = None,
        request_delay: float = DEFAULT_REQUEST_DELAY_S,
    ) -> ScrapeResult:
        """
        Scrapes upcoming match odds.

        Args:
            sport (str): The sport to scrape.
            date (str): The date to scrape.
            league (Optional[str]): The league to scrape.
            markets (Optional[List[str]]): List of markets.
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.

        Returns:
            ScrapeResult: Contains successful results, failed URLs, and statistics.
        """
        current_page = self.playwright_manager.page
        if not current_page:
            raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")

        url = URLBuilder.get_upcoming_matches_url(sport=sport, date=date, league=league)
        self.logger.info(f"Fetching upcoming odds from {url}")

        await current_page.goto(url, timeout=GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
        await self._prepare_page_for_scraping(page=current_page)

        # Scroll to load all matches due to lazy loading
        self.logger.info("Scrolling page to load all upcoming matches...")
        await self.browser_helper.scroll_until_loaded(
            page=current_page,
            timeout=30,
            scroll_pause_time=2,
            max_scroll_attempts=3,
            content_check_selector="div[class*='eventRow']",
        )

        match_links = await self.extract_match_links(page=current_page)

        if not match_links:
            self.logger.warning("No match links found for upcoming matches.")
            return ScrapeResult()

        return await self.extract_match_odds(
            sport=sport,
            match_links=match_links,
            markets=markets,
            scrape_odds_history=scrape_odds_history,
            target_bookmaker=target_bookmaker,
            preview_submarkets_only=self.preview_submarkets_only,
            bookies_filter=bookies_filter,
            period=period,
            request_delay=request_delay,
        )

    async def scrape_matches(
        self,
        match_links: list[str],
        sport: str,
        markets: list[str] | None = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        bookies_filter: BookiesFilter = BookiesFilter.ALL,
        period: Enum | None = None,
        request_delay: float = DEFAULT_REQUEST_DELAY_S,
    ) -> ScrapeResult:
        """
        Scrapes match odds from a list of specific match URLs.

        Args:
            match_links (List[str]): List of URLs of matches to scrape.
            sport (str): The sport to scrape.
            markets (List[str] | None): List of betting markets to scrape. Defaults to None.
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.

        Returns:
            ScrapeResult: Contains successful results, failed URLs, and statistics.
        """
        current_page = self.playwright_manager.page
        if not current_page:
            raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")

        await current_page.goto(ODDSPORTAL_BASE_URL, timeout=GOTO_TIMEOUT_LONG_MS, wait_until="domcontentloaded")
        await self._prepare_page_for_scraping(page=current_page)
        return await self.extract_match_odds(
            sport=sport,
            match_links=match_links,
            markets=markets,
            scrape_odds_history=scrape_odds_history,
            target_bookmaker=target_bookmaker,
            concurrent_scraping_task=len(match_links),
            preview_submarkets_only=self.preview_submarkets_only,
            bookies_filter=bookies_filter,
            period=period,
            request_delay=request_delay,
        )

    async def _prepare_page_for_scraping(self, page: Page):
        """
        Prepares the Playwright page for scraping by setting odds format and dismissing banners.

        Args:
            page: Playwright page instance.
        """
        await self.set_odds_format(page=page)
        await self.browser_helper.dismiss_cookie_banner(page=page)

    async def _get_pagination_info(self, page: Page, max_pages: int | None) -> list[int]:
        """
        Extracts pagination details from the page.

        Args:
            page: Playwright page instance.
            max_pages (Optional[int]): Maximum pages to scrape.

        Returns:
            List[int]: List of pages to scrape.
        """
        self.logger.info("Analyzing pagination information...")

        # Find all pagination links
        pagination_links = await page.query_selector_all("a.pagination-link:not([rel='next'])")
        self.logger.info(f"Found {len(pagination_links)} pagination links")

        # Extract page numbers
        total_pages = []
        for link in pagination_links:
            try:
                text = await link.inner_text()
                if text.isdigit():
                    page_num = int(text)
                    total_pages.append(page_num)
                    self.logger.debug(f"Found pagination link: {page_num}")
            except Exception as e:
                self.logger.warning(f"Error processing pagination link: {e}")

        if not total_pages:
            self.logger.info("No pagination found; scraping only the current page.")
            return [1]

        # Sort and log all available pages
        total_pages = sorted(total_pages)
        self.logger.info(f"Raw pagination pages found: {total_pages}")

        # Check for gaps in pagination (e.g., [1,2,3,4,5,6,7,8,9,10,27] -> missing 11-26)
        pages_to_scrape = self._fill_pagination_gaps(total_pages)

        self.logger.info(f"Maximum pages parameter: {max_pages}")

        # Apply max_pages limit if provided
        if max_pages:
            pages_to_scrape = pages_to_scrape[:max_pages]
            self.logger.info(f"Limited to first {max_pages} pages due to max_pages parameter")
        else:
            self.logger.info(f"No page limit applied, will scrape all {len(pages_to_scrape)} pages")

        self.logger.info(f"Final pages to scrape: {pages_to_scrape}")
        return pages_to_scrape

    def _fill_pagination_gaps(self, raw_pages: list[int]) -> list[int]:
        """
        Sort, deduplicate, and cap discovered pagination pages.

        Trusts the pages discovered in the pagination HTML rather than generating
        phantom pages to fill gaps (e.g., [1, 2, 3, 27] stays as-is instead of
        becoming [1..27]).

        Args:
            raw_pages (List[int]): Raw page numbers found in pagination.

        Returns:
            List[int]: Sorted, deduplicated list of pages capped at MAX_PAGINATION_PAGES.
        """
        if len(raw_pages) <= 1:
            return raw_pages

        # Sort and deduplicate
        unique_pages = sorted(set(raw_pages))
        self.logger.info(f"Discovered {len(unique_pages)} unique pagination pages: {unique_pages}")

        # Apply safety cap
        if len(unique_pages) > MAX_PAGINATION_PAGES:
            self.logger.warning(
                f"Pagination exceeds safety cap ({len(unique_pages)} > {MAX_PAGINATION_PAGES}). "
                f"Limiting to first {MAX_PAGINATION_PAGES} pages."
            )
            unique_pages = unique_pages[:MAX_PAGINATION_PAGES]

        return unique_pages

    async def _collect_match_links(self, base_url: str, pages_to_scrape: list[int]) -> LinkCollectionResult:
        """
        Collects match links from multiple pages.

        Args:
            base_url (str): The base URL of the historic matches.
            pages_to_scrape (List[int]): Pages to scrape.

        Returns:
            LinkCollectionResult: Contains links found and tracking of successful/failed pages.
        """
        self.logger.info(f"Starting collection of match links from {len(pages_to_scrape)} pages")
        self.logger.info(f"Pages to process: {pages_to_scrape}")

        result = LinkCollectionResult()
        all_links = []

        for i, page_number in enumerate(pages_to_scrape, 1):
            self.logger.info(f"Processing page {i}/{len(pages_to_scrape)}: {page_number}")
            tab = None

            try:
                tab = await self.playwright_manager.context.new_page()
                self.logger.debug(f"Created new tab for page {page_number}")

                page_url = f"{base_url}#/page/{page_number}"
                self.logger.info(f"Navigating to: {page_url}")
                await tab.goto(page_url, timeout=GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
                delay = random.randint(PAGE_COLLECTION_DELAY_MIN_MS, PAGE_COLLECTION_DELAY_MAX_MS)  # noqa: S311
                self.logger.debug(f"Waiting {delay}ms before processing...")
                await tab.wait_for_timeout(delay)

                self.logger.info(f"Scrolling page {page_number} to load all matches...")
                scroll_success = await self.browser_helper.scroll_until_loaded(
                    page=tab,
                    timeout=30,
                    scroll_pause_time=2,
                    max_scroll_attempts=3,
                    content_check_selector="div[class*='eventRow']",
                )

                if scroll_success:
                    self.logger.debug(f"Successfully scrolled page {page_number}")
                else:
                    self.logger.warning(f"Scrolling may not have completed for page {page_number}")

                self.logger.info(f"Extracting match links from page {page_number}...")
                links = await self.extract_match_links(page=tab)
                all_links.extend(links)
                result.successful_pages += 1
                self.logger.info(f"Extracted {len(links)} links from page {page_number}")

            except Exception as e:
                result.failed_pages.append(page_number)
                self.logger.error(f"Error processing page {page_number}: {e}")

            finally:
                if tab:
                    await tab.close()
                    self.logger.debug(f"Closed tab for page {page_number}")

        result.links = list(set(all_links))
        self.logger.info("Collection Summary:")
        self.logger.info(f"   - Total pages processed: {len(pages_to_scrape)}")
        self.logger.info(f"   - Successful pages: {result.successful_pages}")
        self.logger.info(f"   - Failed pages: {len(result.failed_pages)}")
        self.logger.info(f"   - Total links found: {len(all_links)}")
        self.logger.info(f"   - Unique links: {len(result.links)}")

        if result.failed_pages:
            self.logger.warning(f"Failed to collect links from pages: {result.failed_pages}")

        return result
