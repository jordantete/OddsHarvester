"""Unit tests run offline: a test that starts Playwright or sends an AWS request fails, naming itself; integration
tests are left alone."""

import pytest

from tests.fake_scraper import FakeScraper


@pytest.fixture(autouse=True)
def _unit_tests_stay_offline(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        return

    def _blocked():
        # pytest.fail raises a BaseException, which the CLI's and the retry's `except Exception` cannot swallow.
        pytest.fail(f"{request.node.nodeid} started Playwright: patch the browser out of a unit test.", pytrace=False)

    monkeypatch.setattr("oddsharvester.core.playwright_manager.async_playwright", _blocked)

    try:
        from botocore.httpsession import URLLib3Session
    except ImportError:  # boto3 is the s3 extra's
        return

    def _no_request(*args, **kwargs):
        pytest.fail(f"{request.node.nodeid} sent an AWS request: patch boto3 out of a unit test.", pytrace=False)

    monkeypatch.setattr(URLLib3Session, "send", _no_request)


@pytest.fixture
def fake_scraper(monkeypatch):
    """The scraper every run_scraper call of the test builds (tests/fake_scraper.py)."""
    scraper = FakeScraper()
    monkeypatch.setattr("oddsharvester.core.scraper_app.OddsPortalScraper", scraper.build)
    return scraper
