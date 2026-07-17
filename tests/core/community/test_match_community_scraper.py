"""Unit tests for MatchCommunityScraper (mocked Playwright page)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oddsharvester.core.community.match_community_scraper import MatchCommunityScraper, run_match_community

_EVAL = {
    "communityData": {
        "total": {"E-1_1_2_0_0.00": 3},
        "count": {"a": 2, "b": 1},
        "group": {"a": "E-1_1_2_0_0.00", "b": "E-1_1_2_0_0.00"},
    },
    "startDate": 1784282400,
    "home_team": "A",
    "away_team": "B",
    "is_started": False,
    "is_finished": False,
    "pick_text": "A To win",
}


def _manager_with_eval(eval_result):
    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.evaluate = AsyncMock(return_value=eval_result)
    manager = MagicMock()
    manager.page = page
    manager.timezone_id = None
    return manager


@pytest.mark.asyncio
async def test_scrape_returns_record_with_markets():
    manager = _manager_with_eval(_EVAL)
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))
    rec = await scraper.scrape("https://www.oddsportal.com/football/h2h/a/b/")
    assert rec["home_team"] == "A"
    assert rec["markets"][0]["total_votes"] == 3
    assert rec["markets"][0]["outcome_counts"] == [2, 1]


@pytest.mark.asyncio
async def test_scrape_finished_match_returns_empty_markets():
    manager = _manager_with_eval({**_EVAL, "communityData": None, "is_started": True})
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))
    rec = await scraper.scrape("url")
    assert rec["markets"] == []


@pytest.mark.asyncio
async def test_run_match_community_stamps_scraped_at_and_cleans_up():
    with patch("oddsharvester.core.community.match_community_scraper.PlaywrightManager") as mgr_cls:
        manager = _manager_with_eval(_EVAL)
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        mgr_cls.return_value = manager
        rec = await run_match_community("https://www.oddsportal.com/football/h2h/a/b/", headless=True)
    assert "scraped_at" in rec
    assert rec["markets"][0]["total_votes"] == 3
    manager.cleanup.assert_awaited_once()
