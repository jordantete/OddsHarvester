import inspect

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
