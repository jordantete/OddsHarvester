from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from oddsharvester.utils.datetime_format import UTC_TIMESTAMP_FORMAT, format_utc


def test_format_utc_converts_aware_non_utc_datetime():
    paris = datetime(2026, 4, 18, 20, 30, tzinfo=ZoneInfo("Europe/Paris"))
    assert format_utc(paris) == "2026-04-18 18:30:00 UTC"


def test_format_utc_is_idempotent_on_utc_input():
    assert format_utc(datetime(2026, 4, 18, 18, 30, tzinfo=UTC)) == "2026-04-18 18:30:00 UTC"


def test_format_matches_the_match_date_convention():
    """The stored match_date shape, which local_kickoff parses back."""
    assert UTC_TIMESTAMP_FORMAT == "%Y-%m-%d %H:%M:%S %Z"
