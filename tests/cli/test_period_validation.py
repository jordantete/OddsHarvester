import argparse
from datetime import datetime, timedelta

import pytest

from src.cli.cli_argument_validator import CLIArgumentValidator
from src.utils.period_constants import FootballPeriod


class TestPeriodValidation:
    """Tests for period validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = CLIArgumentValidator()

    def test_validate_valid_period_full_time(self):
        """Test validation with valid 'full_time' period."""
        # Should not raise any exception
        self.validator._validate_period(period="full_time", sport="football")

    def test_validate_valid_period_first_half(self):
        """Test validation with valid '1st_half' period."""
        # Should not raise any exception
        self.validator._validate_period(period="1st_half", sport="football")

    def test_validate_valid_period_second_half(self):
        """Test validation with valid '2nd_half' period."""
        # Should not raise any exception
        self.validator._validate_period(period="2nd_half", sport="football")

    def test_validate_period_all_values_football(self):
        """Test that all period values are accepted for football."""
        for period_value in [p.value for p in FootballPeriod]:
            # Should not raise any exception
            self.validator._validate_period(period=period_value, sport="football")

    def test_validate_period_invalid_value(self):
        """Test that invalid period values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid period: 'invalid_period' for sport 'football'"):
            self.validator._validate_period(period="invalid_period", sport="football")

    def test_validate_period_tennis_valid(self):
        """Test that valid tennis periods are accepted."""
        # Should not raise any exception
        self.validator._validate_period(period="full_time", sport="tennis")
        self.validator._validate_period(period="1st_set", sport="tennis")

    def test_validate_period_basketball_valid(self):
        """Test that valid basketball periods are accepted."""
        # Should not raise any exception
        self.validator._validate_period(period="full_including_ot", sport="basketball")
        self.validator._validate_period(period="1st_quarter", sport="basketball")

    def test_validate_period_wrong_for_sport(self):
        """Test that using wrong period for a sport raises error."""
        # Football period for tennis should raise error
        with pytest.raises(ValueError, match="Invalid period: '1st_half' for sport 'tennis'"):
            self.validator._validate_period(period="1st_half", sport="tennis")

        # Tennis period for football should raise error
        with pytest.raises(ValueError, match="Invalid period: '1st_set' for sport 'football'"):
            self.validator._validate_period(period="1st_set", sport="football")

    def test_validate_period_unregistered_sport(self, caplog):
        """Test that unregistered sport logs a warning."""
        self.validator._validate_period(period="full_time", sport="cricket")

        # Check that warning was logged
        assert any("does not have period configuration" in record.message for record in caplog.records)

    def test_full_validation_with_period(self):
        """Test full argument validation including period."""
        # Create a mock args namespace with all required attributes
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        args = argparse.Namespace(
            command="scrape_upcoming",
            sport="football",
            date=future_date,
            leagues=None,
            markets=["1x2"],
            storage="local",
            format="json",
            file_path=None,
            proxies=None,
            browser_user_agent=None,
            browser_locale_timezone=None,
            browser_timezone_id=None,
            target_bookmaker=None,
            scrape_odds_history=False,
            headless=True,
            match_links=None,
            odds_format="Decimal Odds",
            concurrency_tasks=3,
            bookies_filter="all",
            period="1st_half",
        )

        # Should not raise any exception
        self.validator.validate_args(args)

    def test_full_validation_with_invalid_period(self):
        """Test full argument validation with invalid period."""
        future_date = (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")
        args = argparse.Namespace(
            command="scrape_upcoming",
            sport="football",
            date=future_date,
            leagues=None,
            markets=["1x2"],
            storage="local",
            format="json",
            file_path=None,
            proxies=None,
            browser_user_agent=None,
            browser_locale_timezone=None,
            browser_timezone_id=None,
            target_bookmaker=None,
            scrape_odds_history=False,
            headless=True,
            match_links=None,
            odds_format="Decimal Odds",
            concurrency_tasks=3,
            bookies_filter="all",
            period="invalid_period",
        )

        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            self.validator.validate_args(args)

        assert "Invalid period" in str(exc_info.value)
