from unittest.mock import AsyncMock, MagicMock

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import pytest

from oddsharvester.core.browser.market_navigation import (
    ACTIVE_TAB_JS,
    FRESH_VIEW_JS,
    MARKET_VIEW_CAP_MS,
    STALE_TAB_ATTRIBUTE,
    MarketTabNavigator,
)
from oddsharvester.core.browser.waits import SIGNAL_POLL_MS
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import MARKET_SWITCH_WAIT_TIME_MS, SCROLL_PAUSE_TIME_MS, TAB_SWITCH_WAIT_MS

_MATCH_URL = "https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj:1X2;2"
_OVER_UNDER_SWITCH = {
    "fragment": "UNC9hLMj",
    "code": "over-under",
    "scope": 2,
    "tabs": OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR,
    "stale": STALE_TAB_ATTRIBUTE,
}


def _tab(text: str):
    el = MagicMock()
    el.text_content = AsyncMock(return_value=text)
    el.click = AsyncMock()
    return el


def _page(url: str = _MATCH_URL, hash_updates: bool = True):
    """Mocked page whose evaluate() rewrites .url like the SPA hash switch would."""
    page = MagicMock()
    page.url = url
    page.wait_for_timeout = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_function = AsyncMock(return_value=MagicMock())
    page.query_selector_all = AsyncMock(return_value=[])
    page.query_selector = AsyncMock(return_value=None)

    async def evaluate(_js, args):
        if hash_updates:
            page.url = (
                f"https://www.oddsportal.com/football/h2h/a-x/b-y/#{args['fragment']}:{args['code']};{args['scope']}"
            )

    page.evaluate = AsyncMock(side_effect=evaluate)
    return page


