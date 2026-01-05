from unittest.mock import patch

import pytest

from src.utils.period_constants import BasketballPeriod, FootballPeriod, TennisPeriod
from src.utils.sport_market_constants import (
    AmericanFootballAsianHandicapMarket,
    AmericanFootballMarket,
    AmericanFootballOverUnderMarket,
    BaseballMarket,
    BaseballOverUnderMarket,
    BasketballAsianHandicapMarket,
    BasketballMarket,
    BasketballOverUnderMarket,
    FootballAsianHandicapMarket,
    FootballEuropeanHandicapMarket,
    FootballMarket,
    FootballOverUnderMarket,
    IceHockeyMarket,
    IceHockeyOverUnderMarket,
    RugbyHandicapMarket,
    RugbyLeagueMarket,
    RugbyOverUnderMarket,
    RugbyUnionMarket,
    Sport,
    TennisAsianHandicapGamesMarket,
    TennisAsianHandicapSetsMarket,
    TennisCorrectScoreMarket,
    TennisMarket,
    TennisOverUnderGamesMarket,
    TennisOverUnderSetsMarket,
)
from src.utils.utils import clean_html_text, get_supported_markets, is_running_in_docker, validate_and_convert_period

EXPECTED_MARKETS = {
    Sport.FOOTBALL: [
        *[market.value for market in FootballMarket],
        *[market.value for market in FootballOverUnderMarket],
        *[market.value for market in FootballEuropeanHandicapMarket],
        *[market.value for market in FootballAsianHandicapMarket],
    ],
    Sport.TENNIS: [
        *[market.value for market in TennisMarket],
        *[market.value for market in TennisOverUnderSetsMarket],
        *[market.value for market in TennisOverUnderGamesMarket],
        *[market.value for market in TennisAsianHandicapGamesMarket],
        *[market.value for market in TennisAsianHandicapSetsMarket],
        *[market.value for market in TennisCorrectScoreMarket],
    ],
    Sport.BASKETBALL: [
        *[market.value for market in BasketballMarket],
        *[market.value for market in BasketballAsianHandicapMarket],
        *[market.value for market in BasketballOverUnderMarket],
    ],
    Sport.RUGBY_LEAGUE: [
        *[market.value for market in RugbyLeagueMarket],
        *[market.value for market in RugbyOverUnderMarket],
        *[market.value for market in RugbyHandicapMarket],
    ],
    Sport.RUGBY_UNION: [
        *[market.value for market in RugbyUnionMarket],
        *[market.value for market in RugbyOverUnderMarket],
        *[market.value for market in RugbyHandicapMarket],
    ],
    Sport.ICE_HOCKEY: [
        *[market.value for market in IceHockeyMarket],
        *[market.value for market in IceHockeyOverUnderMarket],
    ],
    Sport.BASEBALL: [
        *[market.value for market in BaseballMarket],
        *[market.value for market in BaseballOverUnderMarket],
    ],
    Sport.AMERICAN_FOOTBALL: [
        *[market.value for market in AmericanFootballMarket],
        *[market.value for market in AmericanFootballOverUnderMarket],
        *[market.value for market in AmericanFootballAsianHandicapMarket],
    ],
}


@pytest.mark.parametrize(
    ("sport_enum", "expected"),
    [
        (Sport.FOOTBALL, EXPECTED_MARKETS[Sport.FOOTBALL]),
        (Sport.TENNIS, EXPECTED_MARKETS[Sport.TENNIS]),
        (Sport.BASKETBALL, EXPECTED_MARKETS[Sport.BASKETBALL]),
        (Sport.RUGBY_LEAGUE, EXPECTED_MARKETS[Sport.RUGBY_LEAGUE]),
        (Sport.RUGBY_UNION, EXPECTED_MARKETS[Sport.RUGBY_UNION]),
        (Sport.ICE_HOCKEY, EXPECTED_MARKETS[Sport.ICE_HOCKEY]),
        (Sport.BASEBALL, EXPECTED_MARKETS[Sport.BASEBALL]),
        (Sport.AMERICAN_FOOTBALL, EXPECTED_MARKETS[Sport.AMERICAN_FOOTBALL]),
    ],
)
def test_get_supported_markets_enum(sport_enum, expected):
    """Test getting supported markets using Sport enum."""
    assert get_supported_markets(sport_enum) == expected


