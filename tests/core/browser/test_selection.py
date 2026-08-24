from unittest.mock import AsyncMock, MagicMock

import pytest

from oddsharvester.core.browser.selection import (
    BOOKIES_FILTER_STRATEGY,
    PERIOD_STRATEGY,
    PeriodSelector,
    SelectionManager,
)
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors

STRATEGY_CASES = [
    pytest.param(BOOKIES_FILTER_STRATEGY, "classic", "Classic Bookies", id="bookies"),
    pytest.param(PERIOD_STRATEGY, "1st Half", "1st Half", id="period"),
]


def _tab(text: str, active: bool = False):
    el = MagicMock()
    el.text_content = AsyncMock(return_value=text)
    el.get_attribute = AsyncMock(return_value="sub-nav-active-tab" if active else "sub-nav-inactive-tab")
    el.click = AsyncMock()
    return el


def _page(tab_sets):
    """Page whose query_selector_all returns each tab set in sequence (last one repeats)."""
    page = MagicMock()
    page.wait_for_timeout = AsyncMock()
    sets = list(tab_sets)

    async def query(_selector):
        return sets.pop(0) if len(sets) > 1 else sets[0]

    page.query_selector_all = AsyncMock(side_effect=query)
    return page


class TestSelectionManager:
    @pytest.fixture
    def manager(self):
        return SelectionManager()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGY_CASES)
    async def test_returns_false_when_tabs_absent(self, manager, strategy, target_value, display_label):
        page = _page([[]])
        assert await manager.ensure_selected(page, target_value, display_label, strategy) is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGY_CASES)
    async def test_returns_true_noop_when_already_active(self, manager, strategy, target_value, display_label):
        target = _tab(display_label, active=True)
        page = _page([[_tab("All Bookies"), target, _tab("Full Time")]])

        assert await manager.ensure_selected(page, target_value, display_label, strategy) is True

        target.click.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGY_CASES)
    async def test_clicks_and_verifies_activation(self, manager, strategy, target_value, display_label):
        before = _tab(display_label, active=False)
        after = _tab(display_label, active=True)
        page = _page([[_tab("Other"), before], [_tab("Other"), after]])

        assert await manager.ensure_selected(page, target_value, display_label, strategy) is True

        before.click.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGY_CASES)
    async def test_returns_false_when_activation_never_confirms(self, manager, strategy, target_value, display_label):
        before = _tab(display_label, active=False)
        page = _page([[before]])

        assert await manager.ensure_selected(page, target_value, display_label, strategy) is False

        before.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_no_tab_matches_label(self, manager):
        page = _page([[_tab("All Bookies"), _tab("Crypto Bookies")]])

        result = await manager.ensure_selected(page, "classic", "Classic Bookies", BOOKIES_FILTER_STRATEGY)

        assert result is False


class TestPeriodSelector:
    @pytest.fixture
    def selector(self):
        return PeriodSelector()

    def _page(self, url):
        page = MagicMock()
        page.url = url
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_returns_none_when_no_scope_code(self, selector):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2")
        assert await selector.select_by_scope(page, "football", "NotAPeriod") is None
        page.evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_already_active_skips_hash_switch(self, selector):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;3")
        assert await selector.select_by_scope(page, "football", "FirstHalf") is True
        page.evaluate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_switches_scope_via_hash(self, selector):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1:over-under;2")

        async def evaluate(_js, args):
            page.url = f"https://www.oddsportal.com/x/h2h/a/b/#{args['fragment']}:{args['code']};{args['scope']}"

        page.evaluate = AsyncMock(side_effect=evaluate)

        assert await selector.select_by_scope(page, "football", "FirstHalf") is True

        args, kwargs = page.evaluate.await_args
        payload = args[1] if len(args) >= 2 else kwargs.get("arg")
        assert payload == {"fragment": "id1", "code": "over-under", "scope": 3}

    @pytest.mark.asyncio
    async def test_returns_false_when_scope_never_applies(self, selector):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2")
        assert await selector.select_by_scope(page, "football", "FirstHalf") is False

    @pytest.mark.asyncio
    async def test_returns_false_without_market_fragment(self, selector):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1")
        assert await selector.select_by_scope(page, "football", "FirstHalf") is False
        page.evaluate.assert_not_awaited()


def test_strategies_target_sub_nav_tabs():
    assert BOOKIES_FILTER_STRATEGY.tab_selector == OddsPortalSelectors.SUB_NAV_TAB_ANY
    assert PERIOD_STRATEGY.tab_selector == OddsPortalSelectors.SUB_NAV_TAB_ANY
    assert BOOKIES_FILTER_STRATEGY.active_testid == "sub-nav-active-tab"
