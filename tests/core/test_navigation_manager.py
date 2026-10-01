from unittest.mock import AsyncMock, MagicMock

import pytest

from oddsharvester.core.browser.market_navigation import MarketTabNavigator
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.market_extraction.navigation_manager import NavigationManager
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import DEFAULT_MARKET_TIMEOUT_MS, MARKET_SWITCH_WAIT_TIME_MS, SCROLL_PAUSE_TIME_MS


class TestNavigationManager:
    """Unit tests for the NavigationManager class."""

    @pytest.fixture
    def tab_navigator_mock(self):
        """Create a mock for MarketTabNavigator."""
        return MagicMock(spec=MarketTabNavigator)

    @pytest.fixture
    def scroller_mock(self):
        """Create a mock for PageScroller."""
        return MagicMock(spec=PageScroller)

    @pytest.fixture
    def navigation_manager(self, tab_navigator_mock, scroller_mock):
        """Create an instance of NavigationManager with mocked dependencies."""
        return NavigationManager(tab_navigator_mock, scroller_mock)

    @pytest.fixture
    def page_mock(self):
        """Create a mock for the Playwright page."""
        mock = AsyncMock()
        mock.wait_for_timeout = AsyncMock()
        return mock

    async def test_navigate_to_market_tab_success(self, navigation_manager, page_mock, tab_navigator_mock):
        """Test successful navigation to a market tab."""
        # Arrange
        tab_navigator_mock.navigate_to_tab = AsyncMock(return_value=True)
        market_tab_name = "1X2"

        # Act
        result = await navigation_manager.navigate_to_market_tab(page_mock, market_tab_name)

        # Assert
        assert result is True
        tab_navigator_mock.navigate_to_tab.assert_called_once_with(
            page=page_mock, market_tab_name=market_tab_name, timeout=DEFAULT_MARKET_TIMEOUT_MS
        )

    async def test_navigate_to_market_tab_failure(self, navigation_manager, page_mock, tab_navigator_mock):
        """Test failed navigation to a market tab."""
        # Arrange
        tab_navigator_mock.navigate_to_tab = AsyncMock(return_value=False)
        market_tab_name = "NonExistentMarket"

        # Act
        result = await navigation_manager.navigate_to_market_tab(page_mock, market_tab_name)

        # Assert
        assert result is False

    @staticmethod
    def _row(page, line):
        return {
            "page": page,
            "selector": OddsPortalSelectors.SUB_MARKET_SELECTOR,
            "line": line,
            "click_ancestor": OddsPortalSelectors.SUB_MARKET_CLICK_ANCESTOR,
        }

    @pytest.mark.parametrize(
        ("specific_market", "main_market", "line"),
        [("Over/Under 2.5", None, "Over/Under 2.5"), ("Over/Under +20.5 Games", "Over/Under", "+20.5 Games")],
        ids=["full-label", "language-independent-tail"],
    )
    async def test_select_specific_market_opens_the_row_and_waits_for_its_bookmakers(
        self, navigation_manager, page_mock, scroller_mock, specific_market, main_market, line
    ):
        """On localized mirrors only the untranslated tail is matched (issue #70 follow-up)."""
        scroller_mock.click_line_row = AsyncMock(return_value=True)
        scroller_mock.wait_for_line_bookmakers = AsyncMock(return_value=True)

        assert await navigation_manager.select_specific_market(page_mock, specific_market, main_market) is True

        scroller_mock.click_line_row.assert_awaited_once_with(**self._row(page_mock, line))
        scroller_mock.wait_for_line_bookmakers.assert_awaited_once_with(**self._row(page_mock, line), shown=True)

    async def test_select_specific_market_reads_on_when_the_bookmakers_never_show(
        self, navigation_manager, page_mock, scroller_mock
    ):
        scroller_mock.click_line_row = AsyncMock(return_value=True)
        scroller_mock.wait_for_line_bookmakers = AsyncMock(return_value=False)

        assert await navigation_manager.select_specific_market(page_mock, "Over/Under +2.25", "Over/Under") is True

    async def test_select_specific_market_failure(self, navigation_manager, page_mock, scroller_mock):
        scroller_mock.click_line_row = AsyncMock(return_value=False)
        scroller_mock.wait_for_line_bookmakers = AsyncMock()

        assert await navigation_manager.select_specific_market(page_mock, "NonExistentMarket") is False

        scroller_mock.wait_for_line_bookmakers.assert_not_awaited()

    @pytest.mark.parametrize(
        ("specific_market", "main_market", "line"),
        [("Over/Under 2.5", None, "Over/Under 2.5"), ("Over/Under +20.5 Games", "Over/Under", "+20.5 Games")],
        ids=["full-label", "language-independent-tail"],
    )
    async def test_close_specific_market_closes_the_row_and_waits_for_its_bookmakers_to_go(
        self, navigation_manager, page_mock, scroller_mock, specific_market, main_market, line
    ):
        """The next line of an umbrella is read on the same view: this line's rows must be gone first."""
        scroller_mock.click_line_row = AsyncMock(return_value=True)
        scroller_mock.wait_for_line_bookmakers = AsyncMock(return_value=True)

        assert await navigation_manager.close_specific_market(page_mock, specific_market, main_market) is True

        scroller_mock.click_line_row.assert_awaited_once_with(**self._row(page_mock, line))
        scroller_mock.wait_for_line_bookmakers.assert_awaited_once_with(**self._row(page_mock, line), shown=False)

    async def test_close_specific_market_failure(self, navigation_manager, page_mock, scroller_mock):
        scroller_mock.click_line_row = AsyncMock(return_value=False)
        scroller_mock.wait_for_line_bookmakers = AsyncMock()

        assert await navigation_manager.close_specific_market(page_mock, "NonExistentMarket") is False

        scroller_mock.wait_for_line_bookmakers.assert_not_awaited()

    def test_constants(self):
        """Test that centralized constants have expected values."""
        assert DEFAULT_MARKET_TIMEOUT_MS == 5000
        assert SCROLL_PAUSE_TIME_MS == 2000
        assert MARKET_SWITCH_WAIT_TIME_MS == 3000
