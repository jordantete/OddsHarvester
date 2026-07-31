"""Canonical UTC timestamp shape for scraped output fields."""

from datetime import UTC, datetime

UTC_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S %Z"


def format_utc(dt: datetime) -> str:
    """Render an aware datetime as a UTC output timestamp."""
    return dt.astimezone(UTC).strftime(UTC_TIMESTAMP_FORMAT)
