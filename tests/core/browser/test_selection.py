from unittest.mock import AsyncMock, MagicMock

import pytest

from oddsharvester.core.browser.selection import (
    BOOKIES_FILTER_STRATEGY,
    PERIOD_STRATEGY,
    PeriodSelector,
    SelectionManager,
)

STRATEGIES = [
    pytest.param(BOOKIES_FILTER_STRATEGY, "all-bookies", "All bookies", id="bookies"),
    pytest.param(PERIOD_STRATEGY, "Full Time", "Full Time", id="period"),
]


def _make_active_elem(strategy, returned_value):
    """Build a mock active element that returns `returned_value` for the strategy's read mode."""
    elem = AsyncMock()
    if strategy is BOOKIES_FILTER_STRATEGY:
        elem.get_attribute = AsyncMock(return_value=returned_value)
    else:
        elem.text_content = AsyncMock(return_value=returned_value)
    return elem


class TestSelectionManager:
    @pytest.fixture
    def manager(self):
        return SelectionManager()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGIES)
    async def test_returns_false_when_container_absent(self, manager, mock_page, strategy, target_value, display_label):
        mock_page.query_selector = AsyncMock(return_value=None)
        result = await manager.ensure_selected(mock_page, target_value, display_label, strategy)
        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGIES)
    async def test_returns_true_noop_when_already_active(
        self, manager, mock_page, strategy, target_value, display_label
    ):
        active_elem = _make_active_elem(strategy, target_value)
        mock_page.query_selector = AsyncMock(
            side_effect=[
                MagicMock(),  # container present
                active_elem,  # active value lookup
            ]
        )
        mock_page.click = AsyncMock()
        result = await manager.ensure_selected(mock_page, target_value, display_label, strategy)
        assert result is True
        mock_page.click.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGIES)
    async def test_returns_true_when_click_and_wait_succeed(
        self, manager, mock_page, strategy, target_value, display_label
    ):
        # Active element returns a different value than target → click required
        active_elem = _make_active_elem(strategy, "different-value")

        click_target = AsyncMock()
        click_target.click = AsyncMock()

        mock_page.query_selector = AsyncMock(
            side_effect=[
                MagicMock(),  # container present
                active_elem,  # current value lookup
                click_target,  # the option to click
            ]
        )
        mock_page.wait_for_function = AsyncMock()  # success

        result = await manager.ensure_selected(mock_page, target_value, display_label, strategy)
        assert result is True
        click_target.click.assert_awaited_once()
        mock_page.wait_for_function.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGIES)
    async def test_fallback_verify_succeeds(self, manager, mock_page, strategy, target_value, display_label):
        active_old = _make_active_elem(strategy, "different-value")
        active_new = _make_active_elem(strategy, target_value)

        click_target = AsyncMock()
        click_target.click = AsyncMock()

        mock_page.query_selector = AsyncMock(
            side_effect=[
                MagicMock(),  # container
                active_old,  # initial current
                click_target,  # click target
                active_new,  # fallback verify (re-read active)
            ]
        )
        mock_page.wait_for_function = AsyncMock(side_effect=Exception("timeout"))
        mock_page.wait_for_timeout = AsyncMock()

        result = await manager.ensure_selected(mock_page, target_value, display_label, strategy)
        assert result is True

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("strategy", "target_value", "display_label"), STRATEGIES)
    async def test_fallback_verify_fails(self, manager, mock_page, strategy, target_value, display_label):
        active_old = _make_active_elem(strategy, "different-value")
        active_still_wrong = _make_active_elem(strategy, "still-wrong")

        click_target = AsyncMock()
        click_target.click = AsyncMock()

        mock_page.query_selector = AsyncMock(
            side_effect=[
                MagicMock(),
                active_old,
                click_target,
                active_still_wrong,
            ]
        )
        mock_page.wait_for_function = AsyncMock(side_effect=Exception("timeout"))
        mock_page.wait_for_timeout = AsyncMock()

        result = await manager.ensure_selected(mock_page, target_value, display_label, strategy)
        assert result is False

    @pytest.mark.asyncio
    async def test_target_value_with_quote_does_not_break_js_predicate(self, manager, mock_page):
        """Regression: target_value containing a single quote must be passed via arg=, not interpolated into JS."""
        target_value = "o'reilly's"
        display_label = "O'Reilly's"

        active_elem = _make_active_elem(BOOKIES_FILTER_STRATEGY, "different")
        click_target = AsyncMock()
        click_target.click = AsyncMock()

        mock_page.query_selector = AsyncMock(side_effect=[MagicMock(), active_elem, click_target])
        mock_page.wait_for_function = AsyncMock()

        result = await manager.ensure_selected(mock_page, target_value, display_label, BOOKIES_FILTER_STRATEGY)
        assert result is True

        call_args = mock_page.wait_for_function.await_args
        # The first positional arg is the JS predicate string
        js_predicate = call_args.args[0] if call_args.args else call_args.kwargs.get("expression")
        assert "o'reilly" not in js_predicate, "target_value must not be interpolated into the JS string"

        arg_payload = call_args.kwargs.get("arg")
        assert arg_payload is not None
        assert arg_payload["targetValue"] == target_value


class TestPeriodSelector:
    """Language-independent period selection via the URL-fragment scope code."""

    @pytest.fixture
    def selector(self):
        return PeriodSelector()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_scope_code(self, selector, mock_page):
        """Unknown (sport, period) -> None so the caller falls back to label matching."""
        result = await selector.select_by_scope(mock_page, sport="basketball", internal_period="FirstQuarter")
        assert result is None

    @pytest.mark.asyncio
    async def test_already_active_skips_click(self, selector, mock_page):
        """FullTime is the default scope (2); no tab click needed."""
        mock_page.url = "https://x/#abcd:over-under;2"
        mock_page.query_selector_all = AsyncMock()
        result = await selector.select_by_scope(mock_page, sport="tennis", internal_period="FullTime")
        assert result is True
        mock_page.query_selector_all.assert_not_called()

    @pytest.mark.asyncio
    async def test_clicks_tab_until_target_scope_active(self, selector, mock_page):
        """Click period tabs and read the resulting fragment scope until it matches."""
        # Start on FullTime (scope 2); target is 1st Set (scope 12).
        urls = iter(
            [
                "https://x/#abcd:over-under;2",  # initial read
                "https://x/#abcd:over-under;12",  # after clicking tab[0]
            ]
        )

        tab0 = AsyncMock()
        tab1 = AsyncMock()

        def url_getter():
            return next(urls)

        type(mock_page).url = property(lambda self: url_getter())
        mock_page.query_selector_all = AsyncMock(return_value=[tab0, tab1])
        mock_page.wait_for_timeout = AsyncMock()

        result = await selector.select_by_scope(mock_page, sport="tennis", internal_period="FirstSet")
        assert result is True
        tab0.click.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_target_scope_never_reached(self, selector, mock_page):
        """If no tab yields the target scope, return False (never select a wrong period)."""
        type(mock_page).url = property(lambda self: "https://x/#abcd:over-under;2")
        tab0 = AsyncMock()
        mock_page.query_selector_all = AsyncMock(return_value=[tab0])
        mock_page.wait_for_timeout = AsyncMock()

        result = await selector.select_by_scope(mock_page, sport="tennis", internal_period="FirstSet")
        assert result is False
