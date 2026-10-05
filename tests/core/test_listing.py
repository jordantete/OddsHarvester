from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import BeautifulSoup
from tests.dom_builders import listing_row

from oddsharvester.core.listing import _parse_date_header, _row_has_started, _row_kickoff_datetime


class TestRowHasStarted:
    """Unit tests for the _row_has_started helper (GitHub issue #58)."""

    def _row(self, status: str):
        return BeautifulSoup(listing_row("/football/h2h/a-1/b-2/#EV", status=status), "lxml").find("a")

    def test_upcoming_clock_time_means_not_started(self):
        assert _row_has_started(self._row("21:00")) is False

    def test_single_digit_hour_clock_time_means_not_started(self):
        assert _row_has_started(self._row("9:00")) is False

    def test_finished_status_means_started(self):
        assert _row_has_started(self._row("Finished FIN")) is True

    def test_live_period_marker_means_started(self):
        """Live volleyball: the first column shows a set marker instead of a clock."""
        assert _row_has_started(self._row("4S")) is True

    def test_live_football_half_marker_means_started(self):
        assert _row_has_started(self._row("HT")) is True

    def test_empty_status_column_is_failsafe_keep(self):
        """No marker at all (DOM drift): treat as upcoming rather than drop the row."""
        assert _row_has_started(self._row("")) is False


# -- Date header parser ---------------------------------------------------


class TestParseDateHeader:
    """Unit tests for the _parse_date_header helper."""

    def test_today_returns_today_in_utc_by_default(self):
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Today, 14 Apr") == today_utc

    def test_tomorrow_returns_today_plus_one_day(self):
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Tomorrow, 15 Apr") == today_utc + timedelta(days=1)

    def test_yesterday_returns_today_minus_one_day(self):
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Yesterday, 13 Apr") == today_utc - timedelta(days=1)

    def test_explicit_date_with_year(self):
        assert _parse_date_header("18 Apr 2026") == date(2026, 4, 18)

    def test_explicit_date_with_full_month_name(self):
        # Only first 3 chars are looked up, so "April" should work the same as "Apr"
        assert _parse_date_header("18 April 2026") == date(2026, 4, 18)

    def test_tournament_suffix_is_stripped(self):
        assert _parse_date_header("18 Apr 2026 - Apertura") == date(2026, 4, 18)

    def test_today_with_tournament_suffix(self):
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Today, 14 Apr  - Apertura") == today_utc

    def test_date_without_year_uses_current_year(self):
        # Use a month close to today to avoid the >180 days roll-over heuristic
        today = datetime.now(ZoneInfo("UTC")).date()
        result = _parse_date_header(f"{today.day:02d} {today.strftime('%b')}")
        assert result == today

    def test_empty_string_returns_none(self):
        assert _parse_date_header("") is None

    def test_garbage_string_returns_none(self):
        assert _parse_date_header("not a date") is None

    def test_invalid_day_returns_none(self):
        assert _parse_date_header("99 Apr 2026") is None

    def test_invalid_month_returns_none(self):
        assert _parse_date_header("18 Xyz 2026") is None

    def test_invalid_tz_falls_back_to_utc(self):
        # Unknown tz name should not crash, should fall back to UTC silently
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Today, 14 Apr", tz_name="Not/A_Real_Zone") == today_utc

    def test_custom_timezone_used_for_today(self):
        # "Today" should resolve to current date in the specified timezone
        tokyo_today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
        assert _parse_date_header("Today, 14 Apr", tz_name="Asia/Tokyo") == tokyo_today


class TestRowKickoffDatetime:
    """Unit tests for the _row_kickoff_datetime helper (GitHub issue #77)."""

    def _row(self, status: str):
        return BeautifulSoup(listing_row("/football/h2h/a-1/b-2/#EV", status=status), "lxml").find("a")

    def test_valid_time_and_date_returns_aware_datetime(self):
        row = self._row("21:00")
        assert _row_kickoff_datetime(row, date(2026, 4, 18), "UTC") == datetime(2026, 4, 18, 21, 0, tzinfo=UTC)

    def test_single_digit_hour_parsed(self):
        row = self._row("9:05")
        assert _row_kickoff_datetime(row, date(2026, 4, 18), "UTC") == datetime(2026, 4, 18, 9, 5, tzinfo=UTC)

    def test_none_row_date_returns_none(self):
        row = self._row("21:00")
        assert _row_kickoff_datetime(row, None, "UTC") is None

    def test_empty_status_column_returns_none(self):
        row = self._row("")
        assert _row_kickoff_datetime(row, date(2026, 4, 18), "UTC") is None

    def test_live_marker_returns_none(self):
        row = self._row("1H")
        assert _row_kickoff_datetime(row, date(2026, 4, 18), "UTC") is None

    def test_invalid_clock_returns_none(self):
        row = self._row("25:00")
        assert _row_kickoff_datetime(row, date(2026, 4, 18), "UTC") is None


def test_parse_date_header_survives_missing_tzdata():
    """Regression: with tz_name="UTC" and no tz database installed, ZoneInfo
    raises for every name including "UTC". The fallback must return a date
    derived from the stdlib UTC constant, not crash.
    """

    def _no_tzdata(_name):
        raise ZoneInfoNotFoundError(f"No time zone found with key {_name}")

    today_utc = datetime.now(UTC).date()
    with patch("oddsharvester.utils.page_time.ZoneInfo", side_effect=_no_tzdata):
        assert _parse_date_header("Today, 14 Apr", tz_name="UTC") == today_utc
