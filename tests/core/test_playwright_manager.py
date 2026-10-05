import logging
from unittest.mock import AsyncMock, patch

import pytest

from oddsharvester.core.browser.view_data import VIEW_DATA_HOOK_JS
from oddsharvester.core.exceptions import AllProxiesExhaustedError
from oddsharvester.core.playwright_manager import PlaywrightManager, headful_user_agent
from oddsharvester.utils.proxy_manager import ProxyManager

MAC_HEADLESS_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "HeadlessChrome/143.0.0.0 Safari/537.36"
)
MAC_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0.0.0 Safari/537.36"
)


@pytest.fixture
def mock_playwright():
    """Mock async_playwright with browser/context/page chain."""
    with patch("oddsharvester.core.playwright_manager.async_playwright") as mock_ap:
        playwright = AsyncMock()
        browser = AsyncMock()
        context = AsyncMock()
        page = AsyncMock()
        cdp_session = AsyncMock()

        mock_ap.return_value.start = AsyncMock(return_value=playwright)
        playwright.chromium.launch = AsyncMock(return_value=browser)
        browser.version = "143.0.7499.4"
        browser.new_browser_cdp_session = AsyncMock(return_value=cdp_session)
        cdp_session.send = AsyncMock(return_value={"userAgent": MAC_HEADLESS_UA})
        browser.new_context = AsyncMock(return_value=context)
        context.new_page = AsyncMock(return_value=page)
        context.add_init_script = AsyncMock()
        context.route_from_har = AsyncMock()
        page.evaluate = AsyncMock(return_value="UTC")

        yield {
            "playwright": playwright,
            "browser": browser,
            "context": context,
            "page": page,
            "cdp_session": cdp_session,
        }


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


@pytest.mark.parametrize("headless", [True, False], ids=["headless", "headed"])
async def test_the_full_chromium_build_runs_headless_or_headed(mock_playwright, headless):
    pm = PlaywrightManager()
    await pm.initialize(headless=headless)

    launch_kwargs = mock_playwright["playwright"].chromium.launch.await_args.kwargs
    assert launch_kwargs["channel"] == "chromium"
    assert launch_kwargs["headless"] is headless


async def test_a_missing_browser_build_fails_the_run_with_playwrights_message(mock_playwright, caplog):
    """No fallback to another build: Playwright's message names the install command to run."""
    message = "BrowserType.launch: Executable doesn't exist at /ms-playwright/chromium-1200/chrome-linux/chrome"
    mock_playwright["playwright"].chromium.launch = AsyncMock(side_effect=Exception(message))
    pm = PlaywrightManager()

    with caplog.at_level(logging.ERROR), pytest.raises(Exception, match="Executable doesn't exist"):
        await pm.initialize(headless=True)

    mock_playwright["playwright"].chromium.launch.assert_awaited_once()
    assert f"Failed to initialize Playwright: {message}" in caplog.messages


async def test_each_context_gets_the_view_data_hook_and_no_other_script(mock_playwright):
    """No script patches navigator: webdriver, plugins and languages are the browser's own."""
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)

    scripts = [c.args[0] for c in mock_playwright["context"].add_init_script.await_args_list]
    assert scripts == [VIEW_DATA_HOOK_JS, VIEW_DATA_HOOK_JS]


@pytest.mark.parametrize("user_agent", [None, ""], ids=["none", "empty"])
async def test_without_a_user_agent_every_context_gets_the_browsers_own_as_chrome(mock_playwright, user_agent):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, user_agent=user_agent, proxy_manager=proxy_manager)

    agents = [c.kwargs["user_agent"] for c in mock_playwright["browser"].new_context.await_args_list]
    assert agents == [MAC_CHROME_UA, MAC_CHROME_UA]
    mock_playwright["cdp_session"].send.assert_awaited_once_with("Browser.getVersion")


async def test_an_explicit_user_agent_is_passed_through(mock_playwright):
    pm = PlaywrightManager()
    await pm.initialize(headless=True, user_agent="Custom/1.0")

    assert mock_playwright["browser"].new_context.await_args.kwargs["user_agent"] == "Custom/1.0"
    mock_playwright["browser"].new_browser_cdp_session.assert_not_awaited()


async def test_a_failed_user_agent_read_fails_the_run_and_cleanup_still_closes_the_browser(mock_playwright):
    mock_playwright["cdp_session"].send = AsyncMock(side_effect=Exception("Browser.getVersion: Target closed"))
    pm = PlaywrightManager()

    with pytest.raises(Exception, match="Target closed"):
        await pm.initialize(headless=True)
    await pm.cleanup()

    mock_playwright["browser"].new_context.assert_not_awaited()
    mock_playwright["browser"].close.assert_awaited_once()
    mock_playwright["playwright"].stop.assert_awaited_once()


@pytest.mark.parametrize(("locale", "expected"), [(None, "en-US"), ("", "en-US"), ("en-GB", "en-GB")])
async def test_every_context_gets_the_locale_or_en_us(mock_playwright, locale, expected):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, locale=locale, proxy_manager=proxy_manager)

    locales = [c.kwargs["locale"] for c in mock_playwright["browser"].new_context.await_args_list]
    assert locales == [expected, expected]


async def test_the_run_logs_the_browser_version_and_user_agent_once(mock_playwright, caplog):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()

    with caplog.at_level(logging.INFO):
        await pm.initialize(headless=True, proxy_manager=proxy_manager)

    assert caplog.messages.count(f"Browser: Chromium 143.0.7499.4, user agent: {MAC_CHROME_UA}") == 1


@pytest.mark.parametrize(
    ("browser_user_agent", "expected"),
    [
        (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/143.0.0.0 "
            "Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        ),
        (MAC_HEADLESS_UA, MAC_CHROME_UA),
        (MAC_CHROME_UA, MAC_CHROME_UA),
    ],
    ids=["linux", "mac", "already-headful"],
)
def test_headful_user_agent(browser_user_agent, expected):
    assert headful_user_agent(browser_user_agent) == expected


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


async def test_a_second_cleanup_closes_nothing_again(mock_playwright):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    await pm.cleanup()

    await pm.cleanup()

    mock_playwright["page"].close.assert_awaited_once()
    assert mock_playwright["context"].close.await_count == 2
    mock_playwright["browser"].close.assert_awaited_once()
    mock_playwright["playwright"].stop.assert_awaited_once()
    assert (pm.page, pm.context, pm.contexts, pm.browser, pm.playwright) == (None, None, {}, None, None)


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


@pytest.mark.parametrize("docker", [False, True], ids=["local", "docker"])
async def test_no_launch_argument_replaces_playwrights_disabled_features(mock_playwright, docker):
    """Chromium reads only the last --disable-features switch, and Playwright passes its own list first."""
    with patch("oddsharvester.core.playwright_manager.is_running_in_docker", return_value=docker):
        pm = PlaywrightManager()
        await pm.initialize(headless=True)

    args = mock_playwright["playwright"].chromium.launch.await_args.kwargs["args"]
    assert [a for a in args if a.startswith("--disable-features")] == []