@pytest.mark.parametrize(
    ("sport_str", "expected"),
    [
        ("football", EXPECTED_MARKETS[Sport.FOOTBALL]),
        ("tennis", EXPECTED_MARKETS[Sport.TENNIS]),
        ("basketball", EXPECTED_MARKETS[Sport.BASKETBALL]),
        ("rugby-league", EXPECTED_MARKETS[Sport.RUGBY_LEAGUE]),
        ("rugby-union", EXPECTED_MARKETS[Sport.RUGBY_UNION]),
        ("ice-hockey", EXPECTED_MARKETS[Sport.ICE_HOCKEY]),
        ("baseball", EXPECTED_MARKETS[Sport.BASEBALL]),
        ("american-football", EXPECTED_MARKETS[Sport.AMERICAN_FOOTBALL]),
    ],
)
def test_get_supported_markets_string(sport_str, expected):
    """Test getting supported markets using string sport name."""
    assert get_supported_markets(sport_str) == expected


@pytest.mark.parametrize(
    ("sport_str_mixed_case", "expected"),
    [
        ("FooTbAlL", EXPECTED_MARKETS[Sport.FOOTBALL]),
        ("TENNIS", EXPECTED_MARKETS[Sport.TENNIS]),
        ("BaseBall", EXPECTED_MARKETS[Sport.BASEBALL]),
    ],
)
def test_get_supported_markets_case_insensitive(sport_str_mixed_case, expected):
    """Test that sport string input is case-insensitive."""
    assert get_supported_markets(sport_str_mixed_case) == expected


def test_get_supported_markets_unconfigured_sport():
    """Test handling of a sport that is a valid enum but not in the mapping."""
    with patch("src.utils.utils.SPORT_MARKETS_MAPPING", {}):
        with pytest.raises(ValueError) as excinfo:
            get_supported_markets(Sport.FOOTBALL)
        assert "Sport FOOTBALL is not configured in the market mapping" in str(excinfo.value)


def test_sport_markets_mapping_consistency():
    """Test that all sports in Sport enum are included in SPORT_MARKETS_MAPPING."""
    from src.utils.utils import SPORT_MARKETS_MAPPING

    for sport in Sport:
        assert sport in SPORT_MARKETS_MAPPING, f"Sport {sport.name} is missing from SPORT_MARKETS_MAPPING"


@patch("os.path.exists", return_value=True)
def test_is_running_in_docker_true(mock_exists):
    """Test detection of Docker environment when /.dockerenv exists."""
    assert is_running_in_docker() is True
    mock_exists.assert_called_once_with("/.dockerenv")


@patch("os.path.exists", return_value=False)
def test_is_running_in_docker_false(mock_exists):
    """Test detection of Docker environment when /.dockerenv doesn't exist."""
    assert is_running_in_docker() is False
    mock_exists.assert_called_once_with("/.dockerenv")


@patch("os.path.exists", side_effect=PermissionError("Permission denied"))
def test_is_running_in_docker_permission_error(mock_exists):
    """Test handling of permission error when checking for Docker environment."""
    # Should default to False when there's an error checking the file
    assert is_running_in_docker() is False
    mock_exists.assert_called_once_with("/.dockerenv")


