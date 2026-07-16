"""Unit tests for TopPredictionsScraper (mocked Playwright page)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from oddsharvester.core.community.top_predictions_scraper import TopPredictionsScraper

MINIMAL_PAGE_HTML = """
<div data-testid="sport-country-league-item">
  <a data-testid="header-sport-item" href="/football/"><div>Football</div></a>
  <a data-testid="header-country-item" href="/football/europe/"><p>Europe</p></a>
  <a data-testid="header-tournament-item" href="/football/europe/conference-league/">Conference League</a>
</div>
<div data-testid="betting-tip-header">1</div>
<div data-testid="betting-tip-header">X</div>
<div data-testid="betting-tip-header">2</div>
<div data-testid="game-row">
  <a href="/football/h2h/alashkert-aaa/yelimay-bbb/#ccc">
    <div data-testid="date-time-item"><p>Today,</p><p>17:00</p><span>1X2</span></div>
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
    assert records[0]["scraped_at"]


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
    # Fragment routing is not guaranteed to honor non-default sports (gotchas §7):
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
