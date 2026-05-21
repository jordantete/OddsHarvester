from unittest.mock import AsyncMock, patch

import pytest

from oddsharvester.core.playwright_manager import PlaywrightManager


@pytest.fixture
def mock_playwright():
    """Mock async_playwright with browser/context/page chain."""
    with patch("oddsharvester.core.playwright_manager.async_playwright") as mock_ap:
        playwright = AsyncMock()
        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()

        mock_ap.return_value.start = AsyncMock(return_value=playwright)
        playwright.chromium.launch = AsyncMock(return_value=browser)
        browser.new_context = AsyncMock(return_value=context)
        context.new_page = AsyncMock(return_value=page)
        context.add_init_script = AsyncMock()
        context.route_from_har = AsyncMock()
        page.evaluate = AsyncMock(return_value="UTC")

        yield {"playwright": playwright, "browser": browser, "context": context, "page": page}


@pytest.mark.asyncio
async def test_route_from_har_called_when_env_var_set(mock_playwright, monkeypatch, tmp_path):
    har_path = tmp_path / "snapshot.har"
    har_path.write_text("{}")
    monkeypatch.setenv("ODDSHARVESTER_HAR_REPLAY", str(har_path))

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    mock_playwright["context"].route_from_har.assert_awaited_once_with(
        har_path,
        url="**oddsportal.com/**",
        not_found="abort",
    )


@pytest.mark.asyncio
async def test_route_from_har_not_called_when_env_var_unset(mock_playwright, monkeypatch):
    monkeypatch.delenv("ODDSHARVESTER_HAR_REPLAY", raising=False)

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    mock_playwright["context"].route_from_har.assert_not_called()


@pytest.mark.asyncio
async def test_record_har_kwargs_when_record_env_var_set(mock_playwright, monkeypatch, tmp_path):
    har_path = tmp_path / "snapshot.har"
    monkeypatch.setenv("ODDSHARVESTER_HAR_RECORD", str(har_path))

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    mock_playwright["browser"].new_context.assert_awaited_once()
    call_kwargs = mock_playwright["browser"].new_context.await_args.kwargs
    assert call_kwargs["record_har_path"] == har_path
    assert call_kwargs["record_har_mode"] == "full"
    assert call_kwargs["record_har_url_filter"] == "**oddsportal.com/**"


@pytest.mark.asyncio
async def test_record_har_kwargs_absent_when_env_var_unset(mock_playwright, monkeypatch):
    monkeypatch.delenv("ODDSHARVESTER_HAR_RECORD", raising=False)

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    call_kwargs = mock_playwright["browser"].new_context.await_args.kwargs
    assert "record_har_path" not in call_kwargs
    assert "record_har_mode" not in call_kwargs
    assert "record_har_url_filter" not in call_kwargs


@pytest.mark.asyncio
async def test_resolves_system_timezone_when_none_requested(mock_playwright):
    """With no explicit timezone, the effective browser timezone is captured."""
    mock_playwright["page"].evaluate = AsyncMock(return_value="Europe/Paris")

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    assert pm.timezone_id == "Europe/Paris"
    mock_playwright["page"].evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_timezone_is_not_overridden(mock_playwright):
    """An explicit timezone_id is kept as-is and not re-resolved from the page."""
    pm = PlaywrightManager()
    await pm.initialize(headless=True, timezone_id="Asia/Tokyo")

    assert pm.timezone_id == "Asia/Tokyo"
    mock_playwright["page"].evaluate.assert_not_called()


@pytest.mark.asyncio
async def test_timezone_resolution_failure_falls_back_to_utc(mock_playwright):
    """If the timezone probe raises, fall back to UTC rather than crash."""
    mock_playwright["page"].evaluate = AsyncMock(side_effect=RuntimeError("probe failed"))

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    assert pm.timezone_id == "UTC"
