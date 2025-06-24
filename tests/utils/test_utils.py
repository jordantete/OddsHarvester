from unittest.mock import patch

import pytest

from src.utils.sport_market_constants import (
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
    TennisCorrectScoreMarket,
    TennisMarket,
    TennisOverUnderGamesMarket,
    TennisOverUnderSetsMarket,
)
from src.utils.utils import get_supported_markets, is_running_in_docker

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
