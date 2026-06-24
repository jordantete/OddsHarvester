from unittest.mock import AsyncMock, MagicMock

import pytest

from oddsharvester.core.browser.market_navigation import MarketTabNavigator
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.market_extraction.navigation_manager import NavigationManager
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_navigate_to_market_tab_failure(self, navigation_manager, page_mock, tab_navigator_mock):
        """Test failed navigation to a market tab."""
        # Arrange
        tab_navigator_mock.navigate_to_tab = AsyncMock(return_value=False)
        market_tab_name = "NonExistentMarket"

        # Act
        result = await navigation_manager.navigate_to_market_tab(page_mock, market_tab_name)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_market_switch_success(self, navigation_manager, page_mock):
        """Test successful market switch wait."""
        # Arrange
        market_name = "Over/Under"
        mock_active_tab = AsyncMock()
        mock_active_tab.text_content = AsyncMock(return_value="Over/Under")
        page_mock.query_selector = AsyncMock(return_value=mock_active_tab)

        # Act
        result = await navigation_manager.wait_for_market_switch(page_mock, market_name)

        # Assert
        assert result is True
        page_mock.wait_for_timeout.assert_called_with(MARKET_SWITCH_WAIT_TIME_MS)

    @pytest.mark.asyncio
    async def test_wait_for_market_switch_wrong_market(self, navigation_manager, page_mock):
        """Test market switch wait with wrong market name."""
        # Arrange
        market_name = "Over/Under"
        mock_active_tab = AsyncMock()
        mock_active_tab.text_content = AsyncMock(return_value="1X2")
        page_mock.query_selector = AsyncMock(return_value=mock_active_tab)

        # Act
        result = await navigation_manager.wait_for_market_switch(page_mock, market_name)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_market_switch_no_active_tab(self, navigation_manager, page_mock):
        """Test market switch wait when no active tab is found."""
        # Arrange
        market_name = "Over/Under"
        page_mock.query_selector = AsyncMock(return_value=None)

        # Act
        result = await navigation_manager.wait_for_market_switch(page_mock, market_name)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_market_switch_exception_handling(self, navigation_manager, page_mock):
        """Test market switch wait with exception handling."""
        # Arrange
        market_name = "Over/Under"
        page_mock.query_selector = AsyncMock(side_effect=Exception("Test exception"))

        # Act
        result = await navigation_manager.wait_for_market_switch(page_mock, market_name)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_select_specific_market_success(self, navigation_manager, page_mock, scroller_mock):
        """Test successful selection of a specific market."""
        # Arrange
        scroller_mock.scroll_until_visible_and_click_parent = AsyncMock(return_value=True)
        specific_market = "Over/Under 2.5"

        # Act
        result = await navigation_manager.select_specific_market(page_mock, specific_market)

        # Assert
        assert result is True
        scroller_mock.scroll_until_visible_and_click_parent.assert_called_once_with(
            page=page_mock,
            selector="div.flex.w-full.items-center.justify-start.pl-3.font-bold p",
            text=specific_market,
        )

    @pytest.mark.asyncio
    async def test_select_specific_market_matches_language_independent_tail(
        self, navigation_manager, page_mock, scroller_mock
    ):
        """On localized mirrors, match only the untranslated tail (issue #70 follow-up)."""
        # Arrange
        scroller_mock.scroll_until_visible_and_click_parent = AsyncMock(return_value=True)

        # Act
        result = await navigation_manager.select_specific_market(
            page_mock, specific_market="Over/Under +20.5 Games", main_market="Over/Under"
        )

        # Assert
        assert result is True
        scroller_mock.scroll_until_visible_and_click_parent.assert_called_once_with(
            page=page_mock,
            selector="div.flex.w-full.items-center.justify-start.pl-3.font-bold p",
            text="+20.5 Games",
        )

    @pytest.mark.asyncio
    async def test_select_specific_market_failure(self, navigation_manager, page_mock, scroller_mock):
        """Test failed selection of a specific market."""
        # Arrange
        scroller_mock.scroll_until_visible_and_click_parent = AsyncMock(return_value=False)
        specific_market = "NonExistentMarket"

        # Act
        result = await navigation_manager.select_specific_market(page_mock, specific_market)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_close_specific_market_success(self, navigation_manager, page_mock, scroller_mock):
        """Test successful closing of a specific market."""
        # Arrange
        scroller_mock.scroll_until_visible_and_click_parent = AsyncMock(return_value=True)
        specific_market = "Over/Under 2.5"

        # Act
        result = await navigation_manager.close_specific_market(page_mock, specific_market)

        # Assert
        assert result is True
        scroller_mock.scroll_until_visible_and_click_parent.assert_called_once_with(
            page=page_mock,
            selector="div.flex.w-full.items-center.justify-start.pl-3.font-bold p",
            text=specific_market,
        )

    @pytest.mark.asyncio
    async def test_close_specific_market_matches_language_independent_tail(
        self, navigation_manager, page_mock, scroller_mock
    ):
        """Closing a submarket must also use the untranslated tail on mirrors."""
        # Arrange
        scroller_mock.scroll_until_visible_and_click_parent = AsyncMock(return_value=True)

        # Act
        result = await navigation_manager.close_specific_market(
            page_mock, specific_market="Over/Under +20.5 Games", main_market="Over/Under"
        )

        # Assert
        assert result is True
        scroller_mock.scroll_until_visible_and_click_parent.assert_called_once_with(
            page=page_mock,
            selector="div.flex.w-full.items-center.justify-start.pl-3.font-bold p",
            text="+20.5 Games",
        )

    @pytest.mark.asyncio
    async def test_close_specific_market_failure(self, navigation_manager, page_mock, scroller_mock):
        """Test failed closing of a specific market."""
        # Arrange
        scroller_mock.scroll_until_visible_and_click_parent = AsyncMock(return_value=False)
        specific_market = "NonExistentMarket"

        # Act
        result = await navigation_manager.close_specific_market(page_mock, specific_market)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_page_load(self, navigation_manager, page_mock):
        """Test waiting for page load."""
        # Act
        await navigation_manager.wait_for_page_load(page_mock)

        # Assert
        page_mock.wait_for_timeout.assert_called_once_with(SCROLL_PAUSE_TIME_MS)

    def test_constants(self):
        """Test that centralized constants have expected values."""
        assert DEFAULT_MARKET_TIMEOUT_MS == 5000
        assert SCROLL_PAUSE_TIME_MS == 2000
        assert MARKET_SWITCH_WAIT_TIME_MS == 3000
