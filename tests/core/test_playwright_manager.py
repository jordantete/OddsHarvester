from unittest.mock import AsyncMock, patch

import pytest

from oddsharvester.core.exceptions import AllProxiesExhaustedError
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.utils.proxy_manager import ProxyManager


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


@pytest.mark.asyncio
async def test_single_context_when_no_proxy_manager(mock_playwright):
    pm = PlaywrightManager()
    await pm.initialize(headless=True)
    mock_playwright["browser"].new_context.assert_awaited_once()
    assert list(pm.contexts.keys()) == ["direct"]
    assert pm.non_default_context_keys() == []


@pytest.mark.asyncio
async def test_one_context_per_proxy_when_multi(mock_playwright):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    # Two contexts created; browser launched with the per-context sentinel.
    assert mock_playwright["browser"].new_context.await_count == 2
    assert set(pm.contexts.keys()) == {"http://a.example.com:1", "http://b.example.com:2"}
    launch_kwargs = mock_playwright["playwright"].chromium.launch.await_args.kwargs
    assert launch_kwargs["proxy"] == {"server": "per-context"}
    assert len(pm.non_default_context_keys()) == 1


@pytest.mark.asyncio
async def test_new_rotated_page_reports_key(mock_playwright):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    _page, key = await pm.new_rotated_page()
    assert key in {"http://a.example.com:1", "http://b.example.com:2"}


@pytest.mark.asyncio
async def test_new_rotated_page_raises_when_exhausted(mock_playwright):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    for key in ["http://a.example.com:1", "http://b.example.com:2"]:
        for _ in range(3):
            pm.report_page_result(key, is_proxy_failure=True)
    with pytest.raises(AllProxiesExhaustedError):
        await pm.new_rotated_page()
