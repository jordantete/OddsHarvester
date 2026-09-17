"""Unit tests for TeamScraper and run_teams (mocked Playwright page)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.dom_builders import team_page

from oddsharvester.core.team.team_scraper import TeamScraper, run_teams


def _manager_with(*pages):
    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.content = AsyncMock(side_effect=list(pages))
    manager = MagicMock()
    manager.page = page
    return manager


@pytest.mark.asyncio
async def test_scrape_returns_a_stamped_record():
    scraper = TeamScraper(_manager_with(team_page()), MagicMock(dismiss=AsyncMock()))

    record = await scraper.scrape("lId4TMwf")

    assert record["name"] == "Liverpool"
    assert record["scraped_at"].endswith("+00:00")


@pytest.mark.asyncio
async def test_scrape_requests_the_id_regardless_of_slug():
    """The id is authoritative; slug and sport prefix in the path are ignored by the site."""
    manager = _manager_with(team_page())
    scraper = TeamScraper(manager, MagicMock(dismiss=AsyncMock()))

    await scraper.scrape("lId4TMwf")

    requested = manager.page.goto.await_args.args[0]
    assert requested.endswith("/lId4TMwf/")
    assert requested.startswith("https://www.oddsportal.com/")


@pytest.mark.asyncio
async def test_scrape_honors_base_url():
    manager = _manager_with(team_page())
    scraper = TeamScraper(manager, MagicMock(dismiss=AsyncMock()))

    record = await scraper.scrape("lId4TMwf", base_url="https://www.centroquote.it")

    assert manager.page.goto.await_args.args[0].startswith("https://www.centroquote.it/")
    assert record["logo_url"].startswith("https://www.centroquote.it/")


@pytest.mark.asyncio
async def test_run_teams_returns_one_record_per_team_and_cleans_up():
    with patch("oddsharvester.core.team.team_scraper.PlaywrightManager") as manager_cls:
        manager = _manager_with(team_page(), team_page(name="Everton", full_name="Everton FC"))
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        manager_cls.return_value = manager

        result = await run_teams(["lId4TMwf", "Oc9WrCqL"], headless=True)

    assert [record["name"] for record in result.success] == ["Liverpool", "Everton"]
    assert result.failed == []
    manager.cleanup.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_teams_keeps_going_after_a_team_without_payload():
    """A wrong id must not cost the run the teams queued behind it."""
    with patch("oddsharvester.core.team.team_scraper.PlaywrightManager") as manager_cls:
        manager = _manager_with(team_page(with_payload=False), team_page())
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        manager_cls.return_value = manager

        result = await run_teams(["zzzzzzzz", "lId4TMwf"], headless=True)

    assert [record["name"] for record in result.success] == ["Liverpool"]
    assert [failure.url for failure in result.failed] == ["zzzzzzzz"]
    assert result.stats.successful == 1
    assert result.stats.failed == 1


@pytest.mark.asyncio
async def test_run_teams_warns_once_when_a_team_has_no_list_name(caplog):
    html = team_page(last_performance={"form": [], "formEvents": []})
    with patch("oddsharvester.core.team.team_scraper.PlaywrightManager") as manager_cls:
        manager = _manager_with(html)
        manager.initialize = AsyncMock()
        manager.cleanup = AsyncMock()
        manager_cls.return_value = manager

        with caplog.at_level("WARNING"):
            result = await run_teams(["lId4TMwf"], headless=True)

    assert result.success[0]["list_name"] is None, "the record is written anyway"
    assert sum("list_name" in record.message for record in caplog.records) == 1


@pytest.mark.asyncio
async def test_the_cookie_banner_is_only_waited_for_until_it_is_dismissed():
    """The banner is per browser context, so re-checking costs a 10s timeout per team."""
    manager = _manager_with(team_page(), team_page(), team_page())
    dismisser = MagicMock(dismiss=AsyncMock(side_effect=[False, True, False]))
    scraper = TeamScraper(manager, dismisser)

    for _ in range(3):
        await scraper.scrape("lId4TMwf")

    assert dismisser.dismiss.await_count == 2, "the third team must not wait on a banner already accepted"
