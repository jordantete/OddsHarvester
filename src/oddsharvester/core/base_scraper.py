import asyncio
from datetime import UTC, date, datetime, timedelta
from enum import Enum
import json
import logging
import random
import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.browser.selection import (
    BOOKIES_FILTER_STRATEGY,
    SelectionManager,
)
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import (
    RetryConfig,
    classify_error,
    is_proxy_attributable_error,
    is_retryable_error,
    retry_with_backoff,
)
from oddsharvester.core.scrape_result import FailedUrl, ScrapeResult, ScrapeStats
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.constants import (
    DEFAULT_REQUEST_DELAY_S,
    DYNAMIC_CONTENT_WAIT_MS,
    H2H_FRAGMENT_RESOLVE_TIMEOUT_MS,
    MATCH_RETRY_BASE_DELAY,
    MATCH_RETRY_MAX_ATTEMPTS,
    MATCH_RETRY_MAX_DELAY,
    NAVIGATION_TIMEOUT_MS,
    ODDS_FORMAT_SELECTOR_TIMEOUT_MS,
    ODDS_FORMAT_WAIT_MS,
    ODDSPORTAL_BASE_URL,
    REQUEST_DELAY_JITTER_FACTOR,
    SELECTOR_TIMEOUT_MS,
)
from oddsharvester.utils.odds_format_enum import OddsFormat
from oddsharvester.utils.utils import clean_html_text

_MONTH_ABBREV_TO_NUM = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _parse_date_header(header_text: str, tz_name: str | None = None) -> date | None:
    """
    Parse an OddsPortal date-header string into a date object.

    Handles the formats observed on oddsportal.com listing pages:
        - "Today, 14 Apr"          -> today in the reference timezone
        - "Tomorrow, 15 Apr"       -> tomorrow in the reference timezone
        - "Yesterday, 13 Apr"      -> yesterday in the reference timezone
        - "18 Apr 2026"            -> explicit date
        - "Today, 14 Apr  - Apertura" -> tournament suffix is stripped

    When "Today"/"Tomorrow" is present it is trusted over the day/month tokens,
    since OddsPortal resolves them based on the browser timezone.

    Args:
        header_text: Raw inner text of the [data-testid='date-header'] element.
        tz_name: IANA timezone name used to resolve "Today"/"Tomorrow" and to
            infer missing years. Defaults to UTC.

    Returns:
        A date object, or None if the input cannot be parsed (fail-safe: callers
        should treat None as "do not filter").
    """
    if not header_text:
        return None

    text = header_text.strip()
    if " - " in text:
        text = text.split(" - ", 1)[0].strip()

    try:
        tz = ZoneInfo(tz_name) if tz_name else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")

    now_date = datetime.now(tz).date()

    lower = text.lower()
    if lower.startswith("today"):
        return now_date
    if lower.startswith("tomorrow"):
        return now_date + timedelta(days=1)
    if lower.startswith("yesterday"):
        return now_date - timedelta(days=1)

    parts = text.split()

    if len(parts) == 3:
        day_str, month_str, year_str = parts
        try:
            day = int(day_str)
            month = _MONTH_ABBREV_TO_NUM.get(month_str[:3].lower())
            year = int(year_str)
            if month is None:
                return None
            return date(year, month, day)
        except (ValueError, TypeError):
            return None

    if len(parts) == 2:
        day_str, month_str = parts
        try:
            day = int(day_str)
            month = _MONTH_ABBREV_TO_NUM.get(month_str[:3].lower())
            if month is None:
                return None
            candidate = date(now_date.year, month, day)
            if (now_date - candidate).days > 180:
                candidate = date(now_date.year + 1, month, day)
            return candidate
        except (ValueError, TypeError):
            return None

    return None


_OFFSCREEN_STYLE_MARKERS = (
    "left:-9999px",
    "top:-9999px",
    "display:none",
    "visibility:hidden",
)


def _is_offscreen_row(row) -> bool:
    """OddsPortal sometimes ships duplicate event rows in the DOM: a real
    visible one and a CSS-hidden twin whose href points to a corrupted slug
    that 301-redirects to an unrelated match. Skip the hidden twin."""
    style = (row.get("style") or "").lower().replace(" ", "")
    return any(marker in style for marker in _OFFSCREEN_STYLE_MARKERS)


