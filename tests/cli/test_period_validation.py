import argparse

import pytest

from src.cli.cli_argument_validator import CLIArgumentValidator
from src.utils.period_constants import MatchPeriod


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
        for period_value in MatchPeriod.get_all_cli_values():
            # Should not raise any exception
            self.validator._validate_period(period=period_value, sport="football")

    def test_validate_period_invalid_value(self):
        """Test that invalid period values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid period: 'invalid_period'. Supported periods are:"):
            self.validator._validate_period(period="invalid_period", sport="football")

    def test_validate_period_non_football_warning(self, caplog):
        """Test that non-default period for non-football sports logs a warning."""
        # Test with tennis (non-football sport) and non-default period
        self.validator._validate_period(period="1st_half", sport="tennis")

        # Check that warning was logged
        assert any(
            "Period selection '1st_half' is only supported for football" in record.message for record in caplog.records
        )

    def test_validate_period_non_football_default_no_warning(self, caplog):
        """Test that default period for non-football sports doesn't log a warning."""
        # Clear any previous logs
        caplog.clear()

        # Test with tennis (non-football sport) and default period
        self.validator._validate_period(period="full_time", sport="tennis")

        # Check that no warning was logged
        assert not any("Period selection" in record.message for record in caplog.records)

    def test_validate_period_basketball_non_default(self, caplog):
        """Test that non-default period for basketball logs a warning."""
        self.validator._validate_period(period="2nd_half", sport="basketball")

        # Check that warning was logged
        assert any(
            "Period selection '2nd_half' is only supported for football" in record.message for record in caplog.records
        )

    def test_full_validation_with_period(self):
        """Test full argument validation including period."""
        # Create a mock args namespace with all required attributes
        args = argparse.Namespace(
            command="scrape_upcoming",
            sport="football",
            date="20260107",
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
        args = argparse.Namespace(
            command="scrape_upcoming",
            sport="football",
            date="20260107",
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
