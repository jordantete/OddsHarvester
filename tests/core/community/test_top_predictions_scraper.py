"""Unit tests for TopPredictionsScraper (mocked Playwright page)."""

from datetime import datetime, timedelta
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oddsharvester.core.community.top_predictions_scraper import TopPredictionsScraper, run_top_predictions
from oddsharvester.core.retry import RetryResult


def _game_row(href: str, market: str = "1X2") -> str:
    return f"""
<div data-testid="sport-country-league-item">
  <a data-testid="header-sport-item" href="/football/"><div>Football</div></a>
  <a data-testid="header-country-item" href="/football/europe/"><p>Europe</p></a>
  <a data-testid="header-tournament-item" href="/football/europe/conference-league/">Conference League</a>
</div>
<div data-testid="betting-tip-header">1</div>
<div data-testid="betting-tip-header">X</div>
<div data-testid="betting-tip-header">2</div>
<div data-testid="game-row">
  <a href="{href}">
    <div data-testid="date-time-item"><p>Today,</p><p>17:00</p><span>{market}</span></div>
    <div data-testid="event-participants"><p>Yelimay Semey</p><p>Alashkert</p></div>
  </a>
  <p data-testid="odd-container-default">1.69</p>
  <div data-testid="prediction-container"><a href="#">89%</a></div>
  <p data-testid="odd-container-default">3.68</p>
  <div data-testid="prediction-container"><a href="#">9%</a></div>
  <p data-testid="odd-container-default">4.70</p>
  <div data-testid="prediction-container"><a href="#">2%</a></div>
</div>
"""


MINIMAL_PAGE_HTML = _game_row("/football/h2h/alashkert-aaa/yelimay-bbb/#ccc")
# One football row + one row whose match_url belongs to another sport.
MIXED_SPORT_PAGE_HTML = MINIMAL_PAGE_HTML + _game_row("/tennis/h2h/player-a/player-b/#ddd")
# Two football rows (for scraped_at batch-sameness assertions).
TWO_FOOTBALL_ROWS_HTML = MINIMAL_PAGE_HTML + _game_row("/football/h2h/team-c/team-d/#eee")

_RUNNER = "oddsharvester.core.community.top_predictions_scraper"


def _make_scraper(page_html: str):
    page = AsyncMock()
    page.content.return_value = page_html
    manager = MagicMock()
    manager.page = page
    manager.timezone_id = "UTC"
    dismisser = AsyncMock()
    return TopPredictionsScraper(playwright_manager=manager, cookie_dismisser=dismisser), page, dismisser


@pytest.mark.asyncio
async def test_scrape_navigates_and_parses():
    scraper, page, dismisser = _make_scraper(MINIMAL_PAGE_HTML)
    records = await scraper.scrape(sport="football")

    page.goto.assert_awaited_once()
    assert "/predictions/#sport/football/" in page.goto.await_args.args[0]
    dismisser.dismiss.assert_awaited_once()
    page.wait_for_selector.assert_awaited()
    assert len(records) == 1
    assert records[0]["sport"] == "football"
    assert records[0]["market"] == "1X2"
    assert records[0]["community_votes_pct"] == [
        {"outcome": "1", "pct": 89},
        {"outcome": "X", "pct": 9},
        {"outcome": "2", "pct": 2},
    ]
    parsed = datetime.fromisoformat(records[0]["scraped_at"])
    assert parsed.utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_scrape_drops_only_wrong_sport_row_in_mixed_batch():
    # Literal "rows are dropped" contract: a football + tennis batch requested as
    # football keeps only the football row, unmodified in sport labelling.
    scraper, _, _ = _make_scraper(MIXED_SPORT_PAGE_HTML)
    records = await scraper.scrape(sport="football")
    assert len(records) == 1
    assert records[0]["sport"] == "football"
    assert "/football/" in records[0]["match_url"]


@pytest.mark.asyncio
async def test_scrape_tags_batch_with_same_scraped_at():
    scraper, _, _ = _make_scraper(TWO_FOOTBALL_ROWS_HTML)
    records = await scraper.scrape(sport="football")
    assert len(records) == 2
    stamps = {r["scraped_at"] for r in records}
    assert len(stamps) == 1
    assert datetime.fromisoformat(stamps.pop()).utcoffset() == timedelta(0)


@pytest.mark.asyncio
async def test_scrape_uses_base_url_override():
    scraper, page, _ = _make_scraper(MINIMAL_PAGE_HTML)
    await scraper.scrape(sport="football", base_url="https://www.centroquote.it")
    assert page.goto.await_args.args[0].startswith("https://www.centroquote.it/predictions/")


@pytest.mark.asyncio
async def test_scrape_returns_empty_on_no_rows():
    scraper, page, _ = _make_scraper("<html><body></body></html>")
    page.wait_for_selector.side_effect = Exception("Timeout 10000ms exceeded")
    records = await scraper.scrape(sport="football")
    assert records == []


