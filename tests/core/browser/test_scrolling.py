import logging
from unittest.mock import AsyncMock

import pytest

from oddsharvester.core.browser.scrolling import PageScroller


class TestPageScroller:
    @pytest.fixture
    def scroller(self):
        return PageScroller()

    @pytest.mark.asyncio
    async def test_scroll_until_loaded_success_with_selector(self, scroller, mock_page):
        """Test successful scrolling with content selector."""
        # Mock page evaluation and element counting
        mock_page.evaluate.return_value = 1000  # Same height for all calls
        mock_page.query_selector_all.return_value = [AsyncMock()] * 5  # 5 elements
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(
            mock_page, timeout=1, scroll_pause_time=0.1, max_scroll_attempts=2, content_check_selector=".test-element"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_scroll_until_loaded_success_height_based(self, scroller, mock_page):
        """Test successful scrolling with height-based detection."""
        # Mock page evaluation with changing height then stable
        mock_page.evaluate.return_value = 1200  # Stable height
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(mock_page, timeout=1, scroll_pause_time=0.1, max_scroll_attempts=2)
        assert result is True

    @pytest.mark.asyncio
    async def test_scroll_until_loaded_timeout(self, scroller, mock_page):
        """Test scrolling that times out."""
        # Mock page evaluation with changing height (never stabilizes)
        mock_page.evaluate.return_value = 1000  # Stable height but short timeout

        # Mock a longer wait time to ensure timeout is reached
        async def slow_wait(*args, **kwargs):
            import asyncio

            await asyncio.sleep(0.1)  # Simulate slow operation

        mock_page.wait_for_timeout = slow_wait

        result = await scroller.scroll_until_loaded(
            mock_page,
            timeout=0.01,  # Short timeout
            scroll_pause_time=0.1,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_scroll_until_loaded_with_changing_content(self, scroller, mock_page):
        """Test scrolling with content that keeps changing."""
        # Mock page evaluation and changing element count
        mock_page.evaluate.return_value = 1000  # Same height
        mock_page.query_selector_all.return_value = [AsyncMock()] * 7  # 7 elements (stable)
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(
            mock_page, timeout=1, scroll_pause_time=0.1, max_scroll_attempts=2, content_check_selector=".test-element"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_scroll_until_visible_and_click_parent_success_with_text(self, scroller, mock_page):
        """Test successful scroll and click with text matching."""
        # Mock element with matching text and bounding box
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "Target Text"
        mock_element.bounding_box.return_value = {"x": 0, "y": 0, "width": 100, "height": 50}
        mock_element.evaluate_handle.return_value = AsyncMock()

        mock_page.query_selector_all.return_value = [mock_element]
        mock_page.evaluate = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_visible_and_click_parent(
            mock_page, "test-selector", "Target Text", timeout=1, scroll_pause_time=0.1
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_scroll_until_visible_and_click_parent_success_without_text(self, scroller, mock_page):
        """Test successful scroll and click without text matching."""
        # Mock element with bounding box
        mock_element = AsyncMock()
        mock_element.bounding_box.return_value = {"x": 0, "y": 0, "width": 100, "height": 50}
        mock_element.evaluate_handle.return_value = AsyncMock()

        mock_page.query_selector_all.return_value = [mock_element]
        mock_page.evaluate = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_visible_and_click_parent(
            mock_page, "test-selector", timeout=1, scroll_pause_time=0.1
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_scroll_until_visible_and_click_parent_no_bounding_box(self, scroller, mock_page):
        """Test scroll and click when element has no bounding box."""
        # Mock element without bounding box
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "Target Text"
        mock_element.bounding_box.return_value = None

        mock_page.query_selector_all.return_value = [mock_element]
        mock_page.evaluate = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_visible_and_click_parent(
            mock_page, "test-selector", "Target Text", timeout=1, scroll_pause_time=0.1
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_scroll_until_visible_and_click_parent_timeout(self, scroller, mock_page):
        """Test scroll and click that times out."""
        # Mock no elements found
        mock_page.query_selector_all.return_value = []
        mock_page.evaluate = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_visible_and_click_parent(
            mock_page, "test-selector", "Target Text", timeout=0.1, scroll_pause_time=0.1
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_scroll_until_visible_and_click_parent_text_not_found(self, scroller, mock_page):
        """Test scroll and click when text is not found."""
        # Mock element with different text
        mock_element = AsyncMock()
        mock_element.text_content.return_value = "Different Text"

        mock_page.query_selector_all.return_value = [mock_element]
        mock_page.evaluate = AsyncMock()
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_visible_and_click_parent(
            mock_page, "test-selector", "Target Text", timeout=0.1, scroll_pause_time=0.1
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_scroll_until_loaded_zero_timeout(self, scroller, mock_page):
        """Test scrolling with zero timeout."""
        mock_page.evaluate.return_value = 1000
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(mock_page, timeout=0)
        assert result is False

    @pytest.mark.asyncio
    async def test_scroll_until_loaded_negative_timeout(self, scroller, mock_page):
        """Test scrolling with negative timeout."""
        mock_page.evaluate.return_value = 1000
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(mock_page, timeout=-1)
        assert result is False

    @pytest.mark.asyncio
    async def test_scroll_until_visible_and_click_parent_empty_selector(self, scroller, mock_page):
        """Test scroll and click with empty selector."""
        result = await scroller.scroll_until_visible_and_click_parent(mock_page, "", "test-text", timeout=0.1)
        assert result is False

    @pytest.mark.asyncio
    async def test_scroll_until_visible_and_click_parent_none_selector(self, scroller, mock_page):
        """Test scroll and click with None selector."""
        result = await scroller.scroll_until_visible_and_click_parent(mock_page, None, "test-text", timeout=0.1)
        assert result is False

    @pytest.mark.asyncio
    async def test_logging_during_scrolling(self, scroller, mock_page, caplog):
        """Test logging during scrolling operations."""
        with caplog.at_level(logging.INFO):
            mock_page.evaluate.return_value = 1000
            mock_page.wait_for_timeout = AsyncMock()

            await scroller.scroll_until_loaded(mock_page, timeout=0.1)

            assert "Will scroll to the bottom of the page" in caplog.text
            # The test might complete before timeout, so check for either completion or timeout
            assert any(msg in caplog.text for msg in ["Page height stabilized", "Reached scrolling timeout"])

    @pytest.mark.asyncio
    async def test_full_scrolling_flow(self, scroller, mock_page):
        """Test the complete scrolling flow."""
        # Mock successful scrolling
        mock_page.evaluate.return_value = 1000  # Stable height
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(mock_page, timeout=1, scroll_pause_time=0.1, max_scroll_attempts=2)
        assert result is True


def test_listing_scroll_pace_matches_what_the_listings_always_used():
    """E1: the three listings passed 2 s / 3 attempts in-line; the constants now carry those values."""
    from oddsharvester.utils.constants import MAX_SCROLL_ATTEMPTS, SCROLL_PAUSE_S

    assert (SCROLL_PAUSE_S, MAX_SCROLL_ATTEMPTS) == (2, 3)
