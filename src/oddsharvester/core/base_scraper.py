import asyncio
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from enum import Enum
import logging
from typing import Any
from urllib.parse import urldefrag, urlsplit

from bs4 import BeautifulSoup
from playwright.async_api import Page

from oddsharvester.core.browser import warm_up
from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.hydration import dismiss_login_modal, hydrate_match_view
from oddsharvester.core.browser.pagination import PaginationWalker
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.browser.selection import (
    BOOKIES_FILTER_STRATEGY,
    SelectionManager,
)
from oddsharvester.core.browser.waits import wait_for_signal
from oddsharvester.core.exceptions import H2HFragmentResolutionError, MarketDataError, MatchContentError, RateLimitError
from oddsharvester.core.listing import (
    _is_league_link,
    _listing_elements,
    _ListingRows,
    _parse_date_header,
    _row_has_started,
    _row_kickoff_datetime,
)
from oddsharvester.core.match_details import _history_reference, _parse_live_info, _parse_match_details
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import (
    RequestPacer,
    RetryConfig,
    classify_error,
    is_proxy_attributable_error,
    is_retryable_error,
    retry_with_backoff,
)
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats
from oddsharvester.core.url_builder import URLBuilder
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.constants import (
    DEFAULT_REQUEST_DELAY_S,
    DYNAMIC_CONTENT_WAIT_MS,
    MATCH_RETRY_BASE_DELAY,
    MATCH_RETRY_MAX_ATTEMPTS,
    MATCH_RETRY_MAX_DELAY,
    NAVIGATION_TIMEOUT_MS,
    ODDSPORTAL_BASE_URL,
    PROXY_WARM_UP_ATTEMPTS,
    RATE_LIMIT_RETRY_DELAY_S,
)
from oddsharvester.utils.datetime_format import format_utc
from oddsharvester.utils.odds_format_enum import OddsFormat


