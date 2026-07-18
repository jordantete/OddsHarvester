from oddsharvester.utils.venue_timezone_constants import (
    MULTI_TZ_CITY_TIMEZONES,
    resolve_venue_timezone,
)


def test_single_timezone_country_resolves_directly():
    assert resolve_venue_timezone("England", None) == "Europe/London"
    assert resolve_venue_timezone("France", "Paris") == "Europe/Paris"


def test_multi_timezone_country_resolves_by_town():
    assert resolve_venue_timezone("USA", "Los Angeles") == "America/Los_Angeles"
    assert resolve_venue_timezone("USA", "New York") == "America/New_York"


def test_town_lookup_is_case_and_whitespace_insensitive():
    assert resolve_venue_timezone("USA", "  los angeles ") == "America/Los_Angeles"


def test_multi_timezone_country_unknown_town_returns_none():
    assert resolve_venue_timezone("USA", "Nowhereville") is None


def test_multi_timezone_country_missing_town_returns_none():
    assert resolve_venue_timezone("USA", None) is None


def test_unknown_country_returns_none():
    assert resolve_venue_timezone("Atlantis", "Poseidonis") is None


def test_missing_country_returns_none():
    assert resolve_venue_timezone(None, "Paris") is None


def test_every_curated_timezone_is_a_valid_iana_id():
    from zoneinfo import ZoneInfo

    from oddsharvester.utils.venue_timezone_constants import COUNTRY_TIMEZONES

    for tz in COUNTRY_TIMEZONES.values():
        ZoneInfo(tz)  # raises if invalid
    for city_map in MULTI_TZ_CITY_TIMEZONES.values():
        for tz in city_map.values():
            ZoneInfo(tz)
