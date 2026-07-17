"""Scraper for an OddsPortal public user profile (--user)."""

from datetime import UTC, datetime
import logging

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.community.user_profile_parser import parse_user_profile
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import RetryConfig, retry_with_backoff
from oddsharvester.core.url_builder import rebase_url
from oddsharvester.utils.constants import (
    ODDSPORTAL_BASE_URL,
    OPERATION_RETRY_BASE_DELAY,
    OPERATION_RETRY_MAX_ATTEMPTS,
    OPERATION_RETRY_MAX_DELAY,
    SELECTOR_TIMEOUT_MS,
)
from oddsharvester.utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

PAGE_GOTO_TIMEOUT_MS = 30000


class UserProfileScraper:
    """Navigates to /profile/<username>/ and parses the rendered profile."""

    def __init__(self, playwright_manager: PlaywrightManager, cookie_dismisser: CookieDismisser):
        self.playwright_manager = playwright_manager
        self.cookie_dismisser = cookie_dismisser

    async def scrape(self, username: str, base_url: str | None = None) -> dict:
        page = self.playwright_manager.page
        url = rebase_url(f"{ODDSPORTAL_BASE_URL}/profile/{username}/", base_url)
        logger.info("Navigating to user profile: %s", url)
        await page.goto(url, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
        await self.cookie_dismisser.dismiss(page)

        try:
            await page.wait_for_selector(OddsPortalSelectors.COMMUNITY_PROFILE_USERNAME, timeout=SELECTOR_TIMEOUT_MS)
        except Exception:
            logger.warning(
                "Profile header not found for '%s' (missing/404 profile, or anti-bot; gotchas §6).",
                username,
            )

        html = await page.content()
        record = parse_user_profile(html, tz_name=self.playwright_manager.timezone_id)
        record["scraped_at"] = datetime.now(UTC).isoformat()
        if record["privacy"] == "private":
            logger.warning("Profile '%s' is private; only header stats are available.", username)
        return record


async def run_user_profile(
    username: str,
    headless: bool = True,
    proxy_url=None,
    proxy_user: str | None = None,
    proxy_pass: str | None = None,
    browser_user_agent: str | None = None,
    browser_locale_timezone: str | None = None,
    browser_timezone_id: str | None = None,
    base_url: str | None = None,
) -> dict:
    """Owns the Playwright lifecycle for one user-profile scrape run."""
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
        scraper = UserProfileScraper(playwright_manager, CookieDismisser())
        config = RetryConfig(
            max_attempts=OPERATION_RETRY_MAX_ATTEMPTS,
            base_delay=OPERATION_RETRY_BASE_DELAY,
            max_delay=OPERATION_RETRY_MAX_DELAY,
        )
        retry_result = await retry_with_backoff(scraper.scrape, username, base_url, config=config)
        if retry_result.success:
            return retry_result.result
        logger.error("User-profile scrape failed after %d attempts: %s", retry_result.attempts, retry_result.last_error)
        return {
            "mode": "user",
            "username": username,
            "privacy": None,
            "statistics": [],
            "predictions": [],
            "scraped_at": datetime.now(UTC).isoformat(),
        }
    finally:
        await playwright_manager.cleanup()
