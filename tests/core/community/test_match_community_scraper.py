"""Unit tests for MatchCommunityScraper (mocked Playwright page)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.dom_builders import match_view

from oddsharvester.core.community.match_community_scraper import MatchCommunityScraper, run_match_community

_MATCH_URL = "https://www.oddsportal.com/football/h2h/a-x/b-y/#C2Nfvg77"

_PREMATCH_HTML = match_view(home="A", away="B", weekday="Today,", date="24 Aug 2026,", votes=["67%", "33%", "0%"])


def _manager_with_page(html):
    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.evaluate = AsyncMock()
    page.content = AsyncMock(return_value=html)
    manager = MagicMock()
    manager.page = page
    manager.timezone_id = None
    return manager


@pytest.mark.asyncio
async def test_scrape_returns_record_with_markets():
    manager = _manager_with_page(_PREMATCH_HTML)
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))
    rec = await scraper.scrape(_MATCH_URL)
    assert rec["home_team"] == "A"
    assert rec["event_id"] == "C2Nfvg77"
    assert rec["markets"][0]["market"] == "1X2"
    assert [o["votes_pct"] for o in rec["markets"][0]["outcomes"]] == [67, 33, 0]
    # The hash nudge must have carried the fragment
    args, kwargs = manager.page.evaluate.await_args
    payload = args[1] if len(args) >= 2 else kwargs.get("arg")
    assert payload["fragment"] == "C2Nfvg77"


@pytest.mark.asyncio
async def test_scrape_non_hydrated_page_returns_empty_markets():
    manager = _manager_with_page("<html><body><h1>A - B</h1></body></html>")
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))
    rec = await scraper.scrape("https://www.oddsportal.com/football/h2h/a-x/b-y/")
    assert rec["markets"] == []


@pytest.mark.asyncio
async def test_run_match_community_stamps_scraped_at_and_cleans_up():
    with patch("oddsharvester.core.community.match_community_scraper.PlaywrightManager") as mgr_cls:
        manager = _manager_with_page(_PREMATCH_HTML)
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        mgr_cls.return_value = manager
        rec = await run_match_community(_MATCH_URL, headless=True)
    assert "scraped_at" in rec
    assert rec["markets"][0]["market"] == "1X2"
    manager.cleanup.assert_awaited_once()
