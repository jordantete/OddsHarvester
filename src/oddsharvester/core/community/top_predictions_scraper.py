"""Scraper for the OddsPortal Community Top Predictions page."""

from datetime import UTC, datetime
import logging

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.session import browser_session, open_page
from oddsharvester.core.community.top_predictions_parser import parse_top_predictions
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import OPERATION_RETRY_CONFIG, retry_with_backoff
from oddsharvester.core.url_builder import rebase_url, site_slug
from oddsharvester.utils.constants import (
    ODDSPORTAL_BASE_URL,
    SELECTOR_TIMEOUT_MS,
)

logger = logging.getLogger(__name__)


class TopPredictionsScraper:
    """Navigates to /community/predictions/#sport/<sport>/ and parses the rendered picks."""

    def __init__(self, playwright_manager: PlaywrightManager, cookie_dismisser: CookieDismisser):
        self.playwright_manager = playwright_manager
        self.cookie_dismisser = cookie_dismisser

    async def scrape(self, sport: str, base_url: str | None = None) -> list[dict]:
        page = self.playwright_manager.page
        slug = site_slug(sport)
        url = rebase_url(f"{ODDSPORTAL_BASE_URL}/community/predictions/#sport/{slug}/", base_url)
        logger.info(f"Navigating to top predictions page: {url}")
        await open_page(page, url)
        await self.cookie_dismisser.dismiss(page)

        try:
            # Wait for a prediction row inside the page content: rows rendered by
            # other widgets sit outside it and parse to nothing.
            await page.wait_for_selector(OddsPortalSelectors.COMMUNITY_ROW_READY_SELECTOR, timeout=SELECTOR_TIMEOUT_MS)
        except Exception:
            # 0 rows with no error is the anti-bot signature (gotchas §6) — or genuinely no picks.
            logger.warning(
                "No top-predictions rows rendered for sport=%s. If this persists across sports, "
                "suspect anti-bot detection rather than a parsing bug (docs/agentic-gotchas.md §6).",
                sport,
            )
            return []

        html = await page.content()
        scraped_at = datetime.now(UTC).isoformat()
        records = parse_top_predictions(html, tz_name=self.playwright_manager.timezone_id)

        # Fragment routing is not guaranteed to switch the SPA to the requested sport
        # (gotchas §1; see §13) — validate each row's match_url path and drop mismatches rather
        # than emit picks mislabeled with the requested sport.
        expected_prefix = f"/{slug}/"
        matching = [
            r for r in records if r["match_url"].replace(ODDSPORTAL_BASE_URL, "", 1).startswith(expected_prefix)
        ]
        if records and not matching:
            logger.error(
                "Top predictions page rendered %d rows but none belong to sport=%s "
                "(fragment routing likely ignored); returning empty result.",
                len(records),
                sport,
            )
            return []

        for record in matching:
            record["sport"] = sport
            record["scraped_at"] = scraped_at
        logger.info(f"Parsed {len(matching)} top predictions for sport={sport}")
        return matching


async def run_top_predictions(
    sport: str,
    headless: bool = True,
    proxy_url=None,
    proxy_user: str | None = None,
    proxy_pass: str | None = None,
    browser_user_agent: str | None = None,
    browser_locale_timezone: str | None = None,
    browser_timezone_id: str | None = None,
    base_url: str | None = None,
) -> list[dict]:
    """Owns the Playwright lifecycle for one top-predictions scrape run."""
    async with browser_session(
        headless=headless,
        proxy_url=proxy_url,
        proxy_user=proxy_user,
        proxy_pass=proxy_pass,
        user_agent=browser_user_agent,
        locale=browser_locale_timezone,
        timezone_id=browser_timezone_id,
    ) as playwright_manager:
        scraper = TopPredictionsScraper(playwright_manager, CookieDismisser())
        retry_result = await retry_with_backoff(scraper.scrape, sport, base_url, config=OPERATION_RETRY_CONFIG)
        if retry_result.success:
            return retry_result.result
        logger.error(f"Top predictions scrape failed after {retry_result.attempts} attempts: {retry_result.last_error}")
        return []
