"""Scraper for a single match page's embedded community vote data (--match-url)."""

from datetime import UTC, datetime
import logging

from oddsharvester.core.base_scraper import BaseScraper
from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.community.match_community_parser import parse_match_community_dom
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import RetryConfig, retry_with_backoff
from oddsharvester.core.url_builder import rebase_url
from oddsharvester.utils.constants import (
    OPERATION_RETRY_BASE_DELAY,
    OPERATION_RETRY_MAX_ATTEMPTS,
    OPERATION_RETRY_MAX_DELAY,
)
from oddsharvester.utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

PAGE_GOTO_TIMEOUT_MS = 30000
_HYDRATION_ATTEMPTS = 3
_HYDRATION_TIMEOUT_MS = 8000
_HYDRATION_NUDGE_DELAY_MS = 1500


class MatchCommunityScraper:
    """Navigates to a match URL and extracts the displayed market's community vote split.

    2026-08 redesign: the pageVar communityData object is gone; votes surface
    only as the "User Predictions" percentage row of the hydrated match view
    (gotchas §19), so the page is hydrated like any match page and parsed from
    the DOM.
    """

    def __init__(self, playwright_manager: PlaywrightManager, cookie_dismisser: CookieDismisser):
        self.playwright_manager = playwright_manager
        self.cookie_dismisser = cookie_dismisser

    async def scrape(self, match_url: str, base_url: str | None = None) -> dict:
        page = self.playwright_manager.page
        url = rebase_url(match_url, base_url)
        logger.info("Navigating to match page for community votes: %s", url)
        await page.goto(url, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
        await self.cookie_dismisser.dismiss(page)

        fragment = OddsPortalSelectors.event_id_from_url(url)
        await self._hydrate(page, url, fragment)

        html = await page.content()
        record = parse_match_community_dom(html, match_url, event_id=fragment)
        record["scraped_at"] = datetime.now(UTC).isoformat()
        if not record["markets"]:
            logger.warning(
                "No community vote data for %s (finished match, no votes yet, or view not hydrated).",
                match_url,
            )
        else:
            logger.info("Parsed %d community market(s) for %s", len(record["markets"]), match_url)
        return record

    async def _hydrate(self, page, url: str, fragment: str | None) -> None:
        """Nudge the hash-driven match view into rendering (same recipe as BaseScraper)."""
        sport = url.split("oddsportal.com/", 1)[-1].split("/", 1)[0] if "oddsportal.com/" in url else ""
        code = BaseScraper._DEFAULT_MARKET_CODE_BY_SPORT.get(sport, "1X2")
        for attempt in range(1, _HYDRATION_ATTEMPTS + 1):
            if fragment:
                await page.evaluate(
                    BaseScraper._HASH_NUDGE_JS,
                    {"fragment": fragment, "code": code, "scope": 2, "delayMs": _HYDRATION_NUDGE_DELAY_MS},
                )
            try:
                await page.wait_for_selector(
                    OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR, timeout=_HYDRATION_TIMEOUT_MS
                )
                return
            except Exception:
                logger.warning("Match view hydration attempt %d/%d timed out for %s", attempt, _HYDRATION_ATTEMPTS, url)


async def run_match_community(
    match_url: str,
    headless: bool = True,
    proxy_url=None,
    proxy_user: str | None = None,
    proxy_pass: str | None = None,
    browser_user_agent: str | None = None,
    browser_locale_timezone: str | None = None,
    browser_timezone_id: str | None = None,
    base_url: str | None = None,
) -> dict:
    """Owns the Playwright lifecycle for one match-community scrape run."""
    if isinstance(proxy_url, list | tuple):
        proxy_manager = ProxyManager(proxy_urls=list(proxy_url), proxy_user=proxy_user, proxy_pass=proxy_pass)
    else:
        proxy_manager = ProxyManager(proxy_url=proxy_url, proxy_user=proxy_user, proxy_pass=proxy_pass)

    playwright_manager = PlaywrightManager()
    try:
        await playwright_manager.initialize(
            headless=headless,
            user_agent=browser_user_agent,
            locale=browser_locale_timezone,
            timezone_id=browser_timezone_id,
            proxy_manager=proxy_manager,
        )
        scraper = MatchCommunityScraper(playwright_manager, CookieDismisser())
        config = RetryConfig(
            max_attempts=OPERATION_RETRY_MAX_ATTEMPTS,
            base_delay=OPERATION_RETRY_BASE_DELAY,
            max_delay=OPERATION_RETRY_MAX_DELAY,
        )
        retry_result = await retry_with_backoff(scraper.scrape, match_url, base_url, config=config)
        if retry_result.success:
            return retry_result.result
        logger.error(
            "Match-community scrape failed after %d attempts: %s", retry_result.attempts, retry_result.last_error
        )
        return {"mode": "match", "match_url": match_url, "markets": [], "scraped_at": datetime.now(UTC).isoformat()}
    finally:
        await playwright_manager.cleanup()
