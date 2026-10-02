"""Unit tests for UserProfileScraper (mocked Playwright page)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.dom_builders import profile_page

from oddsharvester.core.community.user_profile_scraper import UserProfileScraper, run_user_profile
from oddsharvester.core.exceptions import RateLimitError

_PUBLIC_HTML = profile_page()


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
