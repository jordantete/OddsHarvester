"""Times as OddsPortal shows them: every time on a page is rendered at the browser zone's UTC offset of the
scrape moment, not at the offset in force on the date it shows (gotchas §10)."""

from datetime import UTC, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def timezone_or_utc(tz_name: str | None) -> tzinfo:
    """The named timezone, or UTC for an empty or unknown name."""
    if not tz_name:
        return UTC
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return UTC


def page_utc_offset(tz_name: str | None, now: datetime | None = None) -> timedelta:
    """The offset the page shows every time at: the zone's UTC offset at `now` (aware; the clock by default)."""
    moment = now if now is not None else datetime.now(UTC)
    return moment.astimezone(timezone_or_utc(tz_name)).utcoffset()


def shown_to_utc(shown: datetime, tz_name: str | None, now: datetime | None = None) -> datetime:
    """The aware UTC instant of a naive time as the page shows it."""
    return (shown - page_utc_offset(tz_name, now)).replace(tzinfo=UTC)


def shown_to_local(shown: datetime, tz_name: str | None, now: datetime | None = None) -> datetime:
    """The naive local time of the zone, under its rules for that date, of a naive time as the page shows it."""
    return shown_to_utc(shown, tz_name, now).astimezone(timezone_or_utc(tz_name)).replace(tzinfo=None)


def local_to_shown(local: datetime, tz_name: str | None, now: datetime | None = None) -> datetime:
    """The naive time the page shows for a naive local time of the zone on that date."""
    instant = local.replace(tzinfo=timezone_or_utc(tz_name)).astimezone(UTC)
    return (instant + page_utc_offset(tz_name, now)).replace(tzinfo=None)
