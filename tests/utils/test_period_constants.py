import pytest

from src.utils.period_constants import MatchPeriod


class TestMatchPeriod:
    """Tests for the MatchPeriod enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert MatchPeriod.FULL_TIME.value == "full_time"
        assert MatchPeriod.FIRST_HALF.value == "1st_half"
        assert MatchPeriod.SECOND_HALF.value == "2nd_half"

    def test_get_display_label(self):
        """Test getting display labels for UI."""
        assert MatchPeriod.get_display_label(MatchPeriod.FULL_TIME) == "Full Time"
        assert MatchPeriod.get_display_label(MatchPeriod.FIRST_HALF) == "1st Half"
        assert MatchPeriod.get_display_label(MatchPeriod.SECOND_HALF) == "2nd Half"

    def test_get_internal_value(self):
        """Test getting internal values for scraper functions."""
        assert MatchPeriod.get_internal_value(MatchPeriod.FULL_TIME) == "FullTime"
        assert MatchPeriod.get_internal_value(MatchPeriod.FIRST_HALF) == "FirstHalf"
        assert MatchPeriod.get_internal_value(MatchPeriod.SECOND_HALF) == "SecondHalf"

    def test_from_cli_value_valid(self):
        """Test converting valid CLI values to enum."""
        assert MatchPeriod.from_cli_value("full_time") == MatchPeriod.FULL_TIME
        assert MatchPeriod.from_cli_value("1st_half") == MatchPeriod.FIRST_HALF
        assert MatchPeriod.from_cli_value("2nd_half") == MatchPeriod.SECOND_HALF

    def test_from_cli_value_invalid(self):
        """Test that invalid CLI values raise ValueError."""
        with pytest.raises(ValueError, match="Invalid period value"):
            MatchPeriod.from_cli_value("invalid")

        with pytest.raises(ValueError, match="Invalid period value"):
            MatchPeriod.from_cli_value("full-time")

    def test_get_all_cli_values(self):
        """Test getting all valid CLI values."""
        cli_values = MatchPeriod.get_all_cli_values()
        assert len(cli_values) == 3
        assert "full_time" in cli_values
        assert "1st_half" in cli_values
        assert "2nd_half" in cli_values
