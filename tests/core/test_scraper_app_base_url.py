import inspect
import logging

from oddsharvester.core import scraper_app


def test_run_scraper_accepts_base_url_param():
    sig = inspect.signature(scraper_app.run_scraper)
    assert "base_url" in sig.parameters
    assert sig.parameters["base_url"].default is None


def test_run_scraper_forwards_base_url_to_scraper(monkeypatch):
    captured = {}

    class FakeScraper:
        def __init__(self, *args, base_url=None, **kwargs):
            captured["base_url"] = base_url

        async def start_playwright(self, **kwargs):
            raise RuntimeError("stop here")  # abort before real scraping

        async def stop_playwright(self):
            pass

    monkeypatch.setattr(scraper_app, "OddsPortalScraper", FakeScraper)

    import asyncio

    asyncio.run(
        scraper_app.run_scraper(
            command="scrape_upcoming",
            sport="football",
            date="2025-01-15",
            base_url="https://www.centroquote.it",
        )
    )
    assert captured["base_url"] == "https://www.centroquote.it"


def _run_until_start(monkeypatch, **kwargs):
    class FakeScraper:
        def __init__(self, *a, base_url=None, **kw):
            pass

        async def start_playwright(self, **kw):
            raise RuntimeError("stop here")

        async def stop_playwright(self):
            pass

    monkeypatch.setattr(scraper_app, "OddsPortalScraper", FakeScraper)
    import asyncio

    asyncio.run(scraper_app.run_scraper(command="scrape_upcoming", sport="football", date="2025-01-15", **kwargs))


def test_warns_when_regional_base_url_and_no_locale(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="ScraperApp"):
        _run_until_start(monkeypatch, base_url="https://www.centroquote.it")
    assert any("locale" in r.message.lower() and "timezone" in r.message.lower() for r in caplog.records)


def test_no_warning_for_default_com(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="ScraperApp"):
        _run_until_start(monkeypatch)
    assert not any("base url" in r.message.lower() for r in caplog.records)


def test_no_warning_when_locale_set(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="ScraperApp"):
        _run_until_start(monkeypatch, base_url="https://www.centroquote.it", browser_locale_timezone="it-IT")
    assert not any("base url" in r.message.lower() for r in caplog.records)


def test_no_warning_for_oddsportal_subdomain(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="ScraperApp"):
        _run_until_start(monkeypatch, base_url="https://es.oddsportal.com")
    assert not any("base url" in r.message.lower() for r in caplog.records)
