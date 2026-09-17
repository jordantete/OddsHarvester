"""Scraper for OddsPortal team pages (the `team` command)."""

from datetime import UTC, datetime
import logging

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.exceptions import ScraperError
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import RetryConfig, retry_with_backoff
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats
from oddsharvester.core.team.team_parser import parse_team_page
from oddsharvester.core.url_builder import rebase_url
from oddsharvester.utils.constants import (
    ODDSPORTAL_BASE_URL,
    OPERATION_RETRY_BASE_DELAY,
    OPERATION_RETRY_MAX_ATTEMPTS,
    OPERATION_RETRY_MAX_DELAY,
)
from oddsharvester.utils.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

PAGE_GOTO_TIMEOUT_MS = 30000

# The site resolves a team page by its id alone: the slug and the sport in the
# path are echoed back but never read, so one placeholder path serves every team.
_TEAM_PATH = "football/team/x"


class TeamScraper:
    """Navigates to a team page and turns it into one record."""

    def __init__(self, playwright_manager: PlaywrightManager, cookie_dismisser: CookieDismisser):
        self.playwright_manager = playwright_manager
        self.cookie_dismisser = cookie_dismisser
        self._cookies_dismissed = False

    async def scrape(self, team_id: str, base_url: str | None = None) -> dict:
        page = self.playwright_manager.page
        url = rebase_url(f"{ODDSPORTAL_BASE_URL}/{_TEAM_PATH}/{team_id}/", base_url)
        logger.info("Navigating to team page: %s", url)
        await page.goto(url, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
        if not self._cookies_dismissed:
            # Once accepted the banner is gone for the whole context, and looking
            # for it again costs a full selector timeout on every later team.
            self._cookies_dismissed = await self.cookie_dismisser.dismiss(page)

        record = parse_team_page(await page.content(), team_id=team_id, team_url=url, base_url=base_url)
        record["scraped_at"] = datetime.now(UTC).isoformat()
        return record


async def run_teams(
    team_ids: list[str],
    headless: bool = True,
    proxy_url=None,
    proxy_user: str | None = None,
    proxy_pass: str | None = None,
    browser_user_agent: str | None = None,
    browser_locale_timezone: str | None = None,
    browser_timezone_id: str | None = None,
    base_url: str | None = None,
) -> ScrapeResult:
    """Owns the Playwright lifecycle for one team-scrape run.

    Args:
        team_ids (list[str]): OddsPortal team ids to scrape, in order.

    Returns:
        ScrapeResult: One record per team that resolved, and a FailedUrl per team
            that did not. A team failing does not stop the ones queued behind it.
    """
    if isinstance(proxy_url, list | tuple):
        proxy_manager = ProxyManager(proxy_urls=list(proxy_url), proxy_user=proxy_user, proxy_pass=proxy_pass)
    else:
        proxy_manager = ProxyManager(proxy_url=proxy_url, proxy_user=proxy_user, proxy_pass=proxy_pass)

    playwright_manager = PlaywrightManager()
    result = ScrapeResult(stats=ScrapeStats(total_urls=len(team_ids)))
    try:
        await playwright_manager.initialize(
            headless=headless,
            user_agent=browser_user_agent,
            locale=browser_locale_timezone,
            timezone_id=browser_timezone_id,
            proxy_manager=proxy_manager,
        )
        scraper = TeamScraper(playwright_manager, CookieDismisser())
        config = RetryConfig(
            max_attempts=OPERATION_RETRY_MAX_ATTEMPTS,
            base_delay=OPERATION_RETRY_BASE_DELAY,
            max_delay=OPERATION_RETRY_MAX_DELAY,
        )

        for team_id in team_ids:
            retry_result = await retry_with_backoff(scraper.scrape, team_id, base_url, config=config)
            if retry_result.success:
                _warn_on_missing_fields(retry_result.result)
                result.success.append(retry_result.result)
                result.stats.successful += 1
            else:
                logger.error(
                    "Team '%s' failed after %d attempts: %s", team_id, retry_result.attempts, retry_result.last_error
                )
                result.failed.append(_failure(team_id, retry_result))
                result.stats.failed += 1

        return result
    finally:
        await playwright_manager.cleanup()


def _warn_on_missing_fields(record: dict) -> None:
    if record.get("list_name") is None:
        logger.warning(
            "Team '%s' has no list_name: the page showed no recent matches for the selected bookmakers.",
            record.get("team_id"),
        )


def _failure(team_id: str, retry_result) -> FailedUrl:
    error = retry_result.last_error
    return FailedUrl(
        url=team_id,
        error_type=ErrorType.PARSING
        if isinstance(error, ScraperError) and not error.is_retryable
        else ErrorType.UNKNOWN,
        error_message=str(error),
        attempts=retry_result.attempts,
        is_retryable=getattr(error, "is_retryable", True),
    )
