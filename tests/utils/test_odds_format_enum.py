import pytest

from src.utils.odds_format_enum import OddsFormat


def test_odds_format_enum_values():
    """Test that all expected odds format values are present."""
    expected_values = ["Decimal Odds", "Fractional Odds", "Money Line Odds", "Hong Kong Odds"]

    actual_values = [format.value for format in OddsFormat]
    assert actual_values == expected_values


def test_odds_format_enum_from_value():
    """Test creating enum instances from string values."""
    assert OddsFormat("Decimal Odds") == OddsFormat.DECIMAL_ODDS
    assert OddsFormat("Fractional Odds") == OddsFormat.FRACTIONAL_ODDS
    assert OddsFormat("Money Line Odds") == OddsFormat.MONEY_LINE_ODDS
    assert OddsFormat("Hong Kong Odds") == OddsFormat.HONG_KONG_ODDS


def test_odds_format_enum_invalid_value():
    """Test that invalid values raise ValueError."""
    with pytest.raises(ValueError):
        OddsFormat("Invalid Format")


def test_odds_format_enum_default():
    """Test that the default value is Decimal Odds."""
    assert OddsFormat.DECIMAL_ODDS.value == "Decimal Odds"