@pytest.mark.asyncio
async def test_scrape_drops_rows_of_wrong_sport():
    # Fragment routing is not guaranteed to honor non-default sports (gotchas §1; see §13):
    # rows whose match_url belongs to another sport must be dropped, not mislabeled.
    scraper, _, _ = _make_scraper(MINIMAL_PAGE_HTML)
    records = await scraper.scrape(sport="tennis")
    assert records == []


@pytest.mark.asyncio
async def test_scrape_maps_ice_hockey_to_site_slug():
    scraper, page, _ = _make_scraper("<html><body></body></html>")
    page.wait_for_selector.side_effect = Exception("Timeout 10000ms exceeded")
    await scraper.scrape(sport="ice-hockey")
    assert "/predictions/#sport/hockey/" in page.goto.await_args.args[0]


# --- run_top_predictions runner (Playwright lifecycle) ---


@pytest.mark.asyncio
@patch(f"{_RUNNER}.CookieDismisser")
@patch(f"{_RUNNER}.ProxyManager")
@patch(f"{_RUNNER}.TopPredictionsScraper")
@patch(f"{_RUNNER}.PlaywrightManager")
async def test_run_top_predictions_success(pm_cls, scraper_cls, proxy_cls, cookie_cls):
    pm = MagicMock()
    pm.initialize = AsyncMock()
    pm.cleanup = AsyncMock()
    pm_cls.return_value = pm

    records = [{"sport": "football", "scraped_at": "2026-07-16T00:00:00+00:00"}]
    scraper = MagicMock()
    scraper.scrape = AsyncMock(return_value=records)
    scraper_cls.return_value = scraper

    proxy_instance = MagicMock()
    proxy_cls.return_value = proxy_instance

    result = await run_top_predictions(
        sport="football",
        headless=False,
        proxy_url="http://proxy:1",
        proxy_user="u",
        proxy_pass="pw",
        browser_user_agent="ua",
        browser_locale_timezone="Europe/Paris",
        browser_timezone_id="Europe/Paris",
        base_url="https://mirror.example",
    )

    proxy_cls.assert_called_once_with(proxy_url="http://proxy:1", proxy_user="u", proxy_pass="pw")
    pm.initialize.assert_awaited_once_with(
        headless=False,
        user_agent="ua",
        locale="Europe/Paris",
        timezone_id="Europe/Paris",
        proxy_manager=proxy_instance,
    )
    scraper.scrape.assert_awaited_once_with("football", "https://mirror.example")
    pm.cleanup.assert_awaited_once()
    assert result == records


@pytest.mark.asyncio
@patch(f"{_RUNNER}.retry_with_backoff")
@patch(f"{_RUNNER}.CookieDismisser")
@patch(f"{_RUNNER}.ProxyManager")
@patch(f"{_RUNNER}.TopPredictionsScraper")
@patch(f"{_RUNNER}.PlaywrightManager")
async def test_run_top_predictions_retry_exhausted(pm_cls, scraper_cls, proxy_cls, cookie_cls, retry_mock, caplog):
    pm = MagicMock()
    pm.initialize = AsyncMock()
    pm.cleanup = AsyncMock()
    pm_cls.return_value = pm
    scraper_cls.return_value = MagicMock()

    retry_mock.return_value = RetryResult(success=False, result=None, attempts=3, last_error="boom", error_type=None)

    with caplog.at_level(logging.ERROR):
        result = await run_top_predictions(sport="football")

    assert result == []
    pm.cleanup.assert_awaited_once()
    assert any("Top predictions scrape failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
@patch(f"{_RUNNER}.CookieDismisser")
@patch(f"{_RUNNER}.TopPredictionsScraper")
@patch(f"{_RUNNER}.PlaywrightManager")
@patch(f"{_RUNNER}.ProxyManager")
async def test_run_top_predictions_multi_proxy_branch(proxy_cls, pm_cls, scraper_cls, cookie_cls):
    pm = MagicMock()
    pm.initialize = AsyncMock()
    pm.cleanup = AsyncMock()
    pm_cls.return_value = pm
    scraper = MagicMock()
    scraper.scrape = AsyncMock(return_value=[])
    scraper_cls.return_value = scraper

    await run_top_predictions(sport="football", proxy_url=("http://a:1", "http://b:2"))

    proxy_cls.assert_called_once_with(proxy_urls=["http://a:1", "http://b:2"], proxy_user=None, proxy_pass=None)


@pytest.mark.asyncio
@patch(f"{_RUNNER}.CookieDismisser")
@patch(f"{_RUNNER}.TopPredictionsScraper")
@patch(f"{_RUNNER}.PlaywrightManager")
@patch(f"{_RUNNER}.ProxyManager")
async def test_run_top_predictions_single_proxy_branch(proxy_cls, pm_cls, scraper_cls, cookie_cls):
    pm = MagicMock()
    pm.initialize = AsyncMock()
    pm.cleanup = AsyncMock()
    pm_cls.return_value = pm
    scraper = MagicMock()
    scraper.scrape = AsyncMock(return_value=[])
    scraper_cls.return_value = scraper

    await run_top_predictions(sport="football", proxy_url="http://a:1")

    proxy_cls.assert_called_once_with(proxy_url="http://a:1", proxy_user=None, proxy_pass=None)