class BaseScraper:
    """
    Base class for scraping match data from OddsPortal.
    """

    def __init__(
        self,
        playwright_manager: PlaywrightManager,
        market_extractor: OddsPortalMarketExtractor,
        scroller: PageScroller,
        cookie_dismisser: CookieDismisser,
        selection_manager: SelectionManager,
        preview_submarkets_only: bool = False,
        local_kickoff: bool = False,
        base_url: str | None = None,
        on_match: Callable[[dict[str, Any]], None] | None = None,
    ):
        """
        Args:
            playwright_manager (PlaywrightManager): Handles Playwright lifecycle.
            market_extractor (OddsPortalMarketExtractor): Handles market scraping.
            scroller (PageScroller): Handles incremental page scrolling.
            cookie_dismisser (CookieDismisser): Handles cookie banner dismissal.
            selection_manager (SelectionManager): Manages bookies filter and period selection.
            preview_submarkets_only (bool): If True, only scrape the collapsed submarket odds (best/highest shown
            per line, not per-bookmaker) from visible submarkets without loading individual bookmaker details.
            local_kickoff (bool): If True, add venue_timezone and match_date_venue_local (kickoff converted to
            the venue's local time) to each record. match_date stays UTC.
            base_url (str | None): Regional OddsPortal domain override (scheme+host). When None, the canonical
            https://www.oddsportal.com is used.
            on_match (Callable | None): Called with each match record as soon as it is scraped, before the
            whole run completes. When None, results are only returned at the end.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.playwright_manager = playwright_manager
        self.market_extractor = market_extractor
        self.scroller = scroller
        self.cookie_dismisser = cookie_dismisser
        self.selection_manager = selection_manager
        self.preview_submarkets_only = preview_submarkets_only
        self.local_kickoff = local_kickoff
        self.base_url = base_url
        self.on_match = on_match
        self._warmed_proxy_keys: set[str] = set()
        self.pagination_walker = PaginationWalker()
        # The day of the date header each row was grouped under, by match link, from every listing page read.
        self._row_days: dict[str, str | None] = {}

    async def set_odds_format(
        self, page: Page, odds_format: OddsFormat = OddsFormat.DECIMAL_ODDS, strict: bool = False
    ) -> None:
        """Set the odds format on the page (`warm_up.set_odds_format`), logging on this scraper's logger."""
        await warm_up.set_odds_format(page, self.logger, odds_format=odds_format, strict=strict)

    async def extract_match_rows(
        self,
        page: Page,
        date_filter: date | None = None,
        skip_started: bool = False,
        kickoff_within_hours: float | None = None,
        collect_kickoff: bool = False,
        sport: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract and parse match rows from the current page.

        Event rows on OddsPortal listing pages are grouped by date: a group is
        introduced by a date-header element and the rows that follow it inherit
        that date. When `date_filter`
        is provided, rows are iterated in document order, the "current" date
        header is tracked, and only rows whose group matches the filter are
        kept.

        Args:
            page (Page): A Playwright Page instance for this task.
            date_filter (Optional[date]): If provided, keep only match links
                whose surrounding date-header matches this date. Rows under a
                date-header that cannot be parsed are kept (fail-safe).
            skip_started (bool): If True, drop rows that are live or finished
                (see `_row_has_started` for detection). Fail-safe on DOM drift.
            kickoff_within_hours (Optional[float]): If provided, keep only rows
                whose kickoff is at most this many hours ahead of now. Rows whose
                kickoff cannot be computed are kept (fail-safe). Combines the
                row's date-header with its HH:MM, read at the browser timezone's
                UTC offset of the scrape moment (issue #77, gotchas §10); pair
                with skip_started to bound the window on both sides.
            collect_kickoff (bool): If True, resolve each row's kickoff and emit
                it as `kickoff_utc`.
            sport (Optional[str]): The requested sport. When given, rows whose href
                is not under the sport's site path (`/<site_slug>/`) are dropped and
                counted, so a listing that serves another sport never passes its
                matches off as this one's.

        Returns:
            List[dict]: One entry per unique match link, each carrying
                `match_link` and `kickoff_utc` (None when undeterminable). The
                day of each row's date header (ISO, None without one) goes to
                `self._row_days`, where the historic walk reads it whatever
                replaced `extract_match_links`.

        Raises:
            Exception: Whatever reading or parsing the page raised, so the caller
                records a failed listing instead of an empty one.
        """
        try:
            # Rows are the match <a> elements and date headers are leaf elements holding the group date.
            elements = await _listing_elements(
                page,
                lambda el: el.name in ("a", "div", "span", "p")
                and (
                    OddsPortalSelectors.is_match_link(el)
                    or (OddsPortalSelectors.is_date_header(el) and not OddsPortalSelectors.is_hidden(el))
                ),
            )
            row_count = sum(1 for el in elements if OddsPortalSelectors.is_match_link(el))
            self.logger.info(f"Found {row_count} event rows.")

            need_kickoff = kickoff_within_hours is not None or collect_kickoff
            track_headers = date_filter is not None or need_kickoff
            tz_name = getattr(self.playwright_manager, "timezone_id", None)

            window_cutoff: datetime | None = None
            if kickoff_within_hours is not None:
                window_cutoff = datetime.now(UTC) + timedelta(hours=kickoff_within_hours)

            rows = _ListingRows(sport, self.base_url or ODDSPORTAL_BASE_URL)
            rows_out: list[dict[str, Any]] = []
            without_event: list[str] = []
            current_row_date: date | None = None
            seen_header_dates: set[date] = set()
            filtered_out_count = 0
            unparseable_header_count = 0
            started_filtered_out_count = 0
            window_filtered_out_count = 0

            for el in elements:
                if not OddsPortalSelectors.is_match_link(el):
                    header_text = el.get_text(" ", strip=True)
                    current_row_date = _parse_date_header(header_text, tz_name=tz_name)
                    if current_row_date is not None:
                        seen_header_dates.add(current_row_date)
                    elif track_headers:
                        unparseable_header_count += 1
                        self.logger.warning(
                            f"Could not parse date-header '{header_text}'; rows under it will not be filtered."
                        )
                    continue

                row = el
                href = rows.href(row)
                if href is None:
                    continue
                if "#" not in href:
                    without_event.append(href)

                if date_filter is not None and current_row_date is not None and current_row_date != date_filter:
                    filtered_out_count += 1
                    continue

                if skip_started and _row_has_started(row):
                    started_filtered_out_count += 1
                    continue

                # Looked up in this module's globals, where resolve_events_b.py replaces it to read each kickoff.
                kickoff_dt = _row_kickoff_datetime(row, current_row_date, tz_name) if need_kickoff else None

                if window_cutoff is not None and kickoff_dt is not None and kickoff_dt > window_cutoff:
                    window_filtered_out_count += 1
                    continue

                kickoff_utc = format_utc(kickoff_dt) if collect_kickoff and kickoff_dt is not None else None

                link = rows.link(href)
                if link is not None:
                    rows_out.append({"match_link": link, "kickoff_utc": kickoff_utc})
                    self._row_days[link] = current_row_date.isoformat() if current_row_date else None

            started_suffix = f", {started_filtered_out_count} started/finished rows skipped" if skip_started else ""
            window_suffix = (
                f", {window_filtered_out_count} rows outside the {kickoff_within_hours}h kickoff window"
                if kickoff_within_hours is not None
                else ""
            )
            if date_filter is not None:
                self.logger.info(
                    f"Extracted {len(rows_out)} unique match links after date filtering "
                    f"(filter={date_filter.isoformat()}, filtered out {filtered_out_count} rows, "
                    f"{unparseable_header_count} unparseable headers, "
                    f"{rows.counts()}{started_suffix}{window_suffix})."
                )
                if not rows_out and filtered_out_count:
                    headers_label = ", ".join(d.isoformat() for d in sorted(seen_header_dates)) or "none"
                    self.logger.warning(
                        f"Date filter {date_filter.isoformat()} matched 0 matches although "
                        f"{filtered_out_count} rows were present under other dates. Date headers "
                        f"on the page (grouped in browser timezone '{tz_name or 'UTC'}'): {headers_label}. "
                        f"If the expected matches kick off late and land on an adjacent calendar day, "
                        f"pass --timezone to align the listing with the competition's region."
                    )
            else:
                self.logger.info(
                    f"Extracted {len(rows_out)} unique match links ({rows.counts()}{started_suffix}{window_suffix})."
                )

            rows.warn_if_all_foreign(self.logger, "listing")
            rows.warn_if_all_hidden(self.logger, "listing", page.url)
            if without_event:
                self.logger.warning(
                    f"{len(without_event)} visible match links of this listing ({page.url}) carry no event id, "
                    f"first {without_event[0]}: real rows carry '#<event>', the anti-bot trap clone does not "
                    "(gotchas §28)."
                )
            return rows_out

        except Exception as e:
            self.logger.error(f"Error extracting match links: {e}", exc_info=True)
            raise

    async def extract_match_links(self, page: Page, sport: str | None = None) -> list[str]:
        """Collect match links from a listing page: the links of `extract_match_rows`, the historic walk's page read."""
        rows = await self.extract_match_rows(page=page, sport=sport)
        return [row["match_link"] for row in rows]

    async def extract_live_match_links(
        self,
        page: Page,
        sport: str | None = None,
        league: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract match links from a live-now in-play listing.

        Rows are the match <a> elements, whose hrefs here carry the
        `/inplay-odds/#<id>` suffix. The same match can appear twice in the DOM,
        so rows are deduped on their link, once the filters have run.

        Args:
            page (Page): A Playwright Page instance for this task.
            sport (Optional[str]): The requested sport, required when `league` is given.
                When given, rows whose href is not under the sport's site path
                (`/<site_slug>/`) are dropped and counted.
            league (Optional[str]): League slug; keeps only the rows of the section
                whose header link is the league's path (from SPORTS_LEAGUES_URLS_MAPPING).

        Returns:
            List[dict]: One dict per live match: {"match_link": str}.

        Raises:
            Exception: Whatever reading or parsing the page raised, so the run
                fails instead of reporting nothing in play.
        """
        try:
            league_path_prefix = None
            if league and sport:
                league_url = URLBuilder.get_league_url(sport, league)
                league_path_prefix = urlsplit(league_url).path.rstrip("/")

            # In-play hrefs are H2H URLs carrying no league segment, so the league
            # of a row is the section-header link that precedes it (gotchas §20).
            elements = await _listing_elements(
                page,
                lambda el: el.name == "a"
                and el.has_attr("href")
                and ((OddsPortalSelectors.is_match_link(el) and "/inplay-odds/" in el["href"]) or _is_league_link(el)),
            )

            rows = _ListingRows(sport, self.base_url or ODDSPORTAL_BASE_URL)
            results: list[dict[str, Any]] = []
            league_filtered_out = 0
            current_league: str | None = None

            for row in elements:
                if not OddsPortalSelectors.is_match_link(row):
                    current_league = row["href"]
                    continue

                href = rows.href(row)
                if href is None:
                    continue

                if league_path_prefix and (current_league or "").rstrip("/") != league_path_prefix:
                    league_filtered_out += 1
                    continue

                link = rows.link(href)
                if link is not None:
                    results.append({"match_link": link})

            league_suffix = f", {league_filtered_out} rows outside league '{league}'" if league_path_prefix else ""
            self.logger.info(f"Extracted {len(results)} live match links ({rows.counts()}{league_suffix}).")
            rows.warn_if_all_foreign(self.logger, "live listing")
            rows.warn_if_all_hidden(self.logger, "live listing", page.url)
            return results

        except Exception as e:
            self.logger.error(f"Error extracting live match links: {e}", exc_info=True)
            raise

    async def _warm_up_page(
        self, page: Page, home_timeout_ms: int | None = None, strict_on_canonical_host: bool = False
    ) -> None:
        """Accept the cookie banner, then set decimal odds through `self.set_odds_format` (`warm_up.warm_up_page`)."""
        await warm_up.warm_up_page(
            page, self.cookie_dismisser, self.set_odds_format, self.base_url, home_timeout_ms, strict_on_canonical_host
        )

    async def _warm_proxy_contexts(self):
        """Warm each non-default proxy context once.

        Odds format and cookie consent are per-context state. Without this, match
        pages loaded on a fresh proxy context would render with the wrong odds
        format, silently corrupting odds values, so a context whose odds format
        cannot be set in PROXY_WARM_UP_ATTEMPTS tries leaves the rotation.
        """
        for key in self.playwright_manager.non_default_context_keys():
            if key in self._warmed_proxy_keys:
                continue
            self._warmed_proxy_keys.add(key)
            for attempt in range(1, PROXY_WARM_UP_ATTEMPTS + 1):
                page = None
                try:
                    page = await self.playwright_manager.new_page_on_key(key)
                    await self._warm_up_page(page, home_timeout_ms=NAVIGATION_TIMEOUT_MS, strict_on_canonical_host=True)
                    self.logger.info(f"Warmed proxy context: {key}")
                    break
                except Exception as e:
                    if attempt < PROXY_WARM_UP_ATTEMPTS:
                        self.logger.warning(f"Failed to warm proxy context {key}: {e}. Retrying.")
                    else:
                        self.logger.warning(
                            f"Failed to warm proxy context {key} after {attempt} attempts: {e}. "
                            "Removing proxy from rotation."
                        )
                        self.playwright_manager.blacklist_proxy(key)
                finally:
                    if page:
                        try:
                            await page.close()
                        except Exception as e:
                            self.logger.warning(f"Could not close the warm-up page of proxy context {key}: {e}")

    async def extract_match_odds(
        self,
        sport: str,
        match_links: list[str],
        markets: list[str] | None = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        concurrent_scraping_task: int = 3,
        preview_submarkets_only: bool = False,
        bookies_filter: BookiesFilter = BookiesFilter.ALL,
        period: Enum | None = None,
        retry_config: RetryConfig | None = None,
        request_delay: float = DEFAULT_REQUEST_DELAY_S,
        live_mode: bool = False,
    ) -> ScrapeResult:
        """
        Extract odds for a list of match links concurrently.

        Args:
            sport (str): The sport to scrape odds for.
            match_links (List[str]): A list of match links to scrape odds for.
            markets (Optional[List[str]]: The list of markets to scrape.
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.
            concurrent_scraping_task (int): Controls how many pages are processed simultaneously.
            preview_submarkets_only (bool): If True, only scrape the collapsed submarket odds (best/highest shown
            per line, not per-bookmaker) from visible submarkets without loading individual bookmaker details.
            bookies_filter (BookiesFilter): The bookmaker filter to apply.
            period: The period to scrape odds for.
            retry_config: Configuration for per-match retry behavior.

        Returns:
            ScrapeResult: Contains successful results, failed URLs with error details, and statistics.
        """
        await self._warm_proxy_contexts()

        self.logger.info(f"Starting to scrape odds for {len(match_links)} match links...")

        result = ScrapeResult(stats=ScrapeStats(total_urls=len(match_links)))
        semaphore = asyncio.Semaphore(concurrent_scraping_task)

        if retry_config is None:
            retry_config = RetryConfig(
                max_attempts=MATCH_RETRY_MAX_ATTEMPTS,
                base_delay=MATCH_RETRY_BASE_DELAY,
                max_delay=MATCH_RETRY_MAX_DELAY,
            )

        async def scrape_single_match(page: Page, link: str) -> dict[str, Any] | None:
            """Inner function to scrape a single match (used for retry)."""
            return await self._scrape_match_data(
                page=page,
                sport=sport,
                match_link=link,
                markets=markets,
                scrape_odds_history=scrape_odds_history,
                target_bookmaker=target_bookmaker,
                preview_submarkets_only=preview_submarkets_only,
                bookies_filter=bookies_filter,
                period=period,
                live_mode=live_mode,
            )

        pacer = RequestPacer(request_delay)

        async def scrape_with_semaphore(link: str) -> tuple[str, dict[str, Any] | None, FailedUrl | None]:
            async with semaphore:
                await pacer.wait()

                tab = None
                proxy_key = None

                try:
                    tab, proxy_key = await self.playwright_manager.new_rotated_page()

                    # Use retry with backoff for each match
                    retry_result = await retry_with_backoff(
                        scrape_single_match,
                        tab,
                        link,
                        config=retry_config,
                    )

                    if live_mode and retry_result.success and retry_result.result is None:
                        # The live match ended between listing and visit: neither scraped nor failed.
                        self.playwright_manager.report_page_result(proxy_key, is_proxy_failure=False)
                        return (link, None, None)

                    if retry_result.success and retry_result.result is not None:
                        self.logger.info(f"Successfully scraped match link: {link} (attempts: {retry_result.attempts})")
                        self.playwright_manager.report_page_result(proxy_key, is_proxy_failure=False)
                        self._emit_match(retry_result.result)
                        return (link, retry_result.result, None)
                    else:
                        # Scraping failed after retries
                        error_type = retry_result.error_type or classify_error(retry_result.last_error)
                        failed_url = FailedUrl(
                            url=link,
                            error_type=error_type,
                            error_message=retry_result.last_error or "Unknown error",
                            attempts=retry_result.attempts,
                            is_retryable=retry_result.is_retryable,
                        )
                        self.logger.warning(
                            f"Failed to scrape {link} after {retry_result.attempts} attempts: {retry_result.last_error}"
                        )
                        self.playwright_manager.report_page_result(
                            proxy_key, is_proxy_failure=is_proxy_attributable_error(error_type)
                        )
                        return (link, None, failed_url)

                except Exception as e:
                    # Unexpected error outside of retry mechanism
                    error_message = str(e)
                    failed_url = FailedUrl(
                        url=link,
                        error_type=classify_error(error_message),
                        error_message=error_message,
                        attempts=1,
                        is_retryable=is_retryable_error(error_message),
                    )
                    self.logger.error(f"Unexpected error scraping {link}: {e}")
                    if proxy_key is not None:
                        self.playwright_manager.report_page_result(
                            proxy_key,
                            is_proxy_failure=is_proxy_attributable_error(classify_error(error_message)),
                        )
                    return (link, None, failed_url)

                finally:
                    if tab:
                        try:
                            await tab.close()
                        except Exception as e:
                            self.logger.warning(f"Could not close the tab used for {link}: {e}")

        # Execute all scraping tasks concurrently
        tasks = [scrape_with_semaphore(link) for link in match_links]
        results = await asyncio.gather(*tasks)

        # Process results
        ended = 0
        for _link, data, failed_url in results:
            if data is not None:
                result.success.append(data)
                result.stats.successful += 1
            elif failed_url is not None:
                result.failed.append(failed_url)
                result.stats.failed += 1
            else:
                ended += 1

        if ended:
            result.stats.total_urls -= ended
            self.logger.info(f"{ended} matches ended between listing and scrape; dropped from output.")

        # Log summary
        self.logger.info(
            f"Scraping complete: {result.stats.successful}/{result.stats.total_urls} successful "
            f"({result.stats.success_rate:.1f}%)"
        )

        if result.failed:
            retryable_count = len(result.get_retryable_urls())
            self.logger.warning(
                f"Failed to scrape {result.stats.failed} URLs "
                f"({retryable_count} retryable, {result.stats.failed - retryable_count} permanent)"
            )
            # Log error breakdown
            error_breakdown = result.get_error_breakdown()
            for error_type, urls in error_breakdown.items():
                self.logger.debug(f"  {error_type}: {len(urls)} URLs")

        return result

    def _emit_match(self, record: dict[str, Any]) -> None:
        """Hand a freshly scraped match to the stream consumer, if any."""
        if self.on_match is None:
            return

        try:
            self.on_match(record)

        except Exception as e:
            # A consumer-side failure must not demote a successfully scraped match.
            self.logger.warning(f"Match stream consumer raised, dropping this record from the stream: {e}")

    async def _scrape_match_data(
        self,
        page: Page,
        sport: str,
        match_link: str,
        markets: list[str] | None = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        preview_submarkets_only: bool = False,
        bookies_filter: BookiesFilter = BookiesFilter.ALL,
        period: Enum | None = None,
        live_mode: bool = False,
    ) -> dict[str, Any] | None:
        """Scrape one match, raising RateLimitError when OddsPortal answered 429 during the visit."""
        # A 429 on a request of the page (feed, script, tab switch) leaves the view or a market empty
        # while the document itself loads; only the response stream shows it (gotchas §23).
        domain = (urlsplit(match_link).hostname or "").removeprefix("www.")
        refused: list[tuple[str, str]] = []

        def on_response(response) -> None:
            host = urlsplit(response.url).hostname or ""
            if response.status == 429 and (host == domain or host.endswith("." + domain)):
                refused.append((response.request.resource_type, response.url))

        page.on("response", on_response)
        try:
            result = await self._scrape_match_data_unguarded(
                page=page,
                sport=sport,
                match_link=match_link,
                markets=markets,
                scrape_odds_history=scrape_odds_history,
                target_bookmaker=target_bookmaker,
                preview_submarkets_only=preview_submarkets_only,
                bookies_filter=bookies_filter,
                period=period,
                live_mode=live_mode,
            )
        except (H2HFragmentResolutionError, MatchContentError) as e:
            if refused:
                raise self._rate_limit_error(match_link, [url for _, url in refused]) from e
            raise
        finally:
            page.remove_listener("response", on_response)
        # A refused image or chunk on a view that rendered costs nothing; a refused data request may.
        lost_data = [url for kind, url in refused if kind in ("document", "xhr", "fetch")]
        if lost_data:
            raise self._rate_limit_error(match_link, lost_data)
        return result

    @staticmethod
    def _rate_limit_error(match_link: str, throttled: list[str]) -> RateLimitError:
        return RateLimitError(
            f"rate limited by OddsPortal: HTTP 429 on {len(throttled)} request(s), first {throttled[0]}",
            url=match_link,
            retry_after=RATE_LIMIT_RETRY_DELAY_S,
        )

    async def _scrape_match_data_unguarded(
        self,
        page: Page,
        sport: str,
        match_link: str,
        markets: list[str] | None = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        preview_submarkets_only: bool = False,
        bookies_filter: BookiesFilter = BookiesFilter.ALL,
        period: Enum | None = None,
        live_mode: bool = False,
    ) -> dict[str, Any] | None:
        """
        Scrape data for a specific match based on the desired markets.

        Args:
            page (Page): A Playwright Page instance for this task.
            sport (str): The sport to scrape odds for.
            match_link (str): The link to the match page.
            markets (Optional[List[str]]): A list of markets to scrape (e.g., ['1x2', 'over_under_2_5']).
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.
            preview_submarkets_only (bool): If True, only scrape the collapsed submarket odds (best/highest shown
            per line, not per-bookmaker) from visible submarkets without loading individual bookmaker details.
            bookies_filter (BookiesFilter): The bookmaker filter to apply.
            period: The period enum to scrape odds for (FootballPeriod, TennisPeriod, or BasketballPeriod).

        Returns:
            Dict[str, Any] | None: A dictionary containing scraped data, or None in live mode when the match
            has ended.

        Raises:
            MatchContentError: The page loaded but its match details or content could not be read.
        """
        self.logger.info(f"Scraping match: {match_link}")

        # A page loaded on a URL that already names a market fetches that market's default data instead
        # (gotchas §27): load the event, then reach the market through the checked switch_view.
        event_url = OddsPortalSelectors.event_url(match_link)

        # Navigation is the proxy-sensitive step: let its failures propagate so
        # retry/backoff and multi-proxy failover can attribute them to the proxy.
        # Errors after a successful load are content/DOM issues: they become a
        # MatchContentError, retried but typed so that no proxy is blamed.
        if urldefrag(page.url).url == urldefrag(event_url).url:
            # Same document: goto would only change the fragment, so a retry would reuse the broken view.
            await page.goto("about:blank")
        await page.goto(event_url, timeout=NAVIGATION_TIMEOUT_MS, wait_until="domcontentloaded")

        try:
            await wait_for_signal(
                page,
                self._VIEW_OR_LOGIN_MODAL_JS,
                DYNAMIC_CONTENT_WAIT_MS,
                "match view or login modal",
                arg={
                    "tabs": OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR,
                    "modal": OddsPortalSelectors.LOGIN_MODAL_CLOSE,
                },
            )
            await self._dismiss_login_modal(page)
            await self._hydrate_match_view(page, match_link, sport=sport)

            # Apply bookmaker filter before extracting odds
            await self.selection_manager.ensure_selected(
                page=page,
                target_value=bookies_filter.value,
                display_label=BookiesFilter.get_display_label(bookies_filter),
                strategy=BOOKIES_FILTER_STRATEGY,
            )

            match_details = await self._extract_match_details(page, match_link)

            if not match_details:
                raise MatchContentError(
                    "No match details found - page may be unavailable or structure changed",
                    url=match_link,
                    error_type=ErrorType.HEADER_NOT_FOUND,
                )

            if live_mode:
                live_info = _parse_live_info(BeautifulSoup(await page.content(), "lxml"))
                if live_info is None:
                    # The match ended (or lost live coverage) between listing and visit: not a scraping failure.
                    self.logger.info(
                        f"{match_link} is no longer live: its header shows no live block, or one in a final state; "
                        "skipping."
                    )
                    return None
                match_details.update(live_info)
                match_details["scraped_at_utc"] = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

            if markets:
                self.logger.info(f"Scraping markets: {markets}")
                tz_name = getattr(self.playwright_manager, "timezone_id", None)
                history_reference = _history_reference(match_details.get("match_date"), tz_name)
                if scrape_odds_history and history_reference is None:
                    self.logger.warning(
                        f"No kickoff read on {match_link}: its odds-history timestamps take the current year."
                    )
                try:
                    # Convert period enum to internal value for market extractor
                    # If period is None, get_internal_value will return None and market extractor will use default
                    period_internal = period.get_internal_value(period) if period else None
                    market_data = await self.market_extractor.scrape_markets(
                        page=page,
                        sport=sport,
                        markets=markets,
                        period=period_internal,
                        scrape_odds_history=scrape_odds_history,
                        target_bookmaker=target_bookmaker,
                        preview_submarkets_only=preview_submarkets_only,
                        history_reference=history_reference,
                        history_timezone=tz_name,
                        bookies_filter=bookies_filter,
                    )
                    if market_data:
                        match_details.update(market_data)
                    else:
                        self.logger.warning(f"No market data found for {match_link}")
                except MarketDataError:
                    raise
                except Exception as market_error:
                    self.logger.error(f"Error scraping markets for {match_link}: {market_error}")
                    # Continue without market data rather than failing completely

            return match_details

        except (H2HFragmentResolutionError, MatchContentError):
            raise
        except Exception as e:
            raise MatchContentError(f"{type(e).__name__}: {e}", url=match_link) from e

    async def _dismiss_login_modal(self, page: Page) -> None:
        """Close the login modal that can block match-page rendering on cold profiles."""
        await dismiss_login_modal(page)

    # The tabs of the rendered match view, or the visible close button of the login modal.
    _VIEW_OR_LOGIN_MODAL_JS = """
    (args) => {
        if (document.querySelector(args.tabs)) return true;
        const close = document.querySelector(args.modal);
        return !!close && close.getClientRects().length > 0;
    }
    """

    async def _hydrate_match_view(self, page: Page, match_link: str, sport: str | None = None) -> None:
        """Wait for the match view to render, nudging the hash if it does not (`hydrate_match_view`)."""
        await hydrate_match_view(page, match_link, sport)

    async def _extract_match_details(self, page: Page, match_link: str) -> dict[str, Any] | None:
        """Read the hydrated match page and parse its details (`_parse_match_details`); None if unreadable."""
        try:
            return _parse_match_details(
                await page.content(),
                match_link,
                getattr(self.playwright_manager, "timezone_id", None),
                getattr(self.playwright_manager, "month_name_to_num", {}),
                self.local_kickoff,
                self.logger,
            )
        except Exception as e:
            self.logger.error(f"Error extracting match details from the DOM: {e}")
            return None
