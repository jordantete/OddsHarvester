from unittest.mock import AsyncMock, MagicMock

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import pytest

from oddsharvester.core.browser.waits import SIGNAL_POLL_MS, wait_for_element, wait_for_signal


async def test_a_signal_that_shows_returns_its_handle_without_a_warning(caplog):
    handle = MagicMock()
    page = MagicMock(wait_for_function=AsyncMock(return_value=handle))

    with caplog.at_level("WARNING"):
        assert await wait_for_signal(page, "() => true", 1500, "test signal", arg={"a": 1}) is handle

    page.wait_for_function.assert_awaited_once_with("() => true", arg={"a": 1}, timeout=1500, polling=SIGNAL_POLL_MS)
    assert caplog.text == ""


async def test_a_signal_missing_at_its_cap_returns_none_with_a_warning(caplog):
    page = MagicMock(wait_for_function=AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 1500ms exceeded.")))

    with caplog.at_level("WARNING"):
        assert await wait_for_signal(page, "() => false", 1500, "test signal") is None

    assert "No test signal within 1500 ms; carrying on with the page as it is." in caplog.text


async def test_a_signal_error_other_than_the_cap_propagates():
    page = MagicMock(wait_for_function=AsyncMock(side_effect=RuntimeError("Target closed")))

    with pytest.raises(RuntimeError, match="Target closed"):
        await wait_for_signal(page, "() => true", 1500, "test signal")


async def test_an_element_in_its_state_returns_true_without_a_warning(caplog):
    page = MagicMock(wait_for_selector=AsyncMock())

    with caplog.at_level("WARNING"):
        assert await wait_for_element(page, ".modal", 500, "modal closing", state="hidden") is True

    page.wait_for_selector.assert_awaited_once_with(".modal", state="hidden", timeout=500)
    assert caplog.text == ""


async def test_an_element_missing_at_its_cap_returns_false_with_a_warning(caplog):
    page = MagicMock(wait_for_selector=AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 500ms exceeded.")))

    with caplog.at_level("WARNING"):
        assert await wait_for_element(page, ".options a", 500, "format options") is False

    page.wait_for_selector.assert_awaited_once_with(".options a", state="visible", timeout=500)
    assert "No format options within 500 ms; carrying on with the page as it is." in caplog.text
