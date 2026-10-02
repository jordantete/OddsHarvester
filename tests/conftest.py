"""Unit tests run offline: a test that starts Playwright fails, naming itself; integration tests are left alone."""

import pytest

from tests.fake_scraper import FakeScraper


@pytest.fixture(autouse=True)
def _no_browser_in_unit_tests(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        return

    def _blocked():
        # pytest.fail raises a BaseException, which the CLI's and the retry's `except Exception` cannot swallow.
        pytest.fail(f"{request.node.nodeid} started Playwright: patch the browser out of a unit test.", pytrace=False)

    monkeypatch.setattr("oddsharvester.core.playwright_manager.async_playwright", _blocked)


@pytest.fixture
def fake_scraper(monkeypatch):
    """The scraper every run_scraper call of the test builds (tests/fake_scraper.py)."""
    scraper = FakeScraper()
    monkeypatch.setattr("oddsharvester.core.scraper_app.OddsPortalScraper", scraper.build)
    return scraper
