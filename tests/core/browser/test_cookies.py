import logging
from unittest.mock import AsyncMock

import pytest

from oddsharvester.core.browser.cookies import CookieDismisser


class TestCookieDismisser:
    @pytest.fixture
    def dismisser(self):
        return CookieDismisser()

    @pytest.mark.asyncio
    async def test_dismiss_cookie_banner_success(self, dismisser, mock_page):
        """Test successful cookie banner dismissal."""
        # Mock successful banner dismissal
        mock_page.wait_for_selector = AsyncMock()
        mock_page.click = AsyncMock()

        result = await dismisser.dismiss(mock_page)
        assert result is True
        mock_page.wait_for_selector.assert_called_once()
        mock_page.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_dismiss_cookie_banner_custom_selector(self, dismisser, mock_page):
        """Test cookie banner dismissal with custom selector."""
        custom_selector = "#custom-cookie-banner"
        mock_page.wait_for_selector = AsyncMock()
        mock_page.click = AsyncMock()

        result = await dismisser.dismiss(mock_page, selector=custom_selector)
        assert result is True
        mock_page.wait_for_selector.assert_called_with(custom_selector, timeout=10000)

    @pytest.mark.asyncio
    async def test_dismiss_cookie_banner_timeout_error(self, dismisser, mock_page):
        """Test cookie banner dismissal when banner is not found (timeout)."""
        mock_page.wait_for_selector.side_effect = TimeoutError("Timeout")

        result = await dismisser.dismiss(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_dismiss_cookie_banner_click_error(self, dismisser, mock_page):
        """Test cookie banner dismissal when click fails."""
        mock_page.wait_for_selector = AsyncMock()
        mock_page.click.side_effect = Exception("Click failed")

        result = await dismisser.dismiss(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_dismiss_cookie_banner_wait_error(self, dismisser, mock_page):
        """Test cookie banner dismissal when wait_for_selector fails."""
        mock_page.wait_for_selector.side_effect = Exception("Wait failed")

        result = await dismisser.dismiss(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_logging_during_cookie_banner_dismissal(self, dismisser, mock_page, caplog):
        """Test logging during cookie banner dismissal."""
        with caplog.at_level(logging.INFO):
            mock_page.wait_for_selector = AsyncMock()
            mock_page.click = AsyncMock()

            await dismisser.dismiss(mock_page)

            assert "Checking for cookie banner" in caplog.text
            assert "Cookie banner found. Dismissing it." in caplog.text

    @pytest.mark.asyncio
    async def test_full_cookie_banner_flow(self, dismisser, mock_page):
        """Test the complete cookie banner dismissal flow."""
        # Mock successful cookie banner dismissal
        mock_page.wait_for_selector = AsyncMock()
        mock_page.click = AsyncMock()

        result = await dismisser.dismiss(mock_page, timeout=5000)
        assert result is True
        mock_page.wait_for_selector.assert_called_once()
        mock_page.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_a_second_page_of_the_same_context_does_not_wait_again(self, dismisser, mock_page):
        """Consent is context state, so the banner cannot come back on a later page."""
        mock_page.wait_for_selector = AsyncMock()
        mock_page.click = AsyncMock()
        later_page = AsyncMock()
        later_page.context = mock_page.context

        assert await dismisser.dismiss(mock_page) is True
        assert await dismisser.dismiss(later_page) is True

        mock_page.wait_for_selector.assert_called_once()
        later_page.wait_for_selector.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_page_from_another_context_is_still_checked(self, dismisser, mock_page):
        """Multi-proxy runs hold one context per proxy, each needing its own consent."""
        mock_page.wait_for_selector = AsyncMock()
        mock_page.click = AsyncMock()
        other_context_page = AsyncMock()

        await dismisser.dismiss(mock_page)
        await dismisser.dismiss(other_context_page)

        other_context_page.wait_for_selector.assert_called_once()

    @pytest.mark.asyncio
    async def test_an_absent_banner_is_not_remembered(self, dismisser, mock_page):
        """A banner rendering late must still be caught, so only a success is cached."""
        mock_page.wait_for_selector.side_effect = TimeoutError("Timeout")

        assert await dismisser.dismiss(mock_page) is False
        assert await dismisser.dismiss(mock_page) is False

        assert mock_page.wait_for_selector.call_count == 2
