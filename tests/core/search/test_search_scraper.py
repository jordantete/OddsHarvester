"""Unit tests for SearchScraper and run_search (mocked Playwright page)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.dom_builders import (
    EMPTY_SEARCH_TAB,
    search_match,
    search_next,
    search_page,
    search_participant,
    search_results,
)

from oddsharvester.core.exceptions import PageNotFoundError, ParsingError, RateLimitError
from oddsharvester.core.search.search_scraper import (
    SearchScraper,
    next_matches_url,
    query_url,
    results_url,
    run_search,
)
from oddsharvester.utils.constants import RATE_LIMIT_RETRY_DELAY_S

_SESSION_MANAGER = "oddsharvester.core.browser.session.PlaywrightManager"
_SLEEP = "oddsharvester.core.retry.asyncio.sleep"
_TEAM = "hUyau0Vc"


def _manager_with(*pages):
    page = MagicMock()
    page.url = "about:blank"
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.click = AsyncMock()
    page.content = AsyncMock(side_effect=list(pages))
    manager = MagicMock()
    manager.page = page
    manager.initialize = AsyncMock()
    manager.cleanup = AsyncMock()
    return manager


def _scraper(manager):
    return SearchScraper(manager, MagicMock(dismiss=AsyncMock()), request_delay=0)


def _requested(manager) -> list[str]:
    return [call.args[0] for call in manager.page.goto.await_args_list]


def _event(row: dict) -> str:
    return row["match_link"].rsplit("#", 1)[-1]


def test_query_url_quotes_the_name_and_uses_the_site_path():
    assert query_url("Newell's Old Boys", "football") == (
        "https://www.oddsportal.com/search/results/Newell%27s%20Old%20Boys/football/"
    )
    assert query_url("Potosí", "ice-hockey") == "https://www.oddsportal.com/search/results/Potos%C3%AD/hockey/"
    assert query_url("Nacional", "football", "https://www.centroquote.it").startswith("https://www.centroquote.it/")


def test_team_tab_urls():
    assert next_matches_url(_TEAM) == "https://www.oddsportal.com/search/:hUyau0Vc/"
    assert results_url(_TEAM, 1) == "https://www.oddsportal.com/search/results/:hUyau0Vc/"
    assert results_url(_TEAM, 3) == "https://www.oddsportal.com/search/results/%3AhUyau0Vc/page/3/"


async def test_find_teams_reads_one_page():
    manager = _manager_with(search_page({"participants": {"1": search_participant()}}, search_string="Nacional"))

    candidates = await _scraper(manager).find_teams("Nacional Potosi", "football")

    assert [c["team_id"] for c in candidates] == [_TEAM]
    assert _requested(manager) == ["https://www.oddsportal.com/search/results/Nacional%20Potosi/football/"]


async def test_team_matches_reads_the_upcoming_tab_then_the_first_results_page():
    upcoming = search_match(event_id="NEXT0001", home_result="", away_result="", kickoff=1791500400)
    manager = _manager_with(
        search_page(search_next([upcoming])), search_page(search_results([search_match()], page_count=4))
    )

    rows = await _scraper(manager).team_matches(_TEAM, max_pages=1)

    assert [(row["tab"], _event(row)) for row in rows] == [("next", "NEXT0001"), ("results", "jgMzUSAC")]
    assert _requested(manager) == [next_matches_url(_TEAM), results_url(_TEAM, 1)]


async def test_team_matches_stops_at_the_last_results_page():
    manager = _manager_with(
        search_page(EMPTY_SEARCH_TAB),
        search_page(search_results([search_match(event_id="PAGE0001")], page_count=2)),
        search_page(search_results([search_match(event_id="PAGE0002")], page=2, page_count=2)),
    )

    rows = await _scraper(manager).team_matches(_TEAM, max_pages=5)

    assert [_event(row) for row in rows] == ["PAGE0001", "PAGE0002"]
    assert _requested(manager)[-1] == results_url(_TEAM, 2)
    assert len(_requested(manager)) == 3


async def test_team_matches_honours_max_pages():
    manager = _manager_with(
        search_page(EMPTY_SEARCH_TAB),
        search_page(search_results([search_match(event_id="PAGE0001")], page_count=4)),
        search_page(search_results([search_match(event_id="PAGE0002")], page=2, page_count=4)),
    )

    await _scraper(manager).team_matches(_TEAM, max_pages=2)

    assert len(_requested(manager)) == 3


async def test_a_match_in_both_tabs_keeps_its_results_row():
    """A match in play can still sit under the upcoming tab when it already shows in the results."""
    manager = _manager_with(
        search_page(search_next([search_match(home_result="", away_result="")])),
        search_page(search_results([search_match()])),
    )

    rows = await _scraper(manager).team_matches(_TEAM, max_pages=1)

    assert [(row["tab"], row["home_score"]) for row in rows] == [("results", "2")]


async def test_a_match_shifted_onto_the_next_results_page_is_kept_once():
    """A result landing between two page loads pushes the last row of page 1 onto page 2."""
    manager = _manager_with(
        search_page(EMPTY_SEARCH_TAB),
        search_page(search_results([search_match(event_id="PAGE0001")], page_count=2)),
        search_page(search_results([search_match(event_id="PAGE0001")], page=2, page_count=2)),
    )

    rows = await _scraper(manager).team_matches(_TEAM, max_pages=2)

    assert [_event(row) for row in rows] == ["PAGE0001"]


async def test_a_failing_results_page_fails_the_whole_call():
    manager = _manager_with(
        search_page(EMPTY_SEARCH_TAB),
        search_page(search_results([search_match()], page_count=2)),
        "<main>no payload</main>",
    )

    with pytest.raises(ParsingError, match="no searchData payload"):
        await _scraper(manager).team_matches(_TEAM, max_pages=2)


async def test_a_results_page_serving_page_1_again_fails_the_call():
    manager = _manager_with(
        search_page(EMPTY_SEARCH_TAB),
        search_page(search_results([search_match(event_id="PAGE0001")], page_count=2)),
        search_page(search_results([search_match(event_id="PAGE0001")], page=1, page_count=2)),
    )

    with pytest.raises(ParsingError, match="asked for page 2"):
        await _scraper(manager).team_matches(_TEAM, max_pages=2)


async def test_an_unknown_team_id_fails_without_a_retry():
    manager = _manager_with(search_page(EMPTY_SEARCH_TAB, search_string=""))

    with pytest.raises(PageNotFoundError, match="does not exist on OddsPortal"):
        await _scraper(manager).team_matches("zzzzzzzz", max_pages=1)

    assert manager.page.goto.await_count == 1


async def test_more_upcoming_matches_than_rows_read_is_logged(caplog):
    next_tab = {"total": 25, "rows": [search_match(home_result="", away_result="")]}
    manager = _manager_with(search_page(next_tab), search_page(EMPTY_SEARCH_TAB))

    with caplog.at_level("WARNING"):
        await _scraper(manager).team_matches(_TEAM, max_pages=1)

    assert "25 upcoming matches" in caplog.text


async def test_run_search_returns_the_rows_and_cleans_up():
    with patch(_SESSION_MANAGER) as manager_cls:
        manager = _manager_with(search_page(search_next([])), search_page(search_results([search_match()])))
        manager_cls.return_value = manager

        rows = await run_search(team_id=_TEAM, headless=True, request_delay=0)

    assert [_event(row) for row in rows] == ["jgMzUSAC"]
    manager.cleanup.assert_awaited_once()


async def test_run_search_cleans_up_when_a_page_fails():
    with patch(_SESSION_MANAGER) as manager_cls:
        manager = _manager_with("<main>no payload</main>")
        manager_cls.return_value = manager

        with pytest.raises(ParsingError):
            await run_search(query="Nacional", sport="football", headless=True, request_delay=0)

    manager.cleanup.assert_awaited_once()


async def test_every_page_after_the_first_is_paced():
    with patch(_SESSION_MANAGER) as manager_cls, patch(_SLEEP, new_callable=AsyncMock) as sleep:
        manager = _manager_with(search_page(search_next([])), search_page(search_results([search_match()])))
        manager_cls.return_value = manager

        await run_search(team_id=_TEAM, headless=True, request_delay=1.0)

    assert sleep.await_count == 1
    assert 1.0 <= sleep.await_args.args[0] <= 1.5


async def test_a_refused_page_is_retried_after_the_rate_limit_delay():
    with patch(_SESSION_MANAGER) as manager_cls, patch(_SLEEP, new_callable=AsyncMock) as sleep:
        manager = _manager_with(search_page({"participants": {"1": search_participant()}}))
        manager.page.goto = AsyncMock(side_effect=[MagicMock(status=429), MagicMock(status=200)])
        manager_cls.return_value = manager

        rows = await run_search(query="Nacional", sport="football", headless=True, request_delay=0)

    assert [row["team_id"] for row in rows] == [_TEAM]
    assert sleep.await_args.args[0] >= RATE_LIMIT_RETRY_DELAY_S


async def test_a_page_refused_on_every_attempt_raises_the_rate_limit_error():
    with patch(_SESSION_MANAGER) as manager_cls, patch(_SLEEP, new_callable=AsyncMock):
        manager = _manager_with()
        manager.page.goto = AsyncMock(return_value=MagicMock(status=429))
        manager_cls.return_value = manager

        with pytest.raises(RateLimitError, match="rate limited by OddsPortal"):
            await run_search(query="Nacional", sport="football", headless=True, request_delay=0)
