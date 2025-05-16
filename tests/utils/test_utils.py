import pytest
from unittest.mock import patch
from src.utils.utils import get_supported_markets, is_running_in_docker
from src.utils.sport_market_constants import (
    Sport, FootballMarket, FootballOverUnderMarket, FootballEuropeanHandicapMarket, FootballAsianHandicapMarket,
    TennisMarket, TennisOverUnderSetsMarket, TennisOverUnderGamesMarket, TennisAsianHandicapGamesMarket, TennisCorrectScoreMarket,
    RugbyLeagueMarket, RugbyUnionMarket, IceHockeyMarket,
    RugbyOverUnderMarket, RugbyHandicapMarket, IceHockeyOverUnderMarket
)

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
}

@pytest.mark.parametrize("sport_enum, expected", [
    (Sport.FOOTBALL, EXPECTED_MARKETS[Sport.FOOTBALL]),
    (Sport.TENNIS, EXPECTED_MARKETS[Sport.TENNIS]),
    (Sport.RUGBY_LEAGUE, EXPECTED_MARKETS[Sport.RUGBY_LEAGUE]),
    (Sport.RUGBY_UNION, EXPECTED_MARKETS[Sport.RUGBY_UNION]),
    (Sport.ICE_HOCKEY, EXPECTED_MARKETS[Sport.ICE_HOCKEY]),
])
def test_get_supported_markets_enum(sport_enum, expected):
    assert get_supported_markets(sport_enum) == expected

@pytest.mark.parametrize("sport_str, expected", [
    ("football", EXPECTED_MARKETS[Sport.FOOTBALL]),
    ("tennis", EXPECTED_MARKETS[Sport.TENNIS]),
    ("rugby-league", EXPECTED_MARKETS[Sport.RUGBY_LEAGUE]),
    ("rugby-union", EXPECTED_MARKETS[Sport.RUGBY_UNION]),
    ("ice-hockey", EXPECTED_MARKETS[Sport.ICE_HOCKEY]),
])
def test_get_supported_markets_string(sport_str, expected):
    assert get_supported_markets(sport_str) == expected

@pytest.mark.parametrize("invalid_sport", ["invalid_sport", "handball", 123, None])
def test_get_supported_markets_invalid_sport(invalid_sport):
    with pytest.raises(ValueError, match="Invalid sport name:|Unsupported sport:"):
        get_supported_markets(invalid_sport)

@patch("os.path.exists", return_value=True)
def test_is_running_in_docker_true(mock_exists):
    assert is_running_in_docker() is True
    mock_exists.assert_called_once_with("/.dockerenv")

@patch("os.path.exists", return_value=False)
def test_is_running_in_docker_false(mock_exists):
    assert is_running_in_docker() is False
    mock_exists.assert_called_once_with("/.dockerenv")