def test_clean_html_text():
    # Test with None input
    assert clean_html_text(None) is None

    # Test with empty string
    assert clean_html_text("") == ""

    # Test with plain text (no HTML)
    assert clean_html_text("Simple text") == "Simple text"

    # Test with HTML tags
    assert clean_html_text("<div>Text content</div>") == "Text content"

    # Test with nested HTML tags
    assert clean_html_text("<div><p>Nested <strong>content</strong></p></div>") == "Nestedcontent"

    # Test with HTML entities
    assert clean_html_text("<div>Text &amp; content</div>") == "Text & content"

    # Test with the specific case from the issue
    html_with_sup = "6:3, 6:4, 1:6, 7:6<div><sup>4</sup></div>"
    expected_clean = "6:3, 6:4, 1:6, 7:64"
    assert clean_html_text(html_with_sup) == expected_clean

    # Test with complex HTML structure
    complex_html = """
    <div class="score">
        <span>Set 1: 6-3</span>
        <span>Set 2: 6-4</span>
        <span>Set 3: 1-6</span>
        <span>Set 4: 7-6<sup>4</sup></span>
    </div>
    """
    expected_complex = "Set 1: 6-3Set 2: 6-4Set 3: 1-6Set 4: 7-64"
    assert clean_html_text(complex_html) == expected_complex

    # Test with non-string input (should convert to string)
    assert clean_html_text(123) == "123"
    assert clean_html_text(True) == "True"


def test_validate_and_convert_period_valid_football():
    """Test valid period for football returns correct enum."""
    assert validate_and_convert_period("full_time", "football") == FootballPeriod.FULL_TIME
    assert validate_and_convert_period("1st_half", "football") == FootballPeriod.FIRST_HALF
    assert validate_and_convert_period("2nd_half", "football") == FootballPeriod.SECOND_HALF


def test_validate_and_convert_period_valid_tennis():
    """Test valid period for tennis returns correct enum."""
    assert validate_and_convert_period("full_time", "tennis") == TennisPeriod.FULL_TIME
    assert validate_and_convert_period("1st_set", "tennis") == TennisPeriod.FIRST_SET
    assert validate_and_convert_period("2nd_set", "tennis") == TennisPeriod.SECOND_SET


def test_validate_and_convert_period_valid_basketball():
    """Test valid period for basketball returns correct enum."""
    assert validate_and_convert_period("full_including_ot", "basketball") == BasketballPeriod.FULL_INCLUDING_OT
    assert validate_and_convert_period("1st_quarter", "basketball") == BasketballPeriod.FIRST_QUARTER
    assert validate_and_convert_period("4th_quarter", "basketball") == BasketballPeriod.FOURTH_QUARTER


def test_validate_and_convert_period_case_insensitive():
    """Test that sport comparison is case-insensitive."""
    assert validate_and_convert_period("1st_half", "FOOTBALL") == FootballPeriod.FIRST_HALF
    assert validate_and_convert_period("2nd_half", "Football") == FootballPeriod.SECOND_HALF


def test_validate_and_convert_period_invalid_defaults_to_sport_default():
    """Test that invalid period defaults to sport's default with error log."""
    # Invalid period for football should fallback to full_time
    result = validate_and_convert_period("invalid_period", "football")
    assert result == FootballPeriod.FULL_TIME

    # Invalid period for basketball should fallback to full_including_ot
    result = validate_and_convert_period("invalid_period", "basketball")
    assert result == BasketballPeriod.FULL_INCLUDING_OT


def test_validate_and_convert_period_wrong_period_for_sport():
    """Test that using wrong period for a sport falls back to that sport's default."""
    # Using tennis period for football should fallback to football default
    assert validate_and_convert_period("1st_set", "football") == FootballPeriod.FULL_TIME
    # Using football period for tennis should fallback to tennis default
    assert validate_and_convert_period("2nd_half", "tennis") == TennisPeriod.FULL_TIME


def test_validate_and_convert_period_unregistered_sport():
    """Test that unregistered sports return None."""
    result = validate_and_convert_period("full_time", "rugby-league")
    assert result is None


def test_validate_and_convert_period_none_sport():
    """Test that None sport returns None."""
    # Without sport, cannot determine period
    assert validate_and_convert_period("full_time", None) is None
    assert validate_and_convert_period("1st_half", None) is None


def test_validate_and_convert_period_none_period():
    """Test that None period returns sport's default."""
    # None period should return default for each sport
    assert validate_and_convert_period(None, "football") == FootballPeriod.FULL_TIME
    assert validate_and_convert_period(None, "tennis") == TennisPeriod.FULL_TIME
    assert validate_and_convert_period(None, "basketball") == BasketballPeriod.FULL_INCLUDING_OT
