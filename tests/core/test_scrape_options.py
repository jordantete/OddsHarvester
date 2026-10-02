"""ScrapeOptions: the settings of one run, normalized once, with the names and defaults of run_scraper."""

from dataclasses import MISSING, FrozenInstanceError, fields

import pytest

from oddsharvester.core.scrape_options import ScrapeOptions
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.command_enum import CommandEnum
from oddsharvester.utils.period_constants import BasketballPeriod, FootballPeriod
from oddsharvester.utils.sport_market_constants import Sport

# The signature run_scraper had before ScrapeOptions existed, in order: (name, default).
RUN_SCRAPER_SIGNATURE = [
    ("command", MISSING),
    ("match_links", None),
    ("sport", None),
    ("date", None),
    ("leagues", None),
    ("seasons", None),
    ("markets", None),
    ("max_pages", None),
    ("proxy_url", None),
    ("proxy_user", None),
    ("proxy_pass", None),
    ("browser_user_agent", None),
    ("browser_locale_timezone", None),
    ("browser_timezone_id", None),
    ("base_url", None),
    ("target_bookmaker", None),
    ("scrape_odds_history", False),
    ("headless", True),
    ("preview_submarkets_only", False),
    ("bookies_filter", "all"),
    ("period", None),
    ("request_delay", 1.0),
    ("concurrency_tasks", 3),
    ("include_started", False),
    ("kickoff_within_hours", None),
    ("links_only", False),
    ("local_kickoff", False),
    ("on_match", None),
]


def test_the_options_keep_the_names_order_and_defaults_of_run_scraper():
    assert [(field.name, field.default) for field in fields(ScrapeOptions)] == RUN_SCRAPER_SIGNATURE


def test_strings_and_enums_build_the_same_options():
    from_strings = ScrapeOptions(
        command="scrape_historic", sport="football", bookies_filter="classic", period="1st_half"
    )
    from_enums = ScrapeOptions(
        command=CommandEnum.HISTORIC,
        sport=Sport.FOOTBALL,
        bookies_filter=BookiesFilter.CLASSIC,
        period=FootballPeriod.FIRST_HALF,
    )

    assert from_strings == from_enums
    assert (from_enums.command, from_enums.sport, from_enums.bookies_filter, from_enums.period) == (
        CommandEnum.HISTORIC,
        "football",
        BookiesFilter.CLASSIC,
        FootballPeriod.FIRST_HALF,
    )


def test_a_missing_period_is_the_default_of_the_sport():
    assert ScrapeOptions(command="scrape_upcoming", sport="basketball").period is BasketballPeriod.FULL_INCLUDING_OT
    assert ScrapeOptions(command="scrape_live").period is None


@pytest.mark.parametrize(
    ("proxy_url", "expected"),
    [
        (None, ()),
        ((), ()),
        ("http://a.example:1", ("http://a.example:1",)),
        (["http://a.example:1", "http://b.example:2"], ("http://a.example:1", "http://b.example:2")),
        (("http://a.example:1",), ("http://a.example:1",)),
    ],
)
def test_the_proxy_urls_become_a_tuple(proxy_url, expected):
    assert ScrapeOptions(command="scrape_upcoming", proxy_url=proxy_url).proxy_url == expected


@pytest.mark.parametrize(
    "keywords",
    [{"command": "scrape_everything"}, {"command": "scrape_upcoming", "bookies_filter": "sharp"}],
    ids=["command", "bookies filter"],
)
def test_an_unknown_value_is_refused_when_the_options_are_built(keywords):
    with pytest.raises(ValueError, match="is not a valid"):
        ScrapeOptions(**keywords)


def test_the_repr_shows_no_proxy_setting():
    options = ScrapeOptions(
        command="scrape_upcoming",
        proxy_url="http://user:secret@proxy.example:8080",
        proxy_user="me",
        proxy_pass="hunter2",
    )

    assert "proxy" not in repr(options)
    assert "secret" not in repr(options)
    assert "hunter2" not in repr(options)


def test_the_options_cannot_change_once_built():
    options = ScrapeOptions(command="scrape_upcoming")

    with pytest.raises(FrozenInstanceError):
        options.sport = "tennis"
