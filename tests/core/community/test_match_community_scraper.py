"""Unit tests for MatchCommunityScraper (mocked Playwright page)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import pytest
from tests.clock import frozen_clock
from tests.dom_builders import match_view

from oddsharvester.core.browser.hydration import HASH_NUDGE_JS
from oddsharvester.core.community.match_community_scraper import MatchCommunityScraper, run_match_community
from oddsharvester.core.exceptions import H2HFragmentResolutionError, RateLimitError
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import HASH_NUDGE_DELAY_MS, MATCH_HYDRATION_TIMEOUT_MS

_MATCH_URL = "https://www.oddsportal.com/football/h2h/a-x/b-y/#C2Nfvg77"

_PREMATCH_HTML = match_view(home="A", away="B", weekday="Today,", date="24 Aug 2026,", votes=["67%", "33%", "0%"])


def _manager_with_page(html):
    page = MagicMock()
    page.url = "about:blank"
    page.goto = AsyncMock(side_effect=lambda url, **kwargs: setattr(page, "url", url))
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.evaluate = AsyncMock()
    page.content = AsyncMock(return_value=html)
    manager = MagicMock()
    manager.page = page
    manager.timezone_id = None
    return manager


async def test_scrape_returns_record_with_markets():
    manager = _manager_with_page(_PREMATCH_HTML)
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))
    rec = await scraper.scrape(_MATCH_URL)
    assert rec["home_team"] == "A"
    assert rec["event_id"] == "C2Nfvg77"
    assert rec["markets"][0]["market"] == "1X2"
    assert [o["votes_pct"] for o in rec["markets"][0]["outcomes"]] == [67, 33, 0]
    # The view renders on load: the scraper waits for it and nudges nothing.
    manager.page.wait_for_selector.assert_awaited_once_with(
        OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR, timeout=MATCH_HYDRATION_TIMEOUT_MS
    )
    manager.page.evaluate.assert_not_awaited()


async def test_scrape_nudges_the_hash_only_after_the_view_timed_out():
    manager = _manager_with_page(_PREMATCH_HTML)
    manager.page.wait_for_selector = AsyncMock(side_effect=[PlaywrightTimeoutError("Timeout 8000ms exceeded."), None])
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))

    rec = await scraper.scrape(_MATCH_URL)

    assert rec["markets"][0]["market"] == "1X2"
    manager.page.evaluate.assert_awaited_once_with(
        HASH_NUDGE_JS, {"fragment": "C2Nfvg77", "delayMs": HASH_NUDGE_DELAY_MS, "code": "1X2", "scope": 2}
    )


@pytest.mark.parametrize(
    ("match_url", "base_url"),
    [
        ("https://www.centroquote.it/tennis/h2h/a-x/b-y/#WbDmMwm1", None),
        ("https://www.oddsportal.com/tennis/h2h/a-x/b-y/#WbDmMwm1", "https://www.centroquote.it"),
    ],
)
async def test_a_mirror_tennis_page_nudges_to_the_tennis_default_market(match_url, base_url):
    """The sport comes from the URL path whatever the host: a tennis view has no 1X2 tab."""
    manager = _manager_with_page(_PREMATCH_HTML)
    manager.page.wait_for_selector = AsyncMock(side_effect=[PlaywrightTimeoutError("Timeout 8000ms exceeded."), None])
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))

    await scraper.scrape(match_url, base_url)

    assert manager.page.goto.await_args.args[0].startswith("https://www.centroquote.it/tennis/")
    assert manager.page.evaluate.await_args.args[1]["code"] == "home-away"


async def test_a_refused_match_page_raises_rate_limit_error():
    manager = _manager_with_page(_PREMATCH_HTML)
    manager.page.goto = AsyncMock(return_value=MagicMock(status=429))
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))

    with pytest.raises(RateLimitError, match="rate limited by OddsPortal: HTTP 429 on page"):
        await scraper.scrape(_MATCH_URL)

    manager.page.wait_for_selector.assert_not_awaited()


async def test_scrape_reads_the_kickoff_in_the_browser_zone():
    manager = _manager_with_page(match_view(weekday="Sunday,", date="04 Jan 2026,", time="18:30", votes=["5%", "95%"]))
    manager.timezone_id = "Europe/London"
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))

    with patch("oddsharvester.utils.page_time.datetime", frozen_clock(datetime(2026, 9, 30, 12, 0, tzinfo=UTC))):
        rec = await scraper.scrape(_MATCH_URL)

    assert rec["kickoff"] == "Sunday, 04 Jan 2026, 17:30"


async def test_scrape_non_hydrated_page_returns_empty_markets():
    manager = _manager_with_page("<html><body><h1>A - B</h1></body></html>")
    scraper = MatchCommunityScraper(manager, MagicMock(dismiss=AsyncMock()))
    rec = await scraper.scrape("https://www.oddsportal.com/football/h2h/a-x/b-y/")
    assert rec["markets"] == []


async def test_run_match_community_stamps_scraped_at_and_cleans_up():
    with patch("oddsharvester.core.browser.session.PlaywrightManager") as mgr_cls:
        manager = _manager_with_page(_PREMATCH_HTML)
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        mgr_cls.return_value = manager
        rec = await run_match_community(_MATCH_URL, headless=True)
    assert "scraped_at" in rec
    assert rec["markets"][0]["market"] == "1X2"
    manager.cleanup.assert_awaited_once()


async def test_run_match_community_retries_a_page_that_never_renders_then_raises(caplog):
    with (
        patch("oddsharvester.core.browser.session.PlaywrightManager") as mgr_cls,
        patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        manager = _manager_with_page("<html></html>")
        manager.page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 8000ms exceeded."))
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        mgr_cls.return_value = manager

        with caplog.at_level("ERROR"), pytest.raises(H2HFragmentResolutionError, match="never rendered match content"):
            await run_match_community(_MATCH_URL, headless=True)

    # Each retry reloads the page: a goto that only changes the fragment would keep the view that failed.
    assert manager.page.goto.await_args_list == [
        call(_MATCH_URL, timeout=30000, wait_until="domcontentloaded"),
        call("about:blank"),
        call(_MATCH_URL, timeout=30000, wait_until="domcontentloaded"),
        call("about:blank"),
        call(_MATCH_URL, timeout=30000, wait_until="domcontentloaded"),
    ]
    assert sleep.await_count == 2
    assert "Match-community scrape failed after 3 attempts: match view hydration failed" in caplog.text
    manager.cleanup.assert_awaited_once()
