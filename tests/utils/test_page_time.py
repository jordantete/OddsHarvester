from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest
from tests.clock import frozen_clock

from oddsharvester.utils.page_time import (
    local_to_shown,
    page_utc_offset,
    shown_to_local,
    shown_to_utc,
    timezone_or_utc,
)

SUMMER_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
WINTER_NOW = datetime(2027, 1, 15, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("name", [None, "", "Not/AZone", "../Europe/London"])
def test_timezone_or_utc_falls_back_to_utc(name):
    assert timezone_or_utc(name) is UTC


def test_timezone_or_utc_returns_the_named_zone():
    assert timezone_or_utc("Europe/London") == ZoneInfo("Europe/London")


def test_timezone_or_utc_survives_missing_tzdata():
    """Without a tz database even ZoneInfo("UTC") raises; the fallback must not build a ZoneInfo."""

    def _no_tzdata(name):
        raise ZoneInfoNotFoundError(f"No time zone found with key {name}")

    with patch("oddsharvester.utils.page_time.ZoneInfo", side_effect=_no_tzdata):
        assert timezone_or_utc("UTC") is UTC


@pytest.mark.parametrize(
    ("tz_name", "now", "hours"),
    [
        ("Europe/London", SUMMER_NOW, 1),
        ("Europe/London", WINTER_NOW, 0),
        ("Europe/Paris", SUMMER_NOW, 2),
        ("Europe/Paris", WINTER_NOW, 1),
        ("Australia/Sydney", SUMMER_NOW, 10),
        ("Australia/Sydney", WINTER_NOW, 11),
        ("UTC", SUMMER_NOW, 0),
        (None, WINTER_NOW, 0),
    ],
)
def test_page_utc_offset_is_the_zone_offset_at_the_scrape_moment(tz_name, now, hours):
    assert page_utc_offset(tz_name, now) == timedelta(hours=hours)


def test_page_utc_offset_reads_the_clock_by_default():
    with patch("oddsharvester.utils.page_time.datetime", frozen_clock(WINTER_NOW)):
        assert page_utc_offset("Europe/London") == timedelta(0)


def test_a_january_time_shown_in_summer_is_read_one_hour_earlier():
    """Djokovic - Sinner kicked off at 03:45 UTC on 26 Jan 2024; scraped in BST, the page shows 04:45."""
    shown = datetime(2024, 1, 26, 4, 45)

    assert shown_to_utc(shown, "Europe/London", SUMMER_NOW) == datetime(2024, 1, 26, 3, 45, tzinfo=UTC)
    assert shown_to_local(shown, "Europe/London", SUMMER_NOW) == datetime(2024, 1, 26, 3, 45)


def test_a_july_time_shown_in_winter_is_read_one_hour_later_in_local_time():
    shown = datetime(2026, 7, 4, 18, 0)

    assert shown_to_utc(shown, "Europe/London", WINTER_NOW) == datetime(2026, 7, 4, 18, 0, tzinfo=UTC)
    assert shown_to_local(shown, "Europe/London", WINTER_NOW) == datetime(2026, 7, 4, 19, 0)


@pytest.mark.parametrize("now", [SUMMER_NOW, WINTER_NOW])
def test_utc_times_are_read_as_shown_in_any_season(now):
    shown = datetime(2026, 1, 4, 17, 30)

    assert shown_to_utc(shown, "UTC", now) == shown.replace(tzinfo=UTC)
    assert shown_to_local(shown, None, now) == shown
    assert local_to_shown(shown, "UTC", now) == shown


def test_both_instants_of_the_autumn_fold_read_as_the_same_local_clock():
    """25 Oct 2026 in London: 00:30 and 01:30 UTC are both 01:30 local, which a naive time cannot tell apart."""
    assert shown_to_local(datetime(2026, 10, 25, 0, 30), "Europe/London", WINTER_NOW) == datetime(2026, 10, 25, 1, 30)
    assert shown_to_local(datetime(2026, 10, 25, 1, 30), "Europe/London", WINTER_NOW) == datetime(2026, 10, 25, 1, 30)


def test_a_time_shown_in_the_spring_gap_never_reads_as_a_missing_local_time():
    """29 Mar 2026 in London: 01:00 to 02:00 local does not exist; 01:30 shown at +1 is 00:30 UTC and local."""
    assert shown_to_local(datetime(2026, 3, 29, 1, 30), "Europe/London", SUMMER_NOW) == datetime(2026, 3, 29, 0, 30)


def test_local_to_shown_moves_a_local_time_to_the_page_offset():
    assert local_to_shown(datetime(2025, 12, 31, 23, 30), "Europe/London", SUMMER_NOW) == datetime(2026, 1, 1, 0, 30)
    assert local_to_shown(datetime(2026, 7, 4, 19, 0), "Europe/London", WINTER_NOW) == datetime(2026, 7, 4, 18, 0)
