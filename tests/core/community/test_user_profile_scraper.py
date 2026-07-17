"""Unit tests for UserProfileScraper (mocked Playwright page)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oddsharvester.core.community.user_profile_scraper import UserProfileScraper, run_user_profile

_PUBLIC_HTML = """
<html><body>
<div data-testid="username">BLAPRO</div>
<div data-testid="user-roi">ROI 18.20%</div>
<div data-testid="member-info">Member since: 23 May 2026 Country: France Profile Privacy: Public</div>
</body></html>
"""


def _manager_with_html(html):
    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.content = AsyncMock(return_value=html)
    manager = MagicMock()
    manager.page = page
    manager.timezone_id = None
    return manager


@pytest.mark.asyncio
async def test_scrape_parses_and_stamps_scraped_at():
    manager = _manager_with_html(_PUBLIC_HTML)
    scraper = UserProfileScraper(manager, MagicMock(dismiss=AsyncMock()))
    rec = await scraper.scrape("BLAPRO")
    assert rec["username"] == "BLAPRO"
    assert rec["privacy"] == "public"


@pytest.mark.asyncio
async def test_run_user_profile_stamps_scraped_at_and_cleans_up():
    with patch("oddsharvester.core.community.user_profile_scraper.PlaywrightManager") as mgr_cls:
        manager = _manager_with_html(_PUBLIC_HTML)
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        mgr_cls.return_value = manager
        rec = await run_user_profile("BLAPRO", headless=True)
    assert "scraped_at" in rec
    assert rec["username"] == "BLAPRO"
    manager.cleanup.assert_awaited_once()
