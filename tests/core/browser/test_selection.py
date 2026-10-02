from unittest.mock import AsyncMock, MagicMock, call

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import pytest
from tests.core.browser.fake_view_data import serve_view_data

from oddsharvester.core.browser.market_navigation import FRESH_VIEW_JS, STALE_TAB_ATTRIBUTE
from oddsharvester.core.browser.selection import (
    _PERIOD_TAB_ACTIVE_JS,
    _TAB_SHOWN_ACTIVE_JS,
    BOOKIES_FILTER_STRATEGY,
    PERIOD_STRATEGY,
    PeriodSelector,
    SelectionManager,
)
from oddsharvester.core.browser.waits import SIGNAL_POLL_MS
from oddsharvester.core.exceptions import MarketDataError
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import FALLBACK_VERIFY_WAIT_MS, MARKET_SWITCH_WAIT_TIME_MS

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
    page.wait_for_function = AsyncMock(return_value=MagicMock())
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

    async def test_a_click_waits_for_the_selected_style(self, manager):
        """R10: the click is checked once the button shows the selected style, at most FALLBACK_VERIFY_WAIT_MS."""
        before = _tab("All Bookies", active=False)
        page = _page([[before], [_tab("All Bookies", active=True)]])

        assert await manager.ensure_selected(page, "all", "All Bookies", BOOKIES_FILTER_STRATEGY) is True

        page.wait_for_function.assert_awaited_once_with(
            _TAB_SHOWN_ACTIVE_JS,
            arg={"selector": OddsPortalSelectors.SUB_NAV_TAB_ANY, "label": "all bookies", "marker": "font-weight:700"},
            timeout=FALLBACK_VERIFY_WAIT_MS,
            polling=SIGNAL_POLL_MS,
        )
        page.wait_for_timeout.assert_not_awaited()

    async def test_a_click_never_shown_selected_warns_and_fails(self, manager, caplog):
        before = _tab("Crypto Bookies", active=False)
        page = _page([[before]])
        page.wait_for_function = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 1000ms exceeded."))

        with caplog.at_level("WARNING"):
            assert await manager.ensure_selected(page, "crypto", "Crypto Bookies", BOOKIES_FILTER_STRATEGY) is False

        assert "No selected bookies-filter 'Crypto Bookies' within 1000 ms" in caplog.text
        assert "Failed to set bookies-filter to: Crypto Bookies" in caplog.text

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
        page.wait_for_function = AsyncMock(return_value=MagicMock())
        page.evaluate = AsyncMock()
        return page

    async def test_returns_none_when_no_scope_code(self, selector):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2")
        assert await selector.select_by_scope(page, "football", "NotAPeriod") is None
        page.evaluate.assert_not_awaited()

    async def test_a_period_switch_without_its_data_fails_instead_of_reading_the_previous_period(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:over-under;2", active=1, status=503)

        with pytest.raises(MarketDataError, match="refused the data of the view 'over-under;3': HTTP 503"):
            await selector.select_by_scope(page, "football", "FirstHalf")

    async def test_a_period_switch_given_another_market_fails_instead_of_reading_it(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:over-under;2", active=1, rendered=1)

        with pytest.raises(MarketDataError, match="sent the data of market 1 for the view 'over-under;3'"):
            await selector.select_by_scope(page, "football", "FirstHalf")

    async def test_a_period_view_that_never_rendered_fails_instead_of_reading_the_previous_period(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:over-under;2", active=1)
        page.wait_for_function = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 3000ms exceeded."))

        with pytest.raises(MarketDataError, match="The view 'over-under;3' did not render within 3000 ms"):
            await selector.select_by_scope(page, "football", "FirstHalf")

    def _bar_page(self, url, active, tabs=3, tab_scopes=None, click_writes_hash=True, **view_data):
        """A page whose hash switch lands in the URL, with a period bar of `tabs` tabs.

        `active` is the index of the bold tab: -1 for none, None for a page without a period bar.
        `tab_scopes` gives the scope each tab's click writes into the URL (by tab index); the
        market code is left as it is. `click_writes_hash=False` simulates a click that does not
        change the URL at all.
        """
        page = self._page(url)

        def rewrite_scope(scope):
            base = page.url.rsplit(";", 1)[0]
            return f"{base};{scope}"

        async def evaluate(_js, args):
            if "index" in args:
                if click_writes_hash:
                    page.url = rewrite_scope(tab_scopes[args["index"]])
                return True
            if "fragment" in args:
                page.url = f"https://www.oddsportal.com/x/h2h/a/b/#{args['fragment']}:{args['code']};{args['scope']}"
                return None
            return None if active is None else {"tabs": tabs, "active": active}

        page.evaluate = AsyncMock(side_effect=evaluate)
        serve_view_data(page, **view_data)
        return page

    async def test_already_active_skips_hash_switch(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;3", active=1)

        assert await selector.select_by_scope(page, "football", "FirstHalf") is True

        page.evaluate.assert_awaited_once()
        assert "fragment" not in page.evaluate.await_args.args[1]

    async def test_switches_scope_via_hash(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:over-under;2", active=1)

        assert await selector.select_by_scope(page, "football", "FirstHalf") is True

        assert page.evaluate.await_args_list[0].args[1] == {
            "fragment": "id1",
            "code": "over-under",
            "scope": 3,
            "tabs": OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR,
            "stale": STALE_TAB_ATTRIBUTE,
        }

    async def test_a_period_switch_waits_for_the_view_it_renders(self, selector):
        """R11: the scope is read once the view of the new scope rendered, at most MARKET_SWITCH_WAIT_TIME_MS."""
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:over-under;2", active=1)

        assert await selector.select_by_scope(page, "football", "FirstHalf") is True

        assert page.wait_for_function.await_args_list[0] == call(
            FRESH_VIEW_JS,
            arg=page.evaluate.await_args_list[0].args[1],
            timeout=MARKET_SWITCH_WAIT_TIME_MS,
            polling=SIGNAL_POLL_MS,
        )
        page.wait_for_timeout.assert_not_awaited()

    async def test_each_period_tab_click_waits_for_that_tab_shown_active(self, selector):
        """R12: tab 2 is read within FALLBACK_VERIFY_WAIT_MS, tab 1 within MARKET_SWITCH_WAIT_TIME_MS, as they slept."""
        page = self._bar_page(
            "https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2", active=0, tabs=3, tab_scopes=[2, 3, 17]
        )

        assert await selector.select_by_scope(page, "baseball", "FullTime") is True

        waits = [
            (call.args[0], call.kwargs["arg"]["index"], call.kwargs["timeout"])
            for call in page.wait_for_function.await_args_list
        ]
        assert waits == [
            (_PERIOD_TAB_ACTIVE_JS, 1, FALLBACK_VERIFY_WAIT_MS),
            (_PERIOD_TAB_ACTIVE_JS, 0, MARKET_SWITCH_WAIT_TIME_MS),
        ]
        page.wait_for_timeout.assert_not_awaited()

    async def test_period_tabs_never_shown_active_warn_and_the_url_is_read_as_before(self, selector, caplog):
        page = self._bar_page(
            "https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2", active=0, tabs=3, tab_scopes=[2, 3, 17]
        )
        page.wait_for_function = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout exceeded."))

        with caplog.at_level("WARNING"):
            assert await selector.select_by_scope(page, "baseball", "FullTime") is True

        assert "No period tab 2 shown active within 1000 ms" in caplog.text
        assert "No period tab 1 shown active within 3000 ms" in caplog.text

    async def test_a_period_the_match_lacks_is_refused(self, selector, caplog):
        """NFL 2nd Half forced into the URL: the page keeps its first tab, FT including OT, active."""
        page = self._bar_page(
            "https://www.oddsportal.com/x/h2h/a/b/#id1:home-away;1", active=0, tabs=6, tab_scopes=[1, 3]
        )

        with caplog.at_level("WARNING"):
            assert await selector.select_by_scope(page, "american-football", "SecondHalf") is False

        assert "the page still shows its first period tab, so the match has no such period" in caplog.text

    async def test_a_period_the_match_has_is_selected(self, selector):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:home-away;1", active=2, tabs=6)

        assert await selector.select_by_scope(page, "american-football", "FirstQuarter") is True

    async def test_a_scope_already_in_the_url_is_checked_on_screen_too(self, selector):
        """Baseball Full Time left in the URL by an earlier market: the page still shows FT including OT."""
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:over-under;2", active=0, tab_scopes=[1, 3, 17])

        assert await selector.select_by_scope(page, "baseball", "FullTime") is False

        assert page.evaluate.await_count == 3

    async def test_a_first_tab_period_is_selected_by_the_scope_its_tab_writes(self, selector):
        page = self._bar_page(
            "https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;2", active=0, tabs=3, tab_scopes=[2, 3, 17]
        )

        assert await selector.select_by_scope(page, "baseball", "FullTime") is True

        click_calls = [call.args[1] for call in page.evaluate.await_args_list if "index" in call.args[1]]
        assert [call["index"] for call in click_calls] == [1, 0]

    async def test_a_first_tab_of_another_period_is_refused(self, selector, caplog):
        page = self._bar_page("https://www.oddsportal.com/x/h2h/a/b/#id1:home-away;2", active=0, tab_scopes=[1, 3, 17])

        with caplog.at_level("WARNING"):
            assert await selector.select_by_scope(page, "baseball", "FullTime") is False

        assert "the page still shows its first period tab" in caplog.text

    async def test_a_first_tab_whose_clicks_do_not_change_the_url_is_refused(self, selector, caplog):
        page = self._bar_page(
            "https://www.oddsportal.com/x/h2h/a/b/#id1:home-away;2",
            active=0,
            tab_scopes=[2, 3, 17],
            click_writes_hash=False,
        )

        with caplog.at_level("WARNING"):
            assert await selector.select_by_scope(page, "baseball", "FullTime") is False

        assert "clicking its period tabs did not change the URL" in caplog.text

    async def test_a_period_bar_error_is_refused(self, selector, caplog):
        page = self._page("https://www.oddsportal.com/x/h2h/a/b/#id1:1X2;3")
        page.evaluate = AsyncMock(side_effect=RuntimeError("boom"))

        with caplog.at_level("WARNING"):
            assert await selector.select_by_scope(page, "football", "FirstHalf") is False

        assert "reading the period bar failed" in caplog.text

    async def test_an_in_play_page_is_left_to_the_label_path(self, selector):
        page = self._page("https://www.oddsportal.com/basketball/h2h/a/b/inplay-odds/#id1:home-away;2")

        assert await selector.select_by_scope(page, "basketball", "FullIncludingOT") is None

        page.evaluate.assert_not_awaited()

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
