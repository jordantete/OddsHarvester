import argparse
from datetime import datetime, timedelta

import pytest

from src.cli.cli_argument_validator import CLIArgumentValidator


class TestBookiesFilterValidation:
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = CLIArgumentValidator()

    def test_validate_valid_bookies_filter_all(self):
        """Test validation with valid 'all' bookies filter."""
        errors = self.validator._validate_bookies_filter("all")
        assert errors == []

    def test_validate_valid_bookies_filter_classic(self):
        """Test validation with valid 'classic' bookies filter."""
        errors = self.validator._validate_bookies_filter("classic")
        assert errors == []

    def test_validate_valid_bookies_filter_crypto(self):
        """Test validation with valid 'crypto' bookies filter."""
        errors = self.validator._validate_bookies_filter("crypto")
        assert errors == []

    def test_validate_invalid_bookies_filter(self):
        """Test validation with invalid bookies filter."""
        errors = self.validator._validate_bookies_filter("invalid")
        assert len(errors) == 1
        assert "Invalid bookies filter" in errors[0]
        assert "invalid" in errors[0]
        assert "all, classic, crypto" in errors[0]

    def test_validate_bookies_filter_case_sensitive(self):
        """Test that bookies filter validation is case-sensitive."""
        # Uppercase should fail
        errors = self.validator._validate_bookies_filter("ALL")
        assert len(errors) == 1
        assert "Invalid bookies filter" in errors[0]

    def test_validate_bookies_filter_empty_string(self):
        """Test validation with empty string."""
        errors = self.validator._validate_bookies_filter("")
        assert len(errors) == 1
        assert "Invalid bookies filter" in errors[0]

    def test_full_validation_with_bookies_filter(self):
        """Test full argument validation including bookies_filter."""
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
        )

        # Should not raise any exception
        self.validator.validate_args(args)

    def test_full_validation_with_invalid_bookies_filter(self):
        """Test full argument validation with invalid bookies_filter."""
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
            bookies_filter="invalid_filter",
        )

        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            self.validator.validate_args(args)

        assert "Invalid bookies filter" in str(exc_info.value)
