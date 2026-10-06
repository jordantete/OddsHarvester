"""A frozen clock for tests that patch a module's `datetime`, and two scrape moments on either side of DST."""

from datetime import UTC, datetime
from unittest.mock import patch

# A scrape moment in summer time and one in winter time, for zones that change their UTC offset.
SUMMER_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
WINTER_NOW = datetime(2027, 1, 15, 12, 0, tzinfo=UTC)


def frozen_clock(moment: datetime) -> type[datetime]:
    """A datetime class whose now() is the aware `moment`, moved to the zone asked for; the rest is datetime's."""

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment if tz is None else moment.astimezone(tz)

    return FrozenClock


def page_clock(moment: datetime):
    """Freeze the clock the page's UTC offset is read from (gotchas §10)."""
    return patch("oddsharvester.utils.page_time.datetime", frozen_clock(moment))
