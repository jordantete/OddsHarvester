"""run_scraper hands --base-url to the scraper and warns when a regional mirror runs without a locale or a timezone."""

import logging

import pytest

from oddsharvester.core.scraper_app import run_scraper

UPCOMING = {"command": "scrape_upcoming", "sport": "football", "date": "2025-01-15"}
MIRROR = "https://www.centroquote.it"


async def test_run_scraper_forwards_base_url_to_scraper(fake_scraper):
    await run_scraper(**UPCOMING, base_url=MIRROR)

    assert fake_scraper.built_with["base_url"] == MIRROR


@pytest.mark.parametrize(
    ("options", "warned"),
    [
        ({"base_url": MIRROR}, True),
        ({}, False),
        ({"base_url": MIRROR, "browser_locale_timezone": "it-IT"}, False),
        ({"base_url": "https://es.oddsportal.com"}, False),
        ({"base_url": MIRROR, "browser_timezone_id": "Europe/Rome"}, False),
        ({"base_url": "https://www.notoddsportal.com"}, True),
    ],
    ids=["mirror", "default", "mirror with a locale", "oddsportal subdomain", "mirror with a timezone", "lookalike"],
)
async def test_a_regional_base_url_without_locale_or_timezone_warns(fake_scraper, caplog, options, warned):
    with caplog.at_level(logging.WARNING, logger="ScraperApp"):
        await run_scraper(**UPCOMING, **options)

    assert any("Regional base URL" in record.getMessage() for record in caplog.records) is warned
