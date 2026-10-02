"""The browser session of a community or team run, and the page load those runs share."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import urldefrag

from playwright.async_api import Page, Response

from oddsharvester.core.exceptions import RateLimitError
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.utils.constants import PAGE_GOTO_TIMEOUT_MS, RATE_LIMIT_RETRY_DELAY_S
from oddsharvester.utils.proxy_manager import ProxyManager


@asynccontextmanager
async def browser_session(
    headless: bool = True,
    proxy_url: str | list[str] | tuple[str, ...] | None = None,
    proxy_user: str | None = None,
    proxy_pass: str | None = None,
    user_agent: str | None = None,
    locale: str | None = None,
    timezone_id: str | None = None,
) -> AsyncIterator[PlaywrightManager]:
    """Start Playwright behind the run's proxies and yield its manager, cleaned up however the run ends.

    Several proxy URLs make one rotating pool; the other options go to `PlaywrightManager.initialize`.
    """
    if isinstance(proxy_url, list | tuple):
        proxy_manager = ProxyManager(proxy_urls=list(proxy_url), proxy_user=proxy_user, proxy_pass=proxy_pass)
    else:
        proxy_manager = ProxyManager(proxy_url=proxy_url, proxy_user=proxy_user, proxy_pass=proxy_pass)

    playwright_manager = PlaywrightManager()
    try:
        await playwright_manager.initialize(
            headless=headless,
            user_agent=user_agent,
            locale=locale,
            timezone_id=timezone_id,
            proxy_manager=proxy_manager,
        )
        yield playwright_manager
    finally:
        await playwright_manager.cleanup()


def raise_if_rate_limited(response: Response | None, url: str, page_kind: str = "page") -> None:
    """A refused page would otherwise read as a page without data (gotchas §23)."""
    if response is not None and response.status == 429:
        raise RateLimitError(
            f"rate limited by OddsPortal: HTTP 429 on {page_kind} {url}", url=url, retry_after=RATE_LIMIT_RETRY_DELAY_S
        )


async def open_page(page: Page, url: str) -> Response | None:
    """Load `url` on `page`, raising RateLimitError when OddsPortal answers 429."""
    if urldefrag(page.url).url == urldefrag(url).url:
        # Same document: goto would only change the fragment, so a retry would reuse the page that failed.
        await page.goto("about:blank")
    response = await page.goto(url, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
    raise_if_rate_limited(response, url)
    return response
