from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import random

from playwright.async_api import Page

from oddsharvester.core.base_scraper import BaseScraper
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats
from oddsharvester.core.url_builder import URLBuilder, normalize_inplay_match_url
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
        proxy_manager=None,
    ):
        """Initializes Playwright using PlaywrightManager."""
        await self.playwright_manager.initialize(
            headless=headless,
            user_agent=browser_user_agent,
            locale=browser_locale_timezone,
            timezone_id=browser_timezone_id,
            proxy_manager=proxy_manager,
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
        concurrent_scraping_task: int = 3,
        links_only: bool = False,
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
            links_only (bool): If True, stop after link collection and return the links (no odds scraping).

        Returns:
            ScrapeResult: Contains successful results, failed URLs, and statistics.
        """
        current_page = self.playwright_manager.page
        if not current_page:
            raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")

        base_url = URLBuilder.get_historic_matches_url(
            sport=sport, league=league, season=season, base_url=self.base_url
        )
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

        if links_only:
            self.logger.info(f"Links-only mode: returning {len(link_result.links)} match links without odds.")
            return self._links_only_result(
                links=link_result.links,
                context={"sport": sport, "league": league, "season": season},
                failed_page_urls=[f"{base_url}#/page/{p}" for p in link_result.failed_pages],
            )

        # Extract odds from all collected links
        self.logger.info("Step 3: Extracting odds from collected match links...")
        self.logger.info(f"Total unique matches to process: {len(link_result.links)}")

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

        # A failed listing page loses an entire page of matches that were never
        # discovered, so it cannot show up as a per-match failure. Surface it here
        # or the run reports 100% success on an incomplete dataset.
        if link_result.failed_pages:
            listing_failures = self._listing_page_failures(base_url, link_result.failed_pages)
            result.failed.extend(listing_failures)
            result.stats.failed += len(listing_failures)
            result.stats.total_urls += len(listing_failures)

        return result

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
        concurrent_scraping_task: int = 3,
        include_started: bool = False,
        kickoff_within_hours: float | None = None,
        links_only: bool = False,
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
            include_started (bool): If True, also return matches that have
                already started or finished. Default False keeps the listing
                page's true "upcoming" semantics (GitHub issue #58).
            kickoff_within_hours (Optional[float]): If set, only scrape matches
                kicking off within this many hours from now, cutting request
                volume by skipping far-off matches (GitHub issue #77).
            links_only (bool): If True, stop after link collection and return the links (no odds scraping).

        Returns:
            ScrapeResult: Contains successful results, failed URLs, and statistics.
        """
        current_page = self.playwright_manager.page
        if not current_page:
            raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")

        url = URLBuilder.get_upcoming_matches_url(sport=sport, date=date, league=league, base_url=self.base_url)
        self.logger.info(f"Fetching upcoming odds from {url}")

        await current_page.goto(url, timeout=GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
        await self._prepare_page_for_scraping(page=current_page)

        # Scroll to load all matches due to lazy loading
        self.logger.info("Scrolling page to load all upcoming matches...")
        await self.scroller.scroll_until_loaded(
            page=current_page,
            timeout=30,
            scroll_pause_time=2,
            max_scroll_attempts=3,
            content_check_selector="div[class*='eventRow']",
        )

        # League page shows all upcoming dates; when a specific date is requested,
        # post-filter links by the date-header rendered above each row group.
        date_filter = None
        if league and date:
            try:
                date_filter = datetime.strptime(date, "%Y%m%d").date()
                self.logger.info(f"Applying date filter for league page: {date_filter.isoformat()}")
            except ValueError:
                self.logger.warning(f"Could not parse date '{date}' for filtering; returning all league matches.")

        match_links = await self.extract_match_links(
            page=current_page,
            date_filter=date_filter,
            skip_started=not include_started,
            kickoff_within_hours=kickoff_within_hours,
        )

        if not match_links:
            self.logger.warning("No match links found for upcoming matches.")
            return ScrapeResult()

        if links_only:
            self.logger.info(f"Links-only mode: returning {len(match_links)} match links without odds.")
            return self._links_only_result(
                links=match_links,
                context={"sport": sport, "league": league, "date": date, "season": None},
            )

        return await self.extract_match_odds(
            sport=sport,
            match_links=match_links,
            markets=markets,
            scrape_odds_history=scrape_odds_history,
            target_bookmaker=target_bookmaker,
            concurrent_scraping_task=concurrent_scraping_task,
            preview_submarkets_only=self.preview_submarkets_only,
            bookies_filter=bookies_filter,
            period=period,
            request_delay=request_delay,
        )

    async def scrape_live(
        self,
        sport: str,
        league: str | None = None,
        markets: list[str] | None = None,
        match_links: list[str] | None = None,
        target_bookmaker: str | None = None,
        bookies_filter: BookiesFilter = BookiesFilter.ALL,
        request_delay: float = DEFAULT_REQUEST_DELAY_S,
        concurrent_scraping_task: int = 3,
        links_only: bool = False,
    ) -> ScrapeResult:
        """
        Scrapes a one-shot snapshot of in-play odds for currently live matches.

        Listing source is /inplay-odds/live-now/<sport>/; each match is scraped
        on its in-play view (per-bookmaker live odds plus live score/period).
        When `match_links` is given the listing is skipped and those URLs are
        normalized to their in-play form, which is the building block for
        external re-sampling of a known match.

        Args:
            sport (str): The sport to scrape.
            league (Optional[str]): Single league slug filter, applied after listing.
            markets (Optional[List[str]]): List of markets.
            match_links (Optional[List[str]]): Scrape these matches directly.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.
            links_only (bool): If True, return collected live links without odds.

        Returns:
            ScrapeResult: Contains successful results, failed URLs, and statistics.
        """
        current_page = self.playwright_manager.page
        if not current_page:
            raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")

        if match_links:
            links = [normalize_inplay_match_url(link) for link in match_links]
            await current_page.goto(ODDSPORTAL_BASE_URL, timeout=GOTO_TIMEOUT_LONG_MS, wait_until="domcontentloaded")
            await self._prepare_page_for_scraping(page=current_page)
        else:
            url = URLBuilder.get_live_matches_url(sport=sport, base_url=self.base_url)
            self.logger.info(f"Fetching live matches from {url}")

            await current_page.goto(url, timeout=GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
            await self._prepare_page_for_scraping(page=current_page)
            await self.scroller.scroll_until_loaded(
                page=current_page,
                timeout=30,
                scroll_pause_time=2,
                max_scroll_attempts=3,
                content_check_selector=f"div[data-testid='{OddsPortalSelectors.GAME_ROW_TESTID}']",
            )

            rows = await self.extract_live_match_links(page=current_page, sport=sport, league=league)
            if not rows:
                self.logger.info("No live matches found on the live-now listing.")
                return ScrapeResult()
            links = [row["match_link"] for row in rows]

        if links_only:
            self.logger.info(f"Links-only mode: returning {len(links)} live match links without odds.")
            return self._links_only_result(links=links, context={"sport": sport, "league": league})

        result = await self.extract_match_odds(
            sport=sport,
            match_links=links,
            markets=markets,
            scrape_odds_history=False,
            target_bookmaker=target_bookmaker,
            concurrent_scraping_task=concurrent_scraping_task,
            preview_submarkets_only=self.preview_submarkets_only,
            bookies_filter=bookies_filter,
            period=None,
            request_delay=request_delay,
            live_mode=True,
        )

        ended = [d for d in result.success if d.get("_live_ended")]
        if ended:
            self.logger.info(f"{len(ended)} matches ended between listing and scrape; dropped from output.")
            result.success = [d for d in result.success if not d.get("_live_ended")]
            result.stats.successful -= len(ended)
            result.stats.total_urls -= len(ended)

        return result

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
        concurrent_scraping_task: int = 3,
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
            concurrent_scraping_task=concurrent_scraping_task,
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
        await self.cookie_dismisser.dismiss(page=page)

    @staticmethod
    def _listing_page_failures(base_url: str, failed_pages: list[int]) -> list[FailedUrl]:
        """Build the failure entries for listing pages that could not be collected."""
        return [
            FailedUrl(
                url=f"{base_url}#/page/{page}",
                error_type=ErrorType.LISTING_PAGE,
                error_message="Failed to collect links from listing page",
            )
            for page in failed_pages
        ]

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
                error_type=ErrorType.LISTING_PAGE,
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

        # Apply page limit: explicit --max-pages overrides the default safety cap
        effective_limit = max_pages if max_pages else MAX_PAGINATION_PAGES
        if len(pages_to_scrape) > effective_limit:
            self.logger.warning(
                f"Pagination has {len(pages_to_scrape)} pages, limiting to {effective_limit} "
                f"({'--max-pages' if max_pages else 'safety cap'})."
            )
            pages_to_scrape = pages_to_scrape[:effective_limit]
        else:
            self.logger.info(f"Will scrape all {len(pages_to_scrape)} pages (limit: {effective_limit})")

        self.logger.info(f"Final pages to scrape: {pages_to_scrape}")
        return pages_to_scrape

    def _fill_pagination_gaps(self, raw_pages: list[int]) -> list[int]:
        """
        Sort, deduplicate, and fill gaps in discovered pagination pages.

        OddsPortal renders pagination with an ellipsis for large page ranges
        (e.g. ``[1,2,3,...,28]``), so the HTML only contains the endpoints.
        This method fills the gap so all intermediate pages are scraped.

        Args:
            raw_pages (List[int]): Raw page numbers found in pagination.

        Returns:
            List[int]: Contiguous list of pages from 1..max.
        """
        if len(raw_pages) <= 1:
            return raw_pages

        max_page = max(raw_pages)
        all_pages = list(range(1, max_page + 1))
        self.logger.info(
            f"Pagination HTML showed {sorted(set(raw_pages))}, "
            f"filling to contiguous range 1..{max_page} ({len(all_pages)} pages)"
        )

        return all_pages

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
                scroll_success = await self.scroller.scroll_until_loaded(
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

                # Pagination promised this page exists, so zero rows means it did not
                # render: throttled, blocked, or a parse failure that extract_match_links
                # swallowed into an empty list. Counting it as collected is how a run
                # silently returns page 1 only while reporting no failures at all.
                # A single planned page is different: an empty season legitimately has
                # one empty page, which is the documented way to spot an invalid combo.
                if not links and len(pages_to_scrape) > 1:
                    result.failed_pages.append(page_number)
                    self.logger.warning(f"Page {page_number} returned no links; treating it as failed.")
                    continue

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

        result.links = list(dict.fromkeys(all_links))
        self.logger.info("Collection Summary:")
        self.logger.info(f"   - Total pages processed: {len(pages_to_scrape)}")
        self.logger.info(f"   - Successful pages: {result.successful_pages}")
        self.logger.info(f"   - Failed pages: {len(result.failed_pages)}")
        self.logger.info(f"   - Total links found: {len(all_links)}")
        self.logger.info(f"   - Unique links: {len(result.links)}")

        if result.failed_pages:
            self.logger.warning(f"Failed to collect links from pages: {result.failed_pages}")

        return result
