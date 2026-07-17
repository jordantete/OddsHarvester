"""Scraper for a single match page's embedded community vote data (--match-url)."""

from datetime import UTC, datetime
import logging

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.community.match_community_parser import parse_match_community
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import RetryConfig, retry_with_backoff
from oddsharvester.core.url_builder import rebase_url
from oddsharvester.utils.constants import (
    OPERATION_RETRY_BASE_DELAY,
    OPERATION_RETRY_MAX_ATTEMPTS,
    OPERATION_RETRY_MAX_DELAY,
    SELECTOR_TIMEOUT_MS,
)
from oddsharvester.utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

PAGE_GOTO_TIMEOUT_MS = 30000

# One evaluate() reads everything: pageVar community votes + the #react-event-header
# data JSON (teams / status / start) + the aggregate community pick text.
_EVAL_JS = """() => {
  const pv = window.pageVar || {};
  const hdr = document.getElementById('react-event-header');
  let ed = {}, eb = {};
  if (hdr && hdr.getAttribute('data')) {
    try { const d = JSON.parse(hdr.getAttribute('data')); ed = d.eventData || {}; eb = d.eventBody || {}; }
    catch (e) {}
  }
  const pick = document.querySelector('[data-testid="match-facts-prediction"]');
  return {
    communityData: (pv.predictionData && pv.predictionData.communityData) || null,
    startDate: eb.startDate || pv.startDate || null,
    home_team: ed.home || null,
    away_team: ed.away || null,
    is_started: ed.isStarted === true,
    is_finished: ed.isFinished === true,
    pick_text: pick ? pick.textContent.replace(/\\s+/g, ' ').trim() : null,
  };
}"""


class MatchCommunityScraper:
    """Navigates to a match URL and extracts per-market community vote volume."""

    def __init__(self, playwright_manager: PlaywrightManager, cookie_dismisser: CookieDismisser):
        self.playwright_manager = playwright_manager
        self.cookie_dismisser = cookie_dismisser

    async def scrape(self, match_url: str, base_url: str | None = None) -> dict:
        page = self.playwright_manager.page
        url = rebase_url(match_url, base_url)
        logger.info("Navigating to match page for community votes: %s", url)
        await page.goto(url, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
        await self.cookie_dismisser.dismiss(page)

        try:
            await page.wait_for_selector("#react-event-header", timeout=SELECTOR_TIMEOUT_MS)
        except Exception:
            logger.warning(
                "React event header not found for %s. If community data is empty across matches, "
                "suspect anti-bot detection rather than a parsing bug (docs/agentic-gotchas.md §6/§13).",
                match_url,
            )

        raw = await page.evaluate(_EVAL_JS)
        record = parse_match_community(raw, match_url)
        record["scraped_at"] = datetime.now(UTC).isoformat()
        if not record["markets"]:
            logger.warning(
                "No community vote data for %s (finished match or not yet populated); "
                "OddsPortal drops communityData from finished-match pages (gotchas §13).",
                match_url,
            )
        else:
            logger.info("Parsed %d community markets for %s", len(record["markets"]), match_url)
        return record


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
