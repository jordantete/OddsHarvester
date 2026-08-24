import asyncio
from datetime import UTC, date, datetime, time, timedelta
from enum import Enum
import json
import logging
import random
import re
from typing import Any, ClassVar
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.pagination import PaginationWalker
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.browser.selection import (
    BOOKIES_FILTER_STRATEGY,
    SelectionManager,
)
from oddsharvester.core.exceptions import H2HFragmentResolutionError
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
from oddsharvester.core.url_builder import URLBuilder
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.constants import (
    DEFAULT_REQUEST_DELAY_S,
    DYNAMIC_CONTENT_WAIT_MS,
    HASH_NUDGE_DELAY_MS,
    MATCH_HYDRATION_ATTEMPTS,
    MATCH_HYDRATION_TIMEOUT_MS,
    MATCH_RETRY_BASE_DELAY,
    MATCH_RETRY_MAX_ATTEMPTS,
    MATCH_RETRY_MAX_DELAY,
    NAVIGATION_TIMEOUT_MS,
    ODDS_FORMAT_SELECTOR_TIMEOUT_MS,
    ODDS_FORMAT_WAIT_MS,
    ODDSPORTAL_BASE_URL,
    REQUEST_DELAY_JITTER_FACTOR,
)
from oddsharvester.utils.datetime_format import format_utc
from oddsharvester.utils.local_kickoff import compute_local_kickoff
from oddsharvester.utils.odds_format_enum import OddsFormat

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
        tz = ZoneInfo(tz_name) if tz_name else UTC
    except (ZoneInfoNotFoundError, ValueError):
        tz = UTC

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


def _row_kickoff_datetime(row, row_date: date | None, tz) -> datetime | None:
    """Best-effort kickoff datetime for a listing-page event row.

    Combines the group's `row_date` (from the surrounding date-header) with the
    HH:MM shown in the row's `time-item`. Returns None when the kickoff cannot
    be determined (no date, no time-item, or a non-clock value such as a live
    period marker), so callers keep the row (fail-safe against DOM drift).

    Args:
        row: A BeautifulSoup event-row node.
        row_date: The date of the row's group, or None if unknown.
        tz: tzinfo used to build the aware datetime; must match the timezone the
            listing times are rendered in (see `docs/agentic-gotchas.md` §10).
    """
    if row_date is None:
        return None
    time_el = row.find(attrs={"data-testid": OddsPortalSelectors.EVENT_ROW_TIME_ITEM_TESTID})
    if time_el is None:
        return None
    p = time_el.find("p")
    text = p.get_text(strip=True) if p else time_el.get_text(strip=True)
    if not text or not _KICKOFF_TIME_RE.match(text):
        return None
    hour_str, minute_str = text.split(":")
    try:
        kickoff_time = time(int(hour_str), int(minute_str))
    except ValueError:
        return None
    return datetime.combine(row_date, kickoff_time, tzinfo=tz)


# Separator is a colon on the live header, but OddsPortal renders scores with an
# en-dash (U+2013) elsewhere; accept both rather than silently dropping the score.
_LIVE_MAIN_SCORE_RE = re.compile(r"^(\d+)\s*[:\u2013-]\s*(\d+)$")


# A finished match keeps its live-info container and swaps the period marker for a
# terminal state, so an absent container is not the only end-of-match signal.
# "Final result" verified live 2026-07-20; the rest mirror the listing-page states
# in docs/agentic-gotchas.md §9.
_LIVE_ENDED_PERIOD_MARKERS = frozenset(
    {
        "final result",
        "finished",
        "postponed",
        "canceled",
        "cancelled",
        "abandoned",
        "retired",
        "walkover",
    }
)