class TestMarketTabNavigator:
    @pytest.fixture
    def navigator(self):
        return MarketTabNavigator()

    async def test_hash_navigation_success(self, navigator):
        """A known market code is reached purely through the URL hash: no clicks."""
        page = _page()

        assert await navigator.navigate_to_tab(page, "Over/Under") is True

        args, kwargs = page.evaluate.await_args
        payload = args[1] if len(args) >= 2 else kwargs.get("arg")
        assert payload == _OVER_UNDER_SWITCH
        page.query_selector_all.assert_not_awaited()
        page.wait_for_selector.assert_awaited_once()

    async def test_the_switch_waits_for_the_view_it_renders(self, navigator):
        """R5, R7, R8: one wait for unmarked tabs and the new route, at most the 5.5 s the three sleeps took."""
        page = _page()

        assert await navigator.navigate_to_tab(page, "Over/Under") is True

        page.wait_for_function.assert_awaited_once_with(
            FRESH_VIEW_JS, arg=_OVER_UNDER_SWITCH, timeout=MARKET_VIEW_CAP_MS, polling=SIGNAL_POLL_MS
        )
        page.wait_for_timeout.assert_not_awaited()

    async def test_a_view_never_rendered_warns_and_reads_the_page_as_it_is(self, navigator, caplog):
        page = _page()
        page.wait_for_function = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 5500ms exceeded."))

        with caplog.at_level("WARNING"):
            assert await navigator.navigate_to_tab(page, "Over/Under") is True

        assert "No view of 'over-under;2' within 5500 ms; carrying on with the page as it is." in caplog.text
        page.wait_for_selector.assert_awaited_once()

    async def test_a_market_already_in_the_url_is_not_switched_again(self, navigator):
        """fb_004: every line of the umbrella lives on the tab already shown, and the same hash re-renders nothing."""
        page = _page(url="https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj:over-under;2")

        assert await navigator.navigate_to_tab(page, "Over/Under") is True

        page.evaluate.assert_not_awaited()
        page.wait_for_function.assert_not_awaited()
        page.query_selector_all.assert_not_awaited()

    async def test_a_bare_fragment_is_always_switched(self, navigator):
        """Right after the page load the URL holds '#<id>' only: the first market is switched to."""
        page = _page(url="https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj")

        assert await navigator.navigate_to_tab(page, "1X2") is True

        page.evaluate.assert_awaited_once()
        page.wait_for_function.assert_awaited_once()

    def test_the_market_view_cap_is_the_three_sleeps_it_replaces(self):
        assert MARKET_VIEW_CAP_MS == TAB_SWITCH_WAIT_MS + MARKET_SWITCH_WAIT_TIME_MS + SCROLL_PAUSE_TIME_MS == 5500

    async def test_hash_navigation_preserves_current_scope(self, navigator):
        """The ';<scope>' segment (period) must survive a market switch."""
        page = _page(url="https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj:1X2;3")

        assert await navigator.navigate_to_tab(page, "Over/Under") is True

        args, kwargs = page.evaluate.await_args
        payload = args[1] if len(args) >= 2 else kwargs.get("arg")
        assert payload["scope"] == 3

    async def test_hash_not_applied_falls_back_to_click(self, navigator):
        """If the SPA never reflects the code in the URL, fall back to clicking the tab."""
        page = _page(hash_updates=False)
        tab = _tab("Over/Under")
        page.query_selector_all = AsyncMock(return_value=[_tab("1X2"), tab])
        active = _tab("Over/Under")
        page.query_selector = AsyncMock(return_value=active)

        assert await navigator.navigate_to_tab(page, "Over/Under") is True

        tab.click.assert_awaited_once()
        page.query_selector.assert_awaited_with(OddsPortalSelectors.MARKET_TAB_ACTIVE)

    async def test_unknown_market_goes_straight_to_click(self, navigator):
        page = _page()
        tab = _tab("Odd or Even")
        page.query_selector_all = AsyncMock(return_value=[tab])
        page.query_selector = AsyncMock(return_value=_tab("Odd or Even"))

        assert await navigator.navigate_to_tab(page, "Odd or Even") is True

        page.evaluate.assert_not_awaited()
        tab.click.assert_awaited_once()

    async def test_no_fragment_in_url_falls_back_to_click(self, navigator):
        page = _page(url="https://www.oddsportal.com/football/england/x-y/abcd1234/")
        tab = _tab("1X2")
        page.query_selector_all = AsyncMock(return_value=[tab])
        page.query_selector = AsyncMock(return_value=_tab("1X2"))

        assert await navigator.navigate_to_tab(page, "1X2") is True

        page.evaluate.assert_not_awaited()
        tab.click.assert_awaited_once()

    async def test_click_fallback_rejects_wrong_active_tab(self, navigator):
        page = _page(hash_updates=False)
        tab = _tab("Over/Under")
        page.query_selector_all = AsyncMock(return_value=[tab])
        page.query_selector = AsyncMock(return_value=_tab("1X2"))

        assert await navigator.navigate_to_tab(page, "Over/Under") is False

    async def test_complete_failure(self, navigator):
        page = _page(hash_updates=False)
        page.query_selector_all = AsyncMock(return_value=[_tab("1X2")])

        assert await navigator.navigate_to_tab(page, "Both Teams to Score") is False

    async def test_hash_navigation_content_timeout_falls_back(self, navigator):
        """URL code applied but content never rendered: hash path fails, click path runs."""
        page = _page()
        page.wait_for_selector = AsyncMock(side_effect=TimeoutError("no content"))
        page.query_selector_all = AsyncMock(return_value=[])

        assert await navigator.navigate_to_tab(page, "Over/Under") is False

        page.query_selector_all.assert_awaited()

    async def test_inplay_page_goes_straight_to_click(self, navigator):
        """In-play views use their own hash market codes (e.g. 'O/U'); the
        pre-match hash path must be skipped in favor of clicking the tab."""
        page = _page(url="https://www.oddsportal.com/tennis/h2h/a-x/b-y/inplay-odds/#niGX35MH")
        tab = _tab("Over/Under")
        page.query_selector_all = AsyncMock(return_value=[tab])
        page.query_selector = AsyncMock(return_value=_tab("Over/Under"))

        assert await navigator.navigate_to_tab(page, "Over/Under") is True

        page.evaluate.assert_not_awaited()
        tab.click.assert_awaited_once()

    async def test_a_tab_click_waits_for_the_tab_shown_active(self, navigator):
        """R6: an in-play tab click is read once the active tab names the market, at most 5.5 s."""
        page = _page(url="https://www.oddsportal.com/tennis/h2h/a-x/b-y/inplay-odds/#niGX35MH")
        page.query_selector_all = AsyncMock(return_value=[_tab("Over/Under")])
        page.query_selector = AsyncMock(return_value=_tab("Over/Under"))

        assert await navigator.navigate_to_tab(page, "Over/Under") is True

        page.wait_for_function.assert_awaited_once_with(
            ACTIVE_TAB_JS,
            arg={"selector": OddsPortalSelectors.MARKET_TAB_ACTIVE, "name": "over/under"},
            timeout=MARKET_VIEW_CAP_MS,
            polling=SIGNAL_POLL_MS,
        )
        page.wait_for_timeout.assert_not_awaited()

    async def test_a_tab_never_shown_active_warns_and_is_checked_as_before(self, navigator, caplog):
        page = _page(url="https://www.oddsportal.com/tennis/h2h/a-x/b-y/inplay-odds/#niGX35MH")
        page.query_selector_all = AsyncMock(return_value=[_tab("Over/Under")])
        page.query_selector = AsyncMock(return_value=_tab("Over/Under"))
        page.wait_for_function = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 5500ms exceeded."))

        with caplog.at_level("WARNING"):
            assert await navigator.navigate_to_tab(page, "Over/Under") is True

        assert "No active 'Over/Under' tab within 5500 ms; carrying on with the page as it is." in caplog.text
        page.query_selector.assert_awaited_with(OddsPortalSelectors.MARKET_TAB_ACTIVE)
