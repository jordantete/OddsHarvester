"""Unit tests for UserProfileScraper (mocked Playwright page)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.dom_builders import profile_page

from oddsharvester.core.community.user_profile_scraper import UserProfileScraper, run_user_profile
from oddsharvester.core.exceptions import RateLimitError

_PUBLIC_HTML = profile_page()
_FEED_URL = "https://www.oddsportal.com/proxy/ajax-communityFeed/profile/58920901/1790665730/"


def _manager_with_html(html):
    page = MagicMock()
    page.url = "about:blank"
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.content = AsyncMock(return_value=html)
    manager = MagicMock()
    manager.page = page
    manager.timezone_id = None
    return manager


async def test_scrape_parses_and_stamps_scraped_at():
    manager = _manager_with_html(_PUBLIC_HTML)
    scraper = UserProfileScraper(manager, MagicMock(dismiss=AsyncMock()))
    rec = await scraper.scrape("BLAPRO")
    assert rec["username"] == "BLAPRO"
    assert rec["privacy"] == "public"


async def test_run_user_profile_stamps_scraped_at_and_cleans_up():
    with patch("oddsharvester.core.browser.session.PlaywrightManager") as mgr_cls:
        manager = _manager_with_html(_PUBLIC_HTML)
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        mgr_cls.return_value = manager
        rec = await run_user_profile("BLAPRO", headless=True)
    assert "scraped_at" in rec
    assert rec["username"] == "BLAPRO"
    manager.cleanup.assert_awaited_once()


async def test_a_refused_profile_page_raises_rate_limit_error():
    manager = _manager_with_html(_PUBLIC_HTML)
    manager.page.goto = AsyncMock(return_value=MagicMock(status=429))
    scraper = UserProfileScraper(manager, MagicMock(dismiss=AsyncMock()))

    with pytest.raises(RateLimitError, match="rate limited by OddsPortal: HTTP 429 on page") as excinfo:
        await scraper.scrape("BLAPRO")

    assert excinfo.value.url == "https://www.oddsportal.com/profile/BLAPRO/"


async def test_run_user_profile_raises_a_rate_limit_that_outlasts_the_retries(caplog):
    with (
        patch("oddsharvester.core.browser.session.PlaywrightManager") as mgr_cls,
        patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock),
    ):
        manager = _manager_with_html(_PUBLIC_HTML)
        manager.page.goto = AsyncMock(return_value=MagicMock(status=429))
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        mgr_cls.return_value = manager

        with caplog.at_level("ERROR"), pytest.raises(RateLimitError, match="rate limited by OddsPortal"):
            await run_user_profile("BLAPRO", headless=True)

    assert "User-profile scrape failed after 3 attempts: rate limited by OddsPortal" in caplog.text
    manager.cleanup.assert_awaited_once()


def _feed_answering(manager, *responses):
    """Clicking the Feed tab delivers `responses` to the page's response listeners, then shows no row."""
    page = manager.page
    listeners = []
    page.on = MagicMock(side_effect=lambda event, handler: listeners.append(handler))
    page.remove_listener = MagicMock(side_effect=lambda event, handler: listeners.remove(handler))

    async def click():
        for response in responses:
            for listener in list(listeners):
                listener(response)

    feed_tab = MagicMock(text_content=AsyncMock(return_value="Feed"), click=AsyncMock(side_effect=click))
    page.query_selector_all = AsyncMock(return_value=[feed_tab])
    page.wait_for_selector = AsyncMock(side_effect=[None, TimeoutError("no prediction row")])
    return listeners


async def test_a_refused_profile_feed_raises_rate_limit_error():
    """A 429 on the Feed AJAX must not store the profile with no predictions (gotchas §23)."""
    manager = _manager_with_html(_PUBLIC_HTML)
    listeners = _feed_answering(manager, MagicMock(status=429, url=_FEED_URL))
    scraper = UserProfileScraper(manager, MagicMock(dismiss=AsyncMock()))

    with pytest.raises(RateLimitError, match=f"HTTP 429 on the profile feed {_FEED_URL}") as excinfo:
        await scraper.scrape("BLAPRO")

    assert excinfo.value.url == _FEED_URL
    assert listeners == [], "the listener is removed once the feed is read"


@pytest.mark.parametrize(
    "response",
    [
        MagicMock(status=200, url=_FEED_URL),
        MagicMock(status=429, url="https://www.oddsportal.com/res/public/images/logo.png"),
    ],
    ids=["feed answered", "429 on another request"],
)
async def test_a_profile_feed_without_rows_keeps_the_profile(response):
    manager = _manager_with_html(_PUBLIC_HTML)
    _feed_answering(manager, response)
    scraper = UserProfileScraper(manager, MagicMock(dismiss=AsyncMock()))

    record = await scraper.scrape("BLAPRO")

    assert record["username"] == "BLAPRO"
    assert record["predictions"] == []
