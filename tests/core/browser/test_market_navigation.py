from unittest.mock import AsyncMock, MagicMock

import pytest

from oddsharvester.core.browser.market_navigation import MarketTabNavigator
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors

_MATCH_URL = "https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj:1X2;2"


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

    @pytest.mark.asyncio
    async def test_hash_navigation_success(self, navigator):
        """A known market code is reached purely through the URL hash: no clicks."""
        page = _page()

        assert await navigator.navigate_to_tab(page, "Over/Under") is True

        args, kwargs = page.evaluate.await_args
        payload = args[1] if len(args) >= 2 else kwargs.get("arg")
        assert payload == {"fragment": "UNC9hLMj", "code": "over-under", "scope": 2}
        page.query_selector_all.assert_not_awaited()
        page.wait_for_selector.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_hash_navigation_preserves_current_scope(self, navigator):
        """The ';<scope>' segment (period) must survive a market switch."""
        page = _page(url="https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj:1X2;3")

        assert await navigator.navigate_to_tab(page, "Over/Under") is True

        args, kwargs = page.evaluate.await_args
        payload = args[1] if len(args) >= 2 else kwargs.get("arg")
        assert payload["scope"] == 3

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_unknown_market_goes_straight_to_click(self, navigator):
        page = _page()
        tab = _tab("Odd or Even")
        page.query_selector_all = AsyncMock(return_value=[tab])
        page.query_selector = AsyncMock(return_value=_tab("Odd or Even"))

        assert await navigator.navigate_to_tab(page, "Odd or Even") is True

        page.evaluate.assert_not_awaited()
        tab.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_fragment_in_url_falls_back_to_click(self, navigator):
        page = _page(url="https://www.oddsportal.com/football/england/x-y/abcd1234/")
        tab = _tab("1X2")
        page.query_selector_all = AsyncMock(return_value=[tab])
        page.query_selector = AsyncMock(return_value=_tab("1X2"))

        assert await navigator.navigate_to_tab(page, "1X2") is True

        page.evaluate.assert_not_awaited()
        tab.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_click_fallback_rejects_wrong_active_tab(self, navigator):
        page = _page(hash_updates=False)
        tab = _tab("Over/Under")
        page.query_selector_all = AsyncMock(return_value=[tab])
        page.query_selector = AsyncMock(return_value=_tab("1X2"))

        assert await navigator.navigate_to_tab(page, "Over/Under") is False

    @pytest.mark.asyncio
    async def test_complete_failure(self, navigator):
        page = _page(hash_updates=False)
        page.query_selector_all = AsyncMock(return_value=[_tab("1X2")])

        assert await navigator.navigate_to_tab(page, "Both Teams to Score") is False

    @pytest.mark.asyncio
    async def test_hash_navigation_content_timeout_falls_back(self, navigator):
        """URL code applied but content never rendered: hash path fails, click path runs."""
        page = _page()
        page.wait_for_selector = AsyncMock(side_effect=TimeoutError("no content"))
        page.query_selector_all = AsyncMock(return_value=[])

        assert await navigator.navigate_to_tab(page, "Over/Under") is False

        page.query_selector_all.assert_awaited()

    @pytest.mark.asyncio
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
