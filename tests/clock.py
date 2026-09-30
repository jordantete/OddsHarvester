"""A frozen clock for tests that patch a module's `datetime`."""

from datetime import datetime


def frozen_clock(moment: datetime) -> type[datetime]:
    """A datetime class whose now() is the aware `moment`, moved to the zone asked for; the rest is datetime's."""

    class FrozenClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment if tz is None else moment.astimezone(tz)

    return FrozenClock