_KICKOFF_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def _row_has_started(row) -> bool:
    """Return True if a listing-page event row is live or finished.

    Two signals are needed because OddsPortal splits "started" state:
    live flips `time-item` from HH:MM to a period marker; finished fills
    `game-status-box`. See `docs/agentic-gotchas.md` §9. Fail-safe:
    missing markers → False so DOM drift degrades open.
    """
    box = row.find(attrs={"data-testid": OddsPortalSelectors.EVENT_ROW_GAME_STATUS_BOX_TESTID})
    if box and box.get_text(strip=True):
        return True

    time_el = row.find(attrs={"data-testid": OddsPortalSelectors.EVENT_ROW_TIME_ITEM_TESTID})
    if time_el is None:
        return False
    p = time_el.find("p")
    text = p.get_text(strip=True) if p else time_el.get_text(strip=True)
    if not text:
        return False
    return not _KICKOFF_TIME_RE.match(text)


def _extract_fragment_match_id(match_link: str) -> str | None:
    """
    Extract the URL fragment as a match id from a match link.

    OddsPortal H2H pages encode the requested historic match via the URL
    fragment, e.g. `.../h2h/<home>/<away>/#<match_id>`. Returns the fragment
    string if it looks like a match id (non-empty, no slash). Returns None
    when no fragment is present, the fragment is empty, or it contains a
    slash (which would indicate it isn't a bare match id).
    """
    if "#" not in match_link:
        return None
    fragment = match_link.split("#", 1)[1].strip()
    if not fragment or "/" in fragment:
        return None
    return fragment


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
        base_url: str | None = None,
    ):
        """
        Args:
            playwright_manager (PlaywrightManager): Handles Playwright lifecycle.
            market_extractor (OddsPortalMarketExtractor): Handles market scraping.
            scroller (PageScroller): Handles incremental page scrolling.
            cookie_dismisser (CookieDismisser): Handles cookie banner dismissal.
            selection_manager (SelectionManager): Manages bookies filter and period selection.
            preview_submarkets_only (bool): If True, only scrape average odds from visible submarkets without loading
            individual bookmaker details.
            base_url (str | None): Regional OddsPortal domain override (scheme+host). When None, the canonical
            https://www.oddsportal.com is used.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.playwright_manager = playwright_manager
        self.market_extractor = market_extractor
        self.scroller = scroller
        self.cookie_dismisser = cookie_dismisser
        self.selection_manager = selection_manager
        self.preview_submarkets_only = preview_submarkets_only
        self.base_url = base_url
        self._warmed_proxy_keys: set[str] = set()

    async def set_odds_format(self, page: Page, odds_format: OddsFormat = OddsFormat.DECIMAL_ODDS):
        """
        Sets the odds format on the page.

        Args:
            page (Page): The Playwright page instance.
            odds_format (OddsFormat): The desired odds format.
        """
        try:
            self.logger.info(f"Setting odds format: {odds_format.value}")
            # Text-based selector: OddsPortal's React build periodically reshuffles
            # Tailwind utility classes on this control (issue #68: the old
            # `div.group > button.gap-2` stopped matching when it became
            # `button.flex gap-3`). The button label is always the current odds
            # format ("Decimal Odds", "Fractional Odds", ...), so matching on the
            # "Odds" text survives class refactors. Verified live 2026-05-15.
            button_selector = "button:has-text('Odds')"
            await page.wait_for_selector(button_selector, state="attached", timeout=ODDS_FORMAT_SELECTOR_TIMEOUT_MS)
            dropdown_button = await page.query_selector(button_selector)

            # Check if the desired format is already selected
            current_format = await dropdown_button.inner_text()
            self.logger.info(f"Current odds format detected: {current_format}")

            if current_format == odds_format.value:
                self.logger.info(f"Odds format is already set to '{odds_format.value}'. Skipping.")
                return

            await dropdown_button.click()
            await page.wait_for_timeout(ODDS_FORMAT_WAIT_MS)
            format_option_selector = "div.group > div.dropdown-content > ul > li > a"
            format_options = await page.query_selector_all(format_option_selector)

            for option in format_options:
                option_text = await option.inner_text()

                if odds_format.value.lower() in option_text.lower():
                    self.logger.info(f"Selecting odds format: {option_text}")
                    await option.click()
                    await page.wait_for_timeout(ODDS_FORMAT_WAIT_MS)
                    self.logger.info(f"Odds format changed to '{odds_format.value}'.")
                    return

            self.logger.warning(f"Desired odds format '{odds_format.value}' not found in dropdown options.")

        except TimeoutError:
            self.logger.error("Timeout while setting odds format. Dropdown may not have loaded.")

        except Exception as e:
            self.logger.error(f"Error while setting odds format: {e}", exc_info=True)

    async def extract_match_links(
        self,
        page: Page,
        date_filter: date | None = None,
        skip_started: bool = False,
    ) -> list[str]:
        """
        Extract and parse match links from the current page.

        Event rows on OddsPortal listing pages are grouped by date: the first
        row of a group carries a `[data-testid='date-header']` element, and
        subsequent rows in the same group inherit that date. When `date_filter`
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

        Returns:
            List[str]: A list of unique match links found on the page.
        """
        try:
            html_content = await page.content()
            soup = BeautifulSoup(html_content, "lxml")
            event_rows = soup.find_all(class_=re.compile(OddsPortalSelectors.EVENT_ROW_CLASS_PATTERN))
            self.logger.info(f"Found {len(event_rows)} event rows.")

            tz_name = getattr(self.playwright_manager, "timezone_id", None) if date_filter else None

            seen: set[str] = set()
            match_links: list[str] = []
            current_row_date: date | None = None
            seen_header_dates: set[date] = set()
            filtered_out_count = 0
            unparseable_header_count = 0
            offscreen_skipped_count = 0
            started_filtered_out_count = 0

            for row in event_rows:
                if _is_offscreen_row(row):
                    offscreen_skipped_count += 1
                    continue

                if date_filter is not None:
                    header_el = row.find(attrs={"data-testid": "date-header"})
                    if header_el is not None:
                        header_text = header_el.get_text(" ", strip=True)
                        parsed = _parse_date_header(header_text, tz_name=tz_name)
                        if parsed is None:
                            unparseable_header_count += 1
                            self.logger.warning(
                                f"Could not parse date-header '{header_text}'; rows under it will not be filtered."
                            )
                        else:
                            seen_header_dates.add(parsed)
                        current_row_date = parsed

                    if current_row_date is not None and current_row_date != date_filter:
                        filtered_out_count += 1
                        continue

                if skip_started and _row_has_started(row):
                    started_filtered_out_count += 1
                    continue

                for link in row.find_all("a", href=True):
                    href = link["href"]
                    if len(href.strip("/").split("/")) <= 3:
                        continue
                    full_url = f"{self.base_url or ODDSPORTAL_BASE_URL}{href}"
                    if full_url not in seen:
                        seen.add(full_url)
                        match_links.append(full_url)

            started_suffix = f", {started_filtered_out_count} started/finished rows skipped" if skip_started else ""
            if date_filter is not None:
                self.logger.info(
                    f"Extracted {len(match_links)} unique match links after date filtering "
                    f"(filter={date_filter.isoformat()}, filtered out {filtered_out_count} rows, "
                    f"{unparseable_header_count} unparseable headers, "
                    f"{offscreen_skipped_count} offscreen rows skipped"
                    f"{started_suffix})."
                )
                if not match_links and filtered_out_count:
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
                    f"Extracted {len(match_links)} unique match links "
                    f"({offscreen_skipped_count} offscreen rows skipped"
                    f"{started_suffix})."
                )

            return match_links

        except Exception as e:
            self.logger.error(f"Error extracting match links: {e}", exc_info=True)
            return []

    async def _warm_proxy_contexts(self):
        """Warm each non-default proxy context once.

        Odds format and cookie consent are per-context state. Without this, match
        pages loaded on a fresh proxy context would render with the wrong odds
        format, silently corrupting odds values.
        """
        for key in self.playwright_manager.non_default_context_keys():
            if key in self._warmed_proxy_keys:
                continue
            self._warmed_proxy_keys.add(key)
            page = None
            try:
                page = await self.playwright_manager.new_page_on_key(key)
                await page.goto(ODDSPORTAL_BASE_URL, timeout=NAVIGATION_TIMEOUT_MS, wait_until="domcontentloaded")
                await self.cookie_dismisser.dismiss(page=page)
                await self.set_odds_format(page=page)
                self.logger.info(f"Warmed proxy context: {key}")
            except Exception as e:
                self.logger.warning(f"Failed to warm proxy context {key}: {e}. Removing proxy from rotation.")
                self.playwright_manager.blacklist_proxy(key)
            finally:
                if page:
                    await page.close()

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
            preview_submarkets_only (bool): If True, only scrape average odds from visible submarkets without loading
            individual bookmaker details.
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
            )

        request_counter = {"count": 0}

        async def scrape_with_semaphore(link: str) -> tuple[str, dict[str, Any] | None, FailedUrl | None]:
            async with semaphore:
                # Apply rate limiting delay (skip for the first request)
                current_count = request_counter["count"]
                request_counter["count"] += 1
                if current_count > 0 and request_delay > 0:
                    jitter = request_delay * REQUEST_DELAY_JITTER_FACTOR * random.random()  # noqa: S311
                    total_delay = request_delay + jitter
                    self.logger.debug(f"Rate limiting: waiting {total_delay:.2f}s before request")
                    await asyncio.sleep(total_delay)

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

                    if retry_result.success and retry_result.result is not None:
                        self.logger.info(f"Successfully scraped match link: {link} (attempts: {retry_result.attempts})")
                        self.playwright_manager.report_page_result(proxy_key, is_proxy_failure=False)
                        return (link, retry_result.result, None)
                    else:
                        # Scraping failed after retries
                        error_type = retry_result.error_type or classify_error(retry_result.last_error)
                        failed_url = FailedUrl(
                            url=link,
                            error_type=error_type,
                            error_message=retry_result.last_error or "Unknown error",
                            attempts=retry_result.attempts,
                            is_retryable=is_retryable_error(retry_result.last_error or ""),
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
                        await tab.close()

        # Execute all scraping tasks concurrently
        tasks = [scrape_with_semaphore(link) for link in match_links]
        results = await asyncio.gather(*tasks)

        # Process results
        for _link, data, failed_url in results:
            if data is not None:
                result.success.append(data)
                result.stats.successful += 1
            elif failed_url is not None:
                result.failed.append(failed_url)
                result.stats.failed += 1

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
            preview_submarkets_only (bool): If True, only scrape average odds from visible submarkets without loading
            individual bookmaker details.
            bookies_filter (BookiesFilter): The bookmaker filter to apply.
            period: The period enum to scrape odds for (FootballPeriod, TennisPeriod, or BasketballPeriod).

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing scraped data, or None if scraping fails.
        """
        self.logger.info(f"Scraping match: {match_link}")

        # Navigation is the proxy-sensitive step: let its failures propagate so
        # retry/backoff and multi-proxy failover can attribute them to the proxy.
        # Errors after a successful load are content/DOM issues and must not
        # blacklist a proxy, so they stay swallowed to None below.
        await page.goto(match_link, timeout=NAVIGATION_TIMEOUT_MS, wait_until="domcontentloaded")

        try:
            # Wait a bit for dynamic content to load
            await page.wait_for_timeout(DYNAMIC_CONTENT_WAIT_MS)

            # Apply bookmaker filter before extracting odds
            await self.selection_manager.ensure_selected(
                page=page,
                target_value=bookies_filter.value,
                display_label=BookiesFilter.get_display_label(bookies_filter),
                strategy=BOOKIES_FILTER_STRATEGY,
            )

            match_details = await self._extract_match_details_event_header(page, match_link)

            if not match_details:
                self.logger.warning(
                    f"No match details found for {match_link} - page may be unavailable or structure changed"
                )
                return None

            if markets:
                self.logger.info(f"Scraping markets: {markets}")
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
                    )
                    if market_data:
                        match_details.update(market_data)
                    else:
                        self.logger.warning(f"No market data found for {match_link}")
                except Exception as market_error:
                    self.logger.error(f"Error scraping markets for {match_link}: {market_error}")
                    # Continue without market data rather than failing completely

            return match_details

        except Exception as e:
            self.logger.error(f"Error scraping match data from {match_link}: {e}")
            return None

    def _resolved_browser_timezone(self) -> ZoneInfo:
        """
        Resolve the timezone the Playwright browser context is rendering in.

        Falls back to UTC when no timezone is configured or when an unknown
        timezone identifier is set. Emits a warning on fallback.
        """
        tz_id = getattr(self.playwright_manager, "timezone_id", None) or "UTC"
        try:
            return ZoneInfo(tz_id)
        except ZoneInfoNotFoundError:
            self.logger.warning(f"Unknown timezone '{tz_id}', falling back to UTC for DOM date parsing")
            return ZoneInfo("UTC")

    def _parse_match_date_from_dom(self, soup: BeautifulSoup) -> str | None:
        """
        Extract the match date from <div data-testid="game-time-item"> and
        return it formatted as "YYYY-MM-DD HH:MM:SS UTC".

        Returns None if the div or its child paragraphs are missing, or if
        the text doesn't match the expected "DD MMM YYYY" + "HH:MM" shape.
        """
        try:
            game_time_div = soup.find("div", attrs={"data-testid": OddsPortalSelectors.MATCH_DETAILS_GAME_TIME_TESTID})
            if not game_time_div:
                return None

            paragraphs = game_time_div.find_all("p")
            if len(paragraphs) < 3:
                return None

            date_part = paragraphs[1].get_text(strip=True).rstrip(",")
            time_part = paragraphs[2].get_text(strip=True)
            local_dt = datetime.strptime(f"{date_part} {time_part}", "%d %b %Y %H:%M")
            local_dt = local_dt.replace(tzinfo=self._resolved_browser_timezone())
            return local_dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S %Z")
        except Exception as e:
            self.logger.warning(f"DOM parse failed for match_date: {e}")
            return None

    def _parse_teams_from_dom(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """
        Extract (home_team, away_team) from <div data-testid="game-host">
        and <div data-testid="game-guest">. Returns (None, None) if either
        side is missing - caller falls back to JSON for both fields.
        """
        try:
            host = soup.find("div", attrs={"data-testid": OddsPortalSelectors.MATCH_DETAILS_GAME_HOST_TESTID})
            guest = soup.find("div", attrs={"data-testid": OddsPortalSelectors.MATCH_DETAILS_GAME_GUEST_TESTID})
            host_p = host.find("p") if host else None
            guest_p = guest.find("p") if guest else None
            if not host_p or not guest_p:
                return None, None
            return host_p.get_text(strip=True), guest_p.get_text(strip=True)
        except Exception as e:
            self.logger.warning(f"DOM parse failed for teams: {e}")
            return None, None

    _SEASON_SUFFIX_RE = re.compile(r"\s+\d{4}/\d{4}$")

    def _parse_league_from_dom(self, soup: BeautifulSoup) -> str | None:
        """
        Extract the league name from the breadcrumb navigation, stripping
        the trailing season suffix when present (e.g. "Premier League 2024/2025"
        -> "Premier League"). Returns None if the breadcrumb or league link is
        missing.
        """
        try:
            breadcrumbs = soup.find("div", attrs={"data-testid": OddsPortalSelectors.MATCH_DETAILS_BREADCRUMBS_TESTID})
            if not breadcrumbs:
                return None
            league_link = breadcrumbs.find(
                "a", attrs={"data-testid": OddsPortalSelectors.MATCH_DETAILS_BREADCRUMB_LEAGUE_TESTID}
            )
            if not league_link:
                return None
            raw = league_link.get_text(strip=True)
            return self._SEASON_SUFFIX_RE.sub("", raw) or None
        except Exception as e:
            self.logger.warning(f"DOM parse failed for league_name: {e}")
            return None

    _RESULT_TEXT_RE = re.compile(r"(\d+)\s*:\s*(\d+)(?:\s*\(([\d:,\s ]+)\))?")

    def _parse_results_from_dom(self, soup: BeautifulSoup) -> tuple[str | None, str | None, str | None]:
        """
        Extract (home_score, away_score, partial_results) from the page DOM.

        Scoped to descendants of <div data-testid="game-time-item">'s parent
        to avoid false positives elsewhere in the page. Returns (None, None,
        None) if the score pattern isn't found.
        """
        try:
            game_time_div = soup.find("div", attrs={"data-testid": OddsPortalSelectors.MATCH_DETAILS_GAME_TIME_TESTID})
            if not game_time_div:
                return None, None, None
            scope = game_time_div.find_parent() or soup
            excluded = {id(game_time_div), *(id(d) for d in game_time_div.find_all("div"))}
            for div in scope.find_all("div"):
                if id(div) in excluded:
                    continue
                text = div.get_text(separator=" ", strip=True)
                m = self._RESULT_TEXT_RE.search(text)
                if m:
                    home, away, partial = m.group(1), m.group(2), m.group(3)
                    formatted_partial = (
                        f"({re.sub(r' +', ' ', partial.replace(chr(0xA0), ' ')).strip()})" if partial else None
                    )
                    return home, away, formatted_partial
            return None, None, None
        except Exception as e:
            self.logger.warning(f"DOM parse failed for results: {e}")
            return None, None, None

    async def _resolve_h2h_fragment_mismatch(
        self,
        page: Page,
        fragment: str,
    ) -> tuple[BeautifulSoup, dict[str, Any]] | None:
        """
        Force the OddsPortal React SPA to swap to the fragment-targeted match
        and re-read the page payload.

        OddsPortal `/<sport>/h2h/<home>/<away>/#<id>` URLs are H2H aggregates:
        the SSR HTML always contains data for the next upcoming match between
        the two teams, regardless of the requested fragment. The JS SPA reads
        `location.hash` and refetches the correct match data. Under Playwright
        the swap is unreliable, so we explicitly clear and re-dispatch the hash
        to nudge it, then wait until `react-event-header`'s `eventData.id`
        matches the requested fragment.

        Returns the updated (soup, json_data) on success, or None if the wait
        times out (the page would not show the requested match).
        """
        trigger_js = """
        (desired) => {
            if (window.location.hash !== '#' + desired) {
                window.location.hash = '';
                window.location.hash = '#' + desired;
            }
            window.dispatchEvent(new HashChangeEvent('hashchange', { newURL: window.location.href }));
        }
        """
        predicate_js = """
        (desired) => {
            const el = document.getElementById('react-event-header');
            if (!el) return false;
            try {
                const data = JSON.parse(el.getAttribute('data'));
                return !!(data && data.eventData && data.eventData.id === desired);
            } catch (e) { return false; }
        }
        """
        try:
            await page.evaluate(trigger_js, fragment)
            await page.wait_for_function(
                predicate_js,
                arg=fragment,
                timeout=H2H_FRAGMENT_RESOLVE_TIMEOUT_MS,
            )
        except TimeoutError:
            self.logger.error(
                f"H2H fragment resolution failed after retry: requested={fragment}; "
                f"page never updated eventData.id to match the fragment"
            )
            return None
        except Exception as e:
            self.logger.error(f"H2H fragment resolution raised unexpected error for fragment={fragment}: {e}")
            return None

        html_content = await page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        header_div = soup.find("div", id="react-event-header")
        if not header_div:
            return None
        data_attribute = header_div.get("data")
        if not data_attribute:
            return None
        try:
            json_data = json.loads(data_attribute)
        except (TypeError, json.JSONDecodeError):
            return None
        return soup, json_data

    async def _extract_match_details_event_header(self, page: Page, match_link: str) -> dict[str, Any] | None:
        """
        Extract match details (date, teams, league, scores, venue) from the
        match page.

        Reads the React event header JSON for venue fields and as a per-field
        fallback. Prefers DOM values for date / teams / league / scores
        because the embedded JSON has been observed to return stale values
        for some leagues (see PR #54).

        Returns None if neither the JSON nor the DOM yield enough data to
        identify the match (i.e. the react-event-header div itself is missing).
        """
        try:
            try:
                await page.wait_for_selector("#react-event-header", timeout=SELECTOR_TIMEOUT_MS)
            except Exception:
                self.logger.warning("React event header selector not found, attempting to parse existing content")

            html_content = await page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            event_header_div = soup.find("div", id="react-event-header")

            if not event_header_div:
                self.logger.warning("React event header div not found in page content")
                return None

            data_attribute = event_header_div.get("data")
            if not data_attribute:
                self.logger.warning("React event header div found but 'data' attribute is missing")
                return None

            try:
                json_data = json.loads(data_attribute)
            except (TypeError, json.JSONDecodeError) as e:
                self.logger.error(f"Failed to parse JSON data from react event header: {e}")
                return None

            event_body = json_data.get("eventBody", {})
            event_data = json_data.get("eventData", {})

            # Detect H2H fragment vs eventData.id mismatch. OddsPortal's SSR for
            # /<sport>/h2h/<home>/<away>/#<id> carries data for a different match
            # than the fragment-targeted one. Two distinct cases must be told
            # apart, because they require opposite handling:
            #
            #   * issue #60: the SSR is the *next upcoming* matchup between the
            #     two teams and the SPA has not swapped yet, so the DOM shows
            #     that same wrong match too. We must force a resync, or drop the
            #     match rather than emit the wrong (upcoming) match_date.
            #   * PR #54: the SSR JSON is a stale *recent* match, but the SPA
            #     *did* hydrate the DOM to the requested historic match. The
            #     DOM-first dispatcher below already yields the correct values;
            #     resyncing is impossible here (the embedded JSON id never
            #     updates to the fragment) and dropping would regress PR #54.
            #
            # Discriminate deterministically by whether the DOM has resolved to
            # a match different from the stale JSON: DOM-resolved => PR #54 path
            # (trust DOM), DOM == stale JSON or absent => issue #60 path (resync
            # or drop). This avoids any wall-clock dependency.
            fragment = _extract_fragment_match_id(match_link)
            event_id = event_data.get("id")
            if fragment and event_id and fragment != event_id:
                ssr_json_date = (
                    datetime.fromtimestamp(event_body["startDate"], tz=UTC).strftime("%Y-%m-%d %H:%M:%S %Z")
                    if event_body.get("startDate")
                    else None
                )
                ssr_dom_date = self._parse_match_date_from_dom(soup)
                dom_resolved_independently = ssr_dom_date is not None and ssr_dom_date != ssr_json_date
                if dom_resolved_independently:
                    self.logger.info(
                        f"H2H fragment mismatch (requested={fragment} page={event_id}) but the DOM "
                        f"resolved to the fragment match independently; using DOM-first (PR #54 path)"
                    )
                else:
                    self.logger.warning(
                        f"H2H fragment mismatch detected: requested={fragment} "
                        f"page={event_id} url={match_link}; DOM not resolved, attempting hash-resync"
                    )
                    resolved = await self._resolve_h2h_fragment_mismatch(page=page, fragment=fragment)
                    if resolved is None:
                        return None
                    soup, json_data = resolved
                    event_body = json_data.get("eventBody", {})
                    event_data = json_data.get("eventData", {})

            json_match_date = (
                datetime.fromtimestamp(event_body["startDate"], tz=UTC).strftime("%Y-%m-%d %H:%M:%S %Z")
                if event_body.get("startDate")
                else None
            )

            # DOM extraction (each helper returns None on failure)
            dom_match_date = self._parse_match_date_from_dom(soup)
            dom_home, dom_away = self._parse_teams_from_dom(soup)
            dom_league = self._parse_league_from_dom(soup)
            dom_home_score, dom_away_score, dom_partial = self._parse_results_from_dom(soup)

            # Per-field fallback: DOM wins when present, else JSON
            match_date = dom_match_date if dom_match_date is not None else json_match_date
            home_team = dom_home if dom_home is not None else event_data.get("home")
            away_team = dom_away if dom_away is not None else event_data.get("away")
            league_name = dom_league if dom_league is not None else event_data.get("tournamentName")
            home_score_raw = dom_home_score if dom_home_score is not None else event_body.get("homeResult")
            away_score_raw = dom_away_score if dom_away_score is not None else event_body.get("awayResult")
            home_score = str(home_score_raw) if home_score_raw is not None else None
            away_score = str(away_score_raw) if away_score_raw is not None else None
            partial_results = (
                dom_partial if dom_partial is not None else clean_html_text(event_body.get("partialresult"))
            )

            # Observability: log which fields came from DOM vs. JSON fallback
            sources = {
                "match_date": "dom" if dom_match_date is not None else "json",
                "home_team": "dom" if dom_home is not None else "json",
                "away_team": "dom" if dom_away is not None else "json",
                "league_name": "dom" if dom_league is not None else "json",
                "home_score": "dom" if dom_home_score is not None else "json",
                "away_score": "dom" if dom_away_score is not None else "json",
                "partial_results": "dom" if dom_partial is not None else "json",
            }
            dom_fields = sorted(k for k, v in sources.items() if v == "dom")
            json_fields = sorted(k for k, v in sources.items() if v == "json")
            self.logger.info(f"match_details extracted dom={dom_fields} json_fallback={json_fields}")

            return {
                "scraped_date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S %Z"),
                "match_date": match_date,
                "match_link": match_link,
                "home_team": home_team,
                "away_team": away_team,
                "league_name": league_name,
                "home_score": home_score,
                "away_score": away_score,
                "partial_results": partial_results,
                "venue": event_body.get("venue").encode("ascii", "ignore").decode("ascii")
                if event_body.get("venue")
                else None,
                "venue_town": event_body.get("venueTown").encode("ascii", "ignore").decode("ascii")
                if event_body.get("venueTown")
                else None,
                "venue_country": event_body.get("venueCountry"),
            }

        except Exception as e:
            self.logger.error(f"Error extracting match details while parsing React event header: {e}")
            return None
