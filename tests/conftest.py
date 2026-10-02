"""Unit tests run offline: a test that starts Playwright fails, naming itself; integration tests are left alone."""

import pytest


@pytest.fixture(autouse=True)
def _no_browser_in_unit_tests(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        return

    def _blocked():
        # pytest.fail raises a BaseException, which the CLI's and the retry's `except Exception` cannot swallow.
        pytest.fail(f"{request.node.nodeid} started Playwright: patch the browser out of a unit test.", pytrace=False)

    monkeypatch.setattr("oddsharvester.core.playwright_manager.async_playwright", _blocked)
