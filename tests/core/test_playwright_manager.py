import logging
from unittest.mock import AsyncMock, patch

import pytest

from oddsharvester.core.browser.view_data import VIEW_DATA_HOOK_JS
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


async def test_route_from_har_not_called_when_env_var_unset(mock_playwright, monkeypatch):
    monkeypatch.delenv("ODDSHARVESTER_HAR_REPLAY", raising=False)

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    mock_playwright["context"].route_from_har.assert_not_called()


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


async def test_record_har_kwargs_absent_when_env_var_unset(mock_playwright, monkeypatch):
    monkeypatch.delenv("ODDSHARVESTER_HAR_RECORD", raising=False)

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    call_kwargs = mock_playwright["browser"].new_context.await_args.kwargs
    assert "record_har_path" not in call_kwargs
    assert "record_har_mode" not in call_kwargs
    assert "record_har_url_filter" not in call_kwargs


async def test_resolves_system_timezone_when_none_requested(mock_playwright):
    """With no explicit timezone, the effective browser timezone is captured."""
    mock_playwright["page"].evaluate = AsyncMock(return_value="Europe/Paris")

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    assert pm.timezone_id == "Europe/Paris"
    assert mock_playwright["page"].evaluate.await_count == 2

    scripts = [call.args[0] for call in mock_playwright["page"].evaluate.await_args_list]
    assert "resolvedOptions().timeZone" in scripts[0]
    assert "formatToParts" in scripts[1]


async def test_explicit_timezone_is_not_overridden(mock_playwright):
    """An explicit timezone_id is kept as-is and not re-resolved from the page."""
    pm = PlaywrightManager()
    await pm.initialize(headless=True, timezone_id="Asia/Tokyo")

    assert pm.timezone_id == "Asia/Tokyo"
    assert mock_playwright["page"].evaluate.await_count == 1

    script = mock_playwright["page"].evaluate.await_args.args[0]
    assert "resolvedOptions().timeZone" not in script
    assert "formatToParts" in script


async def test_collects_browser_month_aliases(mock_playwright):
    """Browser locale month labels are captured without hard-coded languages."""
    mock_playwright["page"].evaluate = AsyncMock(
        return_value=[
            ["LocalizedMonth", 9],
            ["LocalizedMonth.", 9],
            ["AnotherMonth", 10],
        ]
    )

    pm = PlaywrightManager()
    await pm.initialize(
        headless=True,
        timezone_id="UTC",
    )

    assert pm.month_name_to_num == {
        "LocalizedMonth": 9,
        "LocalizedMonth.": 9,
        "AnotherMonth": 10,
    }

    mock_playwright["page"].evaluate.assert_awaited_once()

    script = mock_playwright["page"].evaluate.await_args.args[0]
    assert "Intl.DateTimeFormat" in script
    assert "formatToParts" in script
    assert '"short"' in script
    assert '"long"' in script


async def test_timezone_resolution_failure_falls_back_to_utc(mock_playwright):
    """If the timezone probe raises, fall back to UTC rather than crash."""
    mock_playwright["page"].evaluate = AsyncMock(side_effect=RuntimeError("probe failed"))

    pm = PlaywrightManager()
    await pm.initialize(headless=True)

    assert pm.timezone_id == "UTC"


async def test_single_context_when_no_proxy_manager(mock_playwright):
    pm = PlaywrightManager()
    await pm.initialize(headless=True)
    mock_playwright["browser"].new_context.assert_awaited_once()
    assert list(pm.contexts.keys()) == ["direct"]
    assert pm.non_default_context_keys() == []


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


async def test_every_context_records_the_data_its_views_render(mock_playwright):
    """A market switch reads which market its data carry from what the view decrypted (gotchas §27)."""
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)

    scripts = [c.args[0] for c in mock_playwright["context"].add_init_script.await_args_list]
    assert scripts.count(VIEW_DATA_HOOK_JS) == 2


async def test_new_rotated_page_reports_key(mock_playwright):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    _page, key = await pm.new_rotated_page()
    assert key in {"http://a.example.com:1", "http://b.example.com:2"}


async def test_cleanup_closes_everything_when_one_close_fails(mock_playwright, caplog):
    """G11: a context flushes its HAR when it closes, so a failed page close must not skip it or the browser."""
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    mock_playwright["page"].close = AsyncMock(side_effect=Exception("Target page, context or browser has been closed"))
    mock_playwright["context"].close = AsyncMock(side_effect=[Exception("context a"), None])

    with caplog.at_level(logging.WARNING):
        await pm.cleanup()

    assert mock_playwright["context"].close.await_count == 2
    mock_playwright["browser"].close.assert_awaited_once()
    mock_playwright["playwright"].stop.assert_awaited_once()
    assert "Could not close the page: Target page, context or browser has been closed" in caplog.text
    assert "Could not close the browser context http://a.example.com:1: context a" in caplog.text


async def test_new_rotated_page_raises_when_exhausted(mock_playwright):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    for key in ["http://a.example.com:1", "http://b.example.com:2"]:
        for _ in range(3):
            pm.report_page_result(key, is_proxy_failure=True)
    with pytest.raises(AllProxiesExhaustedError):
        await pm.new_rotated_page()


async def test_a_unit_test_cannot_start_the_browser():
    """tests/conftest.py blocks Playwright outside integration tests; the `except Exception` here cannot swallow it."""
    with pytest.raises(pytest.fail.Exception, match="test_a_unit_test_cannot_start_the_browser started Playwright"):
        await PlaywrightManager().initialize(headless=True)


async def test_a_test_that_patches_playwright_itself_still_starts_it(mock_playwright):
    pm = PlaywrightManager()

    await pm.initialize(headless=True)

    assert pm.page is mock_playwright["page"]
