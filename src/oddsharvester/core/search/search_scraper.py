"""Scraper for OddsPortal's search pages (the `search` command)."""

from functools import partial
import logging
from urllib.parse import quote, urldefrag

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.session import browser_session, open_page
from oddsharvester.core.exceptions import ScraperError
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import OPERATION_RETRY_CONFIG, RequestPacer, retry_with_backoff
from oddsharvester.core.search.search_parser import MatchPage, parse_candidates, parse_matches
from oddsharvester.core.url_builder import rebase_url, site_slug
from oddsharvester.utils.constants import DEFAULT_REQUEST_DELAY_S, ODDSPORTAL_BASE_URL

logger = logging.getLogger(__name__)


def query_url(query: str, sport: str, base_url: str | None = None) -> str:
    return rebase_url(f"{ODDSPORTAL_BASE_URL}/search/results/{quote(query, safe='')}/{site_slug(sport)}/", base_url)


def next_matches_url(team_id: str, base_url: str | None = None) -> str:
    return rebase_url(f"{ODDSPORTAL_BASE_URL}/search/:{team_id}/", base_url)


def results_url(team_id: str, page: int, base_url: str | None = None) -> str:
    path = f"/search/results/:{team_id}/" if page == 1 else f"/search/results/%3A{team_id}/page/{page}/"
    return rebase_url(f"{ODDSPORTAL_BASE_URL}{path}", base_url)


class SearchScraper:
    """Reads search pages one after the other, each paced, retried, and fatal to the call when it fails."""

    def __init__(self, playwright_manager: PlaywrightManager, cookie_dismisser: CookieDismisser, request_delay: float):
        self.playwright_manager = playwright_manager
        self.cookie_dismisser = cookie_dismisser
        self.pacer = RequestPacer(request_delay)

    async def find_teams(self, query: str, sport: str, base_url: str | None = None) -> list[dict]:
        url = query_url(query, sport, base_url)
        return await self._read(url, partial(parse_candidates, url=url, base_url=base_url))

    async def team_matches(self, team_id: str, max_pages: int, base_url: str | None = None) -> list[dict]:
        url = next_matches_url(team_id, base_url)
        upcoming: MatchPage = await self._read(
            url, partial(parse_matches, url=url, team_id=team_id, tab="next", base_url=base_url)
        )
        if upcoming.total > len(upcoming.rows):
            logger.warning(
                "Team '%s' has %d upcoming matches, only the %d of the first page are read.",
                team_id,
                upcoming.total,
                len(upcoming.rows),
            )

        results = []
        for page in range(1, max_pages + 1):
            url = results_url(team_id, page, base_url)
            current: MatchPage = await self._read(
                url, partial(parse_matches, url=url, team_id=team_id, tab="results", base_url=base_url)
            )
            results += current.rows
            if page >= current.page_count:
                break
        return _merge(upcoming.rows, results)

    async def _read(self, url: str, parse):
        await self.pacer.wait()
        retry_result = await retry_with_backoff(self._load, url, parse, config=OPERATION_RETRY_CONFIG)
        if not retry_result.success:
            raise retry_result.exception or ScraperError(retry_result.last_error or "search page failed", url)
        return retry_result.result

    async def _load(self, url: str, parse):
        page = self.playwright_manager.page
        logger.info("Navigating to search page: %s", url)
        await open_page(page, url)
        await self.cookie_dismisser.dismiss(page)
        return parse(await page.content())


def _merge(upcoming: list[dict], results: list[dict]) -> list[dict]:
    """Upcoming first, then results; a match met twice keeps its results row, or its first one."""
    played = {_event_id(row) for row in results}
    merged, seen = [], set()
    for row in [row for row in upcoming if _event_id(row) not in played] + results:
        if _event_id(row) not in seen:
            seen.add(_event_id(row))
            merged.append(row)
    return merged


def _event_id(row: dict) -> str:
    return urldefrag(row["match_link"]).fragment


async def run_search(
    query: str | None = None,
    sport: str | None = None,
    team_id: str | None = None,
    max_pages: int = 1,
    headless: bool = True,
    proxy_url=None,
    proxy_user: str | None = None,
    proxy_pass: str | None = None,
    browser_user_agent: str | None = None,
    browser_locale_timezone: str | None = None,
    browser_timezone_id: str | None = None,
    base_url: str | None = None,
    request_delay: float = DEFAULT_REQUEST_DELAY_S,
) -> list[dict]:
    """Owns the Playwright lifecycle for one search: ``team_id`` lists its matches, else ``query`` its teams.

    Args:
        max_pages (int): Results pages read for ``team_id``, 20 matches each.
        request_delay (float): Seconds between two pages, jittered; none before the first.

    Raises:
        ScraperError: The first page that failed after its retries; nothing partial is returned.
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
        scraper = SearchScraper(playwright_manager, CookieDismisser(), request_delay)
        if team_id:
            return await scraper.team_matches(team_id, max_pages, base_url)
        return await scraper.find_teams(query, sport, base_url)
