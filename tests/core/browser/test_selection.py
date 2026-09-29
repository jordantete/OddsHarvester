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
    """A sub-nav button; the selected one carries an inline font-weight."""
    el = MagicMock()
    el.text_content = AsyncMock(return_value=text)
    style = "background-color: rgb(47, 47, 47); font-weight: 700; color: rgb(255, 255, 255);" if active else None
    el.get_attribute = AsyncMock(return_value=style)
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

    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGY_CASES)
    async def test_returns_false_when_tabs_absent(self, manager, strategy, target_value, display_label):
        page = _page([[]])
        assert await manager.ensure_selected(page, target_value, display_label, strategy) is False

    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGY_CASES)
    async def test_returns_true_noop_when_already_active(self, manager, strategy, target_value, display_label):
        target = _tab(display_label, active=True)
        page = _page([[_tab("All Bookies"), target, _tab("Full Time")]])

        assert await manager.ensure_selected(page, target_value, display_label, strategy) is True

        target.click.assert_not_awaited()

    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGY_CASES)
    async def test_clicks_and_verifies_activation(self, manager, strategy, target_value, display_label):
        before = _tab(display_label, active=False)
        after = _tab(display_label, active=True)
        page = _page([[_tab("Other"), before], [_tab("Other"), after]])

        assert await manager.ensure_selected(page, target_value, display_label, strategy) is True

        before.click.assert_awaited_once()

    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGY_CASES)
    async def test_returns_false_when_activation_never_confirms(self, manager, strategy, target_value, display_label):
        before = _tab(display_label, active=False)
        page = _page([[before]])

        assert await manager.ensure_selected(page, target_value, display_label, strategy) is False

        before.click.assert_awaited_once()

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

    async def test_returns_none_when_no_scope_code(self, selector):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2")
        assert await selector.select_by_scope(page, "football", "NotAPeriod") is None
        page.evaluate.assert_not_awaited()

    def _bar_page(self, url, active, tabs=3):
        """A page whose hash switch lands in the URL, with a period bar of `tabs` tabs.

        `active` is the index of the bold tab: -1 for none, None for a page without a period bar.
        """
        page = self._page(url)

        async def evaluate(_js, args):
            if "fragment" in args:
                page.url = f"https://www.oddsportal.com/x/h2h/a/b/#{args['fragment']}:{args['code']};{args['scope']}"
                return None
            return None if active is None else {"tabs": tabs, "active": active}

        page.evaluate = AsyncMock(side_effect=evaluate)
        return page

    async def test_already_active_skips_hash_switch(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;3", active=1)

        assert await selector.select_by_scope(page, "football", "FirstHalf") is True

        page.evaluate.assert_awaited_once()
        assert "fragment" not in page.evaluate.await_args.args[1]

    async def test_switches_scope_via_hash(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:over-under;2", active=1)

        assert await selector.select_by_scope(page, "football", "FirstHalf") is True

        assert page.evaluate.await_args_list[0].args[1] == {"fragment": "id1", "code": "over-under", "scope": 3}

    async def test_a_period_the_match_lacks_is_refused(self, selector, caplog):
        """NFL 2nd Half forced into the URL: the page keeps its first tab, FT including OT, active."""
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:home-away;1", active=0, tabs=6)

        with caplog.at_level("WARNING"):
            assert await selector.select_by_scope(page, "american-football", "SecondHalf") is False

        assert page.url.endswith(";4")
        assert "the page still shows its first period tab, so the match has no such period" in caplog.text

    async def test_a_period_the_match_has_is_selected(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:home-away;1", active=2, tabs=6)

        assert await selector.select_by_scope(page, "american-football", "FirstQuarter") is True

    async def test_a_scope_already_in_the_url_is_checked_on_screen_too(self, selector):
        """Baseball Full Time left in the URL by an earlier market: the page still shows FT including OT."""
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:over-under;2", active=0)

        assert await selector.select_by_scope(page, "baseball", "FullTime") is False

        page.evaluate.assert_awaited_once()

    @pytest.mark.parametrize(
        ("active", "tabs"),
        [(0, 1), (-1, 3), (None, 0)],
        ids=["single-tab-bar", "no-bold-tab", "no-period-bar"],
    )
    async def test_a_period_that_cannot_be_seen_on_screen_is_refused(self, selector, active, tabs):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2", active=active, tabs=tabs)

        assert await selector.select_by_scope(page, "football", "SecondHalf") is False

    async def test_the_default_period_needs_only_the_url(self, selector):
        """Basketball FT including OT is the page's first tab: no period bar read."""
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:home-away;2", active=0)

        assert await selector.select_by_scope(page, "basketball", "FullIncludingOT") is True

        page.evaluate.assert_awaited_once()
        assert page.evaluate.await_args.args[1]["scope"] == 1

    async def test_the_collector_path_reads_nothing_on_the_page(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2", active=None)

        assert await selector.select_by_scope(page, "football", "FullTime") is True

        page.evaluate.assert_not_awaited()

    async def test_returns_false_when_scope_never_applies(self, selector):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2")
        assert await selector.select_by_scope(page, "football", "FirstHalf") is False

    async def test_returns_false_without_market_fragment(self, selector):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1")
        assert await selector.select_by_scope(page, "football", "FirstHalf") is False
        page.evaluate.assert_not_awaited()


def test_strategies_target_sub_nav_tabs():
    assert BOOKIES_FILTER_STRATEGY.tab_selector == OddsPortalSelectors.SUB_NAV_TAB_ANY
    assert PERIOD_STRATEGY.tab_selector == OddsPortalSelectors.SUB_NAV_TAB_ANY
    assert BOOKIES_FILTER_STRATEGY.active_style_marker == OddsPortalSelectors.SUB_NAV_ACTIVE_STYLE_MARKER
