"""--date is refused only once it is past in every timezone, whatever the machine's timezone."""

from datetime import UTC, datetime
import time
from unittest.mock import patch

import click
import pytest

from oddsharvester.cli.validators import validate_date


def _frozen_clock(instant: datetime) -> type[datetime]:
    """A datetime class whose now() is `instant`; the naive now() follows the machine's TZ, as the real one does."""

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.astimezone().replace(tzinfo=None)

    return FrozenDatetime


@pytest.fixture(params=["Etc/GMT+12", "Pacific/Kiritimati"])
def machine_timezone(request, monkeypatch):
    """Run the test with the machine clock at UTC-12, then at UTC+14."""
    monkeypatch.setenv("TZ", request.param)
    time.tzset()
    yield request.param
    monkeypatch.undo()
    time.tzset()


def _validate_at(instant: datetime, value: str) -> str:
    with patch("oddsharvester.cli.validators.datetime", _frozen_clock(instant)):
        return validate_date(None, None, value)


def test_the_collector_date_is_accepted_late_in_the_utc_day(machine_timezone):
    """The collector passes the UTC date; at 23:30 UTC that date is already over east of UTC+1."""
    assert _validate_at(datetime(2026, 7, 14, 23, 30, tzinfo=UTC), "20260714") == "20260714"


def test_a_date_still_current_in_utc_minus_12_is_accepted(machine_timezone):
    """At 05:00 UTC on 15 July it is still 14 July in UTC-12."""
    assert _validate_at(datetime(2026, 7, 15, 5, 0, tzinfo=UTC), "20260714") == "20260714"


def test_the_day_before_today_in_utc_minus_12_is_rejected(machine_timezone):
    with pytest.raises(click.BadParameter, match="already past in every timezone"):
        _validate_at(datetime(2026, 7, 15, 5, 0, tzinfo=UTC), "20260713")
