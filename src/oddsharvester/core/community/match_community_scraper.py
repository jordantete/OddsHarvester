"""Scraper for a single match page's embedded community vote data (--match-url)."""

from datetime import UTC, datetime
import logging
from urllib.parse import urlsplit

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.hydration import hydrate_match_view
from oddsharvester.core.browser.session import browser_session, open_page
from oddsharvester.core.community.match_community_parser import parse_match_community_dom
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import OPERATION_RETRY_CONFIG, retry_with_backoff
from oddsharvester.core.url_builder import rebase_url

logger = logging.getLogger(__name__)


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
        await open_page(page, url)
        await self.cookie_dismisser.dismiss(page)

        # The sport is the first path segment on every mirror; a two-outcome sport has no 1X2 tab to nudge to.
        await hydrate_match_view(page, url, sport=urlsplit(url).path.strip("/").split("/", 1)[0])

        fragment = OddsPortalSelectors.event_id_from_url(url)
        html = await page.content()
        record = parse_match_community_dom(
            html, match_url, event_id=fragment, tz_name=self.playwright_manager.timezone_id
        )
        record["scraped_at"] = datetime.now(UTC).isoformat()
        if not record["markets"]:
            logger.warning("No community vote data for %s: the page shows no vote row.", match_url)
        else:
            logger.info("Parsed %d community market(s) for %s", len(record["markets"]), match_url)
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
    """Owns the Playwright lifecycle for one match-community scrape run.

    Raises the last error when every attempt failed, so a page that never rendered is not reported as a match
    without votes.
    """
    async with browser_session(
        headless=headless,
        proxy_url=proxy_url,
        proxy_user=proxy_user,
        proxy_pass=proxy_pass,
        user_agent=browser_user_agent,
        locale=browser_locale_timezone,
        timezone_id=browser_timezone_id,
    ) as playwright_manager:
        scraper = MatchCommunityScraper(playwright_manager, CookieDismisser())
        retry_result = await retry_with_backoff(scraper.scrape, match_url, base_url, config=OPERATION_RETRY_CONFIG)
        if retry_result.success:
            return retry_result.result
        logger.error(
            "Match-community scrape failed after %d attempts: %s", retry_result.attempts, retry_result.last_error
        )
        raise retry_result.exception