def _parse_inplay_live_score(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Live score from the redesigned in-play match header.

    In-play pages render no `live-info` element; the running score is the red
    digits flanking the participant names inside `game-participants` (verified
    live 2026-08-24). The page shows no period/clock, so `live_period` is None
    (site regression). Returns None when no red digits are present (not live).
    """
    participants = soup.find(attrs={"data-testid": "game-participants"})
    if participants is None:
        return None
    digits = [
        el.get_text(strip=True)
        for el in participants.find_all(class_=re.compile(r"text-red"))
        if el.get_text(strip=True).isdigit()
    ]
    if len(digits) < 2:
        return None
    home, away = int(digits[0]), int(digits[1])
    return {
        "live_period": None,
        "live_score_home": home,
        "live_score_away": away,
        "live_score_raw": f"{home}:{away}",
    }


def _parse_live_info(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Parse the in-play match header into live context fields.

    Structure (verified 2026-07-20): a `live-info` container holding a period
    chunk, a main-score chunk, and an optional `partial-result` element with
    the compound detail in parentheses. Match on text shape, not classes.

    Returns None when the match is not live, which covers two cases: the
    container is absent, or it carries a terminal marker such as "Final result".
    """
    container = soup.find(attrs={"data-testid": OddsPortalSelectors.LIVE_INFO_TESTID})
    if container is None:
        return _parse_inplay_live_score(soup)

    partial_text = None
    partial_el = container.find(attrs={"data-testid": OddsPortalSelectors.LIVE_PARTIAL_RESULT_TESTID})
    if partial_el is not None:
        partial_text = partial_el.get_text("", strip=True).strip("()") or None
        partial_el.extract()

    period = None
    score_raw = None
    score_home = None
    score_away = None
    for raw_chunk in container.stripped_strings:
        # OddsPortal separates words with non-breaking spaces in these chunks.
        chunk = raw_chunk.replace("\u00a0", " ").strip()
        match = _LIVE_MAIN_SCORE_RE.match(chunk)
        if match and score_raw is None:
            score_raw = chunk
            score_home, score_away = int(match.group(1)), int(match.group(2))
        elif period is None and not match:
            period = chunk

    # Prefix match: the redesigned page can serve the terminal text as a single
    # chunk ("Final result 1:2 (0:1, 1:1)"), not a standalone marker element.
    if period and any(period.casefold().startswith(marker) for marker in _LIVE_ENDED_PERIOD_MARKERS):
        return None

    live_score_raw = score_raw
    if score_raw and partial_text:
        live_score_raw = f"{score_raw} ({partial_text})"

    return {
        "live_period": period,
        "live_score_home": score_home,
        "live_score_away": score_away,
        "live_score_raw": live_score_raw,
    }


def _extract_fragment_match_id(match_link: str) -> str | None:
    """
    Extract the URL fragment as a match id from a match link.

    OddsPortal H2H pages encode the requested historic match via the URL
    fragment, e.g. `.../h2h/<home>/<away>/#<match_id>`. Returns the fragment
    string if it looks like a match id (non-empty, no slash). Returns None
    when no fragment is present, the fragment is empty, or it contains a
    slash (which would indicate it isn't a bare match id).
    """
    return OddsPortalSelectors.event_id_from_url(match_link)


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
        self._warmed_proxy_keys: set[str] = set()
        self.pagination_walker = PaginationWalker()

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

    async def extract_match_rows(
        self,
        page: Page,
        date_filter: date | None = None,
        skip_started: bool = False,
        kickoff_within_hours: float | None = None,
        collect_kickoff: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Extract and parse match rows from the current page.

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
            kickoff_within_hours (Optional[float]): If provided, keep only rows
                whose kickoff is at most this many hours ahead of now. Rows whose
                kickoff cannot be computed are kept (fail-safe). Combines the
                row's date-header with its HH:MM in the browser timezone (issue
                #77); pair with skip_started to bound the window on both sides.
            collect_kickoff (bool): If True, resolve each row's kickoff and emit
                it as `kickoff_utc`. Off by default because it forces date-header
                tracking, which the historic pagination path does not need.

        Returns:
            List[dict]: One entry per unique match link, each carrying
                `match_link` and `kickoff_utc` (None when undeterminable).
        """
        try:
            html_content = await page.content()
            soup = BeautifulSoup(html_content, "lxml")
            # 2026-08 redesign: rows are [data-testid='game-row'] and date headers
            # are *siblings* (inside a 'secondary-header' element), no longer
            # children of the first row of a group. Walk both in document order.
            elements = soup.find_all(
                attrs={"data-testid": [OddsPortalSelectors.DATE_HEADER_TESTID, OddsPortalSelectors.GAME_ROW_TESTID]}
            )
            row_count = sum(1 for el in elements if el.get("data-testid") == OddsPortalSelectors.GAME_ROW_TESTID)
            self.logger.info(f"Found {row_count} event rows.")

            need_kickoff = kickoff_within_hours is not None or collect_kickoff
            track_headers = date_filter is not None or need_kickoff
            tz_name = getattr(self.playwright_manager, "timezone_id", None) if track_headers else None
            ref_tz = self._resolved_browser_timezone() if need_kickoff else None

            window_cutoff: datetime | None = None
            if kickoff_within_hours is not None:
                window_cutoff = datetime.now(ref_tz) + timedelta(hours=kickoff_within_hours)

            seen: set[str] = set()
            rows_out: list[dict[str, Any]] = []
            current_row_date: date | None = None
            seen_header_dates: set[date] = set()
            filtered_out_count = 0
            unparseable_header_count = 0
            offscreen_skipped_count = 0
            started_filtered_out_count = 0
            window_filtered_out_count = 0

            for el in elements:
                if el.get("data-testid") == OddsPortalSelectors.DATE_HEADER_TESTID:
                    if track_headers:
                        header_text = el.get_text(" ", strip=True)
                        parsed = _parse_date_header(header_text, tz_name=tz_name)
                        if parsed is None:
                            unparseable_header_count += 1
                            self.logger.warning(
                                f"Could not parse date-header '{header_text}'; rows under it will not be filtered."
                            )
                        else:
                            seen_header_dates.add(parsed)
                        current_row_date = parsed
                    continue

                row = el
                if _is_offscreen_row(row):
                    offscreen_skipped_count += 1
                    continue

                if date_filter is not None and current_row_date is not None and current_row_date != date_filter:
                    filtered_out_count += 1
                    continue

                if skip_started and _row_has_started(row):
                    started_filtered_out_count += 1
                    continue

                kickoff_dt = _row_kickoff_datetime(row, current_row_date, ref_tz) if need_kickoff else None

                if window_cutoff is not None and kickoff_dt is not None and kickoff_dt > window_cutoff:
                    window_filtered_out_count += 1
                    continue

                kickoff_utc = format_utc(kickoff_dt) if collect_kickoff and kickoff_dt is not None else None

                for link in row.find_all("a", href=True):
                    href = link["href"]
                    if len(href.strip("/").split("/")) <= 3:
                        continue
                    full_url = f"{self.base_url or ODDSPORTAL_BASE_URL}{href}"
                    if full_url not in seen:
                        seen.add(full_url)
                        rows_out.append({"match_link": full_url, "kickoff_utc": kickoff_utc})

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
                    f"{offscreen_skipped_count} offscreen rows skipped"
                    f"{started_suffix}{window_suffix})."
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
                    f"Extracted {len(rows_out)} unique match links "
                    f"({offscreen_skipped_count} offscreen rows skipped"
                    f"{started_suffix}{window_suffix})."
                )

            return rows_out

        except Exception as e:
            self.logger.error(f"Error extracting match links: {e}", exc_info=True)
            return []

    async def extract_match_links(
        self,
        page: Page,
        date_filter: date | None = None,
        skip_started: bool = False,
        kickoff_within_hours: float | None = None,
    ) -> list[str]:
        """Collect match links from a listing page.

        Thin wrapper over `extract_match_rows` for callers that need only URLs.
        """
        rows = await self.extract_match_rows(
            page=page,
            date_filter=date_filter,
            skip_started=skip_started,
            kickoff_within_hours=kickoff_within_hours,
        )
        return [row["match_link"] for row in rows]

    async def extract_live_match_links(
        self,
        page: Page,
        sport: str | None = None,
        league: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Extract match links and listing context from a live-now in-play listing.

        Rows are `[data-testid='game-row']` elements; this listing carries no
        `eventRow` class, unlike `/matches/`. The testid appears twice per row
        (outer div and a nested div inside the anchor), so dedupe on href.
        Hrefs here already carry the `/inplay-odds/#<id>` suffix.

        Args:
            page (Page): A Playwright Page instance for this task.
            sport (Optional[str]): Sport slug, required when `league` is given.
            league (Optional[str]): League slug; keeps only rows whose href sits
                under the league URL path from SPORTS_LEAGUES_URLS_MAPPING.

        Returns:
            List[dict]: One dict per live match: {"match_link": str, "live_period": str | None}.
        """
        try:
            league_path_prefix = None
            if league and sport:
                league_url = URLBuilder.get_league_url(sport, league)
                league_path_prefix = urlsplit(league_url).path

            html_content = await page.content()
            soup = BeautifulSoup(html_content, "lxml")
            rows = soup.find_all(attrs={"data-testid": OddsPortalSelectors.GAME_ROW_TESTID})

            seen: set[str] = set()
            results: list[dict[str, Any]] = []
            offscreen_skipped = 0
            league_filtered_out = 0

            for row in rows:
                if _is_offscreen_row(row):
                    offscreen_skipped += 1
                    continue

                anchor = row.find("a", href=lambda h: h and "/inplay-odds/" in h)
                if anchor is None:
                    continue
                href = anchor["href"]
                if href in seen:
                    continue
                seen.add(href)

                if league_path_prefix and not href.startswith(league_path_prefix):
                    league_filtered_out += 1
                    continue

                period = None
                time_el = row.find(attrs={"data-testid": OddsPortalSelectors.EVENT_ROW_TIME_ITEM_TESTID})
                if time_el is not None:
                    p = time_el.find("p")
                    text = p.get_text(strip=True) if p else time_el.get_text(strip=True)
                    period = text or None

                results.append(
                    {
                        "match_link": f"{self.base_url or ODDSPORTAL_BASE_URL}{href}",
                        "live_period": period,
                    }
                )

            league_suffix = f", {league_filtered_out} rows outside league '{league}'" if league_path_prefix else ""
            self.logger.info(
                f"Extracted {len(results)} live match links "
                f"({offscreen_skipped} offscreen rows skipped{league_suffix})."
            )
            return results

        except Exception as e:
            self.logger.error(f"Error extracting live match links: {e}", exc_info=True)
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
            Optional[Dict[str, Any]]: A dictionary containing scraped data, or None if scraping fails.
        """
        self.logger.info(f"Scraping match: {match_link}")

        # Navigation is the proxy-sensitive step: let its failures propagate so
        # retry/backoff and multi-proxy failover can attribute them to the proxy.
        # Errors after a successful load are content/DOM issues and must not
        # blacklist a proxy, so they are swallowed to None below except
        # H2HFragmentResolutionError, which is deliberately re-raised.
        await page.goto(match_link, timeout=NAVIGATION_TIMEOUT_MS, wait_until="domcontentloaded")

        try:
            # Wait a bit for dynamic content to load
            await page.wait_for_timeout(DYNAMIC_CONTENT_WAIT_MS)

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
                self.logger.warning(
                    f"No match details found for {match_link} - page may be unavailable or structure changed"
                )
                return None

            if live_mode:
                live_info = _parse_live_info(BeautifulSoup(await page.content(), "lxml"))
                if live_info is None:
                    # No live-info header: the match ended (or lost live coverage)
                    # between listing and visit. Not a scraping failure.
                    self.logger.info(f"No live-info header on {match_link}; match no longer live, skipping.")
                    return {"_live_ended": True, "match_link": match_link}
                match_details.update(live_info)
                match_details["scraped_at_utc"] = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

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

        except H2HFragmentResolutionError:
            raise
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
        except (ZoneInfoNotFoundError, ValueError):
            self.logger.warning(f"Unknown timezone '{tz_id}', falling back to UTC for DOM date parsing")
            return UTC

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
            return format_utc(local_dt)
        except Exception as e:
            self.logger.warning(f"DOM parse failed for match_date: {e}")
            return None

    def _parse_teams_from_dom(self, soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """
        Extract (home_team, away_team) from <div data-testid="game-host">
        and <div data-testid="game-guest">. Returns (None, None) if either
        side is missing - caller falls back to JSON for both fields.
        """

        def _name(container):
            if container is None:
                return None
            el = container.find(attrs={"data-testid": "participant-name"}) or container.find(class_="participant-name")
            el = el or container.find("p")
            text = el.get_text(strip=True) if el else None
            return text or None

        try:
            host = soup.find("div", attrs={"data-testid": OddsPortalSelectors.MATCH_DETAILS_GAME_HOST_TESTID})
            guest = soup.find("div", attrs={"data-testid": OddsPortalSelectors.MATCH_DETAILS_GAME_GUEST_TESTID})
            host_name = _name(host)
            guest_name = _name(guest)
            if not host_name or not guest_name:
                return None, None
            return host_name, guest_name
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
            # Redesign: breadcrumb anchors carry their label as data-testid; the
            # league is the last testid-bearing anchor (the current page is not an <a>).
            links = breadcrumbs.find_all("a", attrs={"data-testid": True})
            if not links:
                return None
            raw = links[-1].get_text(strip=True)
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

    async def _dismiss_login_modal(self, page: Page) -> None:
        """Close the login modal that can block match-page rendering on cold profiles."""
        try:
            el = await page.query_selector(OddsPortalSelectors.LOGIN_MODAL_CLOSE)
            if el and await el.is_visible():
                await el.click()
                await page.wait_for_timeout(500)
                self.logger.info("Dismissed the login modal.")
        except Exception as e:
            self.logger.debug(f"Login modal dismissal skipped: {e}")

    # The SPA hydrates the match view only on an in-page hashchange to the full
    # '#<id>:<market>;<scope>' form; a direct page load with that hash stays on
    # the H2H landing skeleton. Setting the bare id first guarantees the second
    # assignment is a change even when the page URL already carried the full form.
    _HASH_NUDGE_JS = """
    (args) => {
        if (args.bare) {
            window.location.hash = '';
            setTimeout(() => {
                window.location.hash = '#' + args.fragment;
                window.dispatchEvent(new HashChangeEvent('hashchange', { newURL: window.location.href }));
            }, args.delayMs);
            return;
        }
        window.location.hash = '#' + args.fragment;
        setTimeout(() => {
            window.location.hash = '#' + args.fragment + ':' + args.code + ';' + args.scope;
            window.dispatchEvent(new HashChangeEvent('hashchange', { newURL: window.location.href }));
        }, args.delayMs);
    }
    """

    # Hydration needs a market tab that exists for the sport; two-outcome sports
    # have no 1X2 tab. Adjusted by live validation, not exhaustive.
    _DEFAULT_MARKET_CODE_BY_SPORT: ClassVar[dict[str, str]] = {
        "tennis": "home-away",
        "basketball": "home-away",
        "baseball": "home-away",
        "american-football": "home-away",
        "volleyball": "home-away",
        "cricket": "home-away",
    }

    async def _hydrate_match_view(self, page: Page, match_link: str, sport: str | None = None) -> None:
        """Force the SPA to render the fragment match (2026-08 redesign).

        Nudges the URL hash (bare id, then '#<id>:<market>;<scope>' plus an
        explicit hashchange) and waits for `game-time-item` to render. The first
        nudge right after domcontentloaded can fire before the SPA has booted,
        so the nudge is retried. Raises H2HFragmentResolutionError (retryable,
        proxy-neutral) when the view never renders.
        """
        fragment = _extract_fragment_match_id(match_link)
        if fragment is None:
            # Legacy non-fragment match URL: the page renders directly or not at all.
            try:
                await page.wait_for_selector(
                    OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR, timeout=MATCH_HYDRATION_TIMEOUT_MS
                )
            except TimeoutError as e:
                raise H2HFragmentResolutionError(
                    f"match view hydration failed: {match_link} never rendered match content", url=match_link
                ) from e
            return

        if "/inplay-odds/" in match_link:
            # In-play pages hydrate on their own and route their own market codes
            # (e.g. 'O/U', not 'over-under'); forcing the pre-match full-form hash
            # can flip the view to Pre-match Odds. Wait first, nudge the bare id
            # only as a retry.
            for attempt in range(1, MATCH_HYDRATION_ATTEMPTS + 1):
                try:
                    await page.wait_for_selector(
                        OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR, timeout=MATCH_HYDRATION_TIMEOUT_MS
                    )
                    return
                except TimeoutError:
                    self.logger.warning(
                        f"In-play hydration attempt {attempt}/{MATCH_HYDRATION_ATTEMPTS} timed out for {match_link}"
                    )
                    await self._dismiss_login_modal(page)
                    await page.evaluate(
                        self._HASH_NUDGE_JS,
                        {"fragment": fragment, "bare": True, "delayMs": HASH_NUDGE_DELAY_MS},
                    )
            raise H2HFragmentResolutionError(
                f"match view hydration failed: {match_link} never rendered match content", url=match_link
            )

        code = self._DEFAULT_MARKET_CODE_BY_SPORT.get((sport or "").lower(), "1X2")
        scope = OddsPortalSelectors.period_scope_code(sport, "FullTime") or 2
        for attempt in range(1, MATCH_HYDRATION_ATTEMPTS + 1):
            await page.evaluate(
                self._HASH_NUDGE_JS,
                {"fragment": fragment, "code": code, "scope": scope, "delayMs": HASH_NUDGE_DELAY_MS},
            )
            try:
                await page.wait_for_selector(
                    OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR, timeout=MATCH_HYDRATION_TIMEOUT_MS
                )
                return
            except TimeoutError:
                self.logger.warning(
                    f"Match view hydration attempt {attempt}/{MATCH_HYDRATION_ATTEMPTS} timed out for {match_link}"
                )
                await self._dismiss_login_modal(page)

        raise H2HFragmentResolutionError(
            f"match view hydration failed: {match_link} never rendered match content", url=match_link
        )

    def _parse_venue_from_ld_json(
        self, soup: BeautifulSoup, dom_match_date: str | None
    ) -> tuple[str | None, str | None, str | None]:
        """Venue trio from the SSR JSON-LD SportsEvent, staleness-guarded.

        The SSR JSON-LD describes the *next upcoming* meeting of the two teams
        (gotchas §1b), so it is trusted only when its startDate calendar date
        equals the DOM-extracted match date. Returns (venue, town, country),
        all None when absent or stale.
        """
        if not dom_match_date:
            return None, None, None
        try:
            for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
                try:
                    data = json.loads(script.string or "")
                except (TypeError, json.JSONDecodeError):
                    continue
                types = data.get("@type") or []
                if isinstance(types, str):
                    types = [types]
                if "SportsEvent" not in types:
                    continue
                try:
                    ld_date = datetime.fromisoformat(data.get("startDate") or "").astimezone(UTC).date()
                except ValueError:
                    continue
                if ld_date.isoformat() != dom_match_date[:10]:
                    return None, None, None
                location = data.get("location") or {}
                address = location.get("address") or {}
                if not isinstance(address, dict):
                    address = {}
                country = address.get("addressCountry")
                if isinstance(country, dict):
                    country = country.get("name")
                return location.get("name") or None, address.get("addressLocality") or None, country or None
        except Exception as e:
            self.logger.debug(f"JSON-LD venue parse failed: {e}")
        return None, None, None

    async def _extract_match_details(self, page: Page, match_link: str) -> dict[str, Any] | None:
        """
        Extract match details (date, teams, league, scores, venue) from the
        hydrated match page DOM.

        The redesigned page embeds no per-match JSON: content renders only after
        the SPA fetches the fragment match (see `_hydrate_match_view`), so the
        DOM *is* the requested match. Venue comes from the SSR JSON-LD only when
        it describes the same match.

        Returns None when the DOM lacks the minimum landmarks to identify the
        match (no kickoff and no team pair).
        """
        try:
            html_content = await page.content()
            soup = BeautifulSoup(html_content, "html.parser")

            match_date = self._parse_match_date_from_dom(soup)
            home_team, away_team = self._parse_teams_from_dom(soup)
            league_name = self._parse_league_from_dom(soup)
            home_score_raw, away_score_raw, partial_results = self._parse_results_from_dom(soup)

            if match_date is None and (home_team is None or away_team is None):
                self.logger.warning(
                    f"No match landmarks found for {match_link} - page may be unavailable or structure changed"
                )
                return None

            venue, venue_town, venue_country = self._parse_venue_from_ld_json(soup, match_date)

            details = {
                "scraped_date": format_utc(datetime.now(UTC)),
                "match_date": match_date,
                "season": None,
                "match_link": match_link,
                "home_team": home_team,
                "away_team": away_team,
                "league_name": league_name,
                "home_score": str(home_score_raw) if home_score_raw is not None else None,
                "away_score": str(away_score_raw) if away_score_raw is not None else None,
                "partial_results": partial_results,
                "venue": venue.encode("ascii", "ignore").decode("ascii") if venue else None,
                "venue_town": venue_town.encode("ascii", "ignore").decode("ascii") if venue_town else None,
                "venue_country": venue_country,
                "match_info": None,
            }

            if self.local_kickoff:
                venue_timezone, match_date_venue_local = compute_local_kickoff(
                    match_date_utc=details["match_date"],
                    country=details["venue_country"],
                    town=details["venue_town"],
                )
                details["venue_timezone"] = venue_timezone
                details["match_date_venue_local"] = match_date_venue_local

                if venue_timezone is None and details["venue_country"]:
                    self.logger.debug(
                        f"Unresolved venue timezone for country={details['venue_country']!r} "
                        f"town={details['venue_town']!r}; match_date_venue_local left null"
                    )

            return details

        except Exception as e:
            self.logger.error(f"Error extracting match details from the DOM: {e}")
            return None
