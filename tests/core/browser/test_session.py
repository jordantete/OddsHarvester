"""Unit tests for the community and team browser session and its page load (mocked Playwright)."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from oddsharvester.core.browser.session import browser_session, open_page
from oddsharvester.core.exceptions import RateLimitError
from oddsharvester.utils.constants import PAGE_GOTO_TIMEOUT_MS, RATE_LIMIT_RETRY_DELAY_S

_SESSION = "oddsharvester.core.browser.session"
_URL = "https://www.oddsportal.com/community/predictions/#sport/football/"


def _manager():
    manager = MagicMock()
    manager.initialize = AsyncMock()
    manager.cleanup = AsyncMock()
    return manager


@patch(f"{_SESSION}.ProxyManager")
@patch(f"{_SESSION}.PlaywrightManager")
async def test_the_session_starts_playwright_with_the_run_options_and_cleans_up(pm_cls, proxy_cls):
    pm_cls.return_value = manager = _manager()

    async with browser_session(
        headless=False,
        proxy_url="http://a:1",
        proxy_user="u",
        proxy_pass="pw",
        user_agent="ua",
        locale="fr-BE",
        timezone_id="Europe/Brussels",
    ) as session_manager:
        assert session_manager is manager
        manager.cleanup.assert_not_awaited()

    proxy_cls.assert_called_once_with(proxy_url="http://a:1", proxy_user="u", proxy_pass="pw")
    manager.initialize.assert_awaited_once_with(
        headless=False,
        user_agent="ua",
        locale="fr-BE",
        timezone_id="Europe/Brussels",
        proxy_manager=proxy_cls.return_value,
    )
    manager.cleanup.assert_awaited_once()


@pytest.mark.parametrize("proxy_url", [("http://a:1", "http://b:2"), ["http://a:1", "http://b:2"]])
@patch(f"{_SESSION}.ProxyManager")
@patch(f"{_SESSION}.PlaywrightManager")
async def test_several_proxy_urls_make_one_rotating_pool(pm_cls, proxy_cls, proxy_url):
    pm_cls.return_value = _manager()

    async with browser_session(proxy_url=proxy_url):
        pass

    proxy_cls.assert_called_once_with(proxy_urls=["http://a:1", "http://b:2"], proxy_user=None, proxy_pass=None)


@patch(f"{_SESSION}.PlaywrightManager")
async def test_the_session_is_cleaned_up_when_the_run_raises(pm_cls):
    pm_cls.return_value = manager = _manager()

    with pytest.raises(RuntimeError, match="boom"):
        async with browser_session():
            raise RuntimeError("boom")

    manager.cleanup.assert_awaited_once()


@patch(f"{_SESSION}.PlaywrightManager")
async def test_the_session_is_cleaned_up_when_playwright_fails_to_start(pm_cls):
    pm_cls.return_value = manager = _manager()
    manager.initialize = AsyncMock(side_effect=RuntimeError("no browser"))

    with pytest.raises(RuntimeError, match="no browser"):
        async with browser_session():
            pytest.fail("the body must not run without a browser")

    manager.cleanup.assert_awaited_once()


def _page(url="about:blank", status=200):
    page = MagicMock()
    page.url = url
    page.goto = AsyncMock(return_value=MagicMock(status=status))
    return page


async def test_open_page_loads_the_url_with_the_page_timeout():
    page = _page()

    response = await open_page(page, _URL)

    assert response is page.goto.return_value
    page.goto.assert_awaited_once_with(_URL, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded")


async def test_a_429_raises_rate_limit_error_with_the_rate_limit_delay():
    page = _page(status=429)

    with pytest.raises(RateLimitError, match="rate limited by OddsPortal: HTTP 429 on page") as excinfo:
        await open_page(page, _URL)

    assert excinfo.value.url == _URL
    assert excinfo.value.retry_after == RATE_LIMIT_RETRY_DELAY_S
    assert excinfo.value.is_retryable is True


async def test_a_page_already_on_that_document_is_reloaded_through_a_blank_page():
    """A goto that only changes the fragment neither reloads the page nor returns a response."""
    page = _page(url="https://www.oddsportal.com/community/predictions/#sport/tennis/")

    await open_page(page, _URL)

    assert page.goto.await_args_list == [
        call("about:blank"),
        call(_URL, timeout=PAGE_GOTO_TIMEOUT_MS, wait_until="domcontentloaded"),
    ]
