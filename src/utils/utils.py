import os
from enum import Enum
from typing import Dict, List, Type
from src.utils.sport_market_constants import (
    Sport, FootballMarket, FootballOverUnderMarket, FootballEuropeanHandicapMarket, FootballAsianHandicapMarket,
    TennisMarket, TennisOverUnderSetsMarket, TennisOverUnderGamesMarket, TennisAsianHandicapGamesMarket, TennisCorrectScoreMarket,
    BasketballMarket, BasketballAsianHandicapMarket, BasketballOverUnderMarket,
    RugbyLeagueMarket, RugbyUnionMarket
)

SPORT_MARKETS_MAPPING: Dict[Sport, List[Type[Enum]]] = {
    Sport.FOOTBALL: [FootballMarket, FootballOverUnderMarket, FootballEuropeanHandicapMarket, FootballAsianHandicapMarket],
    Sport.TENNIS: [TennisMarket, TennisOverUnderSetsMarket, TennisOverUnderGamesMarket, TennisAsianHandicapGamesMarket, TennisCorrectScoreMarket],
    Sport.BASKETBALL: [BasketballMarket, BasketballAsianHandicapMarket, BasketballOverUnderMarket],
    Sport.RUGBY_LEAGUE: [RugbyLeagueMarket],
    Sport.RUGBY_UNION: [RugbyUnionMarket],
}

def get_supported_markets(sport: Sport) -> List[str]:
    """Retrieve the list of supported markets for a given sport."""
    if isinstance(sport, str):
        try:
            sport = Sport(sport.lower())
        except ValueError:
            raise ValueError(f"Invalid sport name: {sport}. Expected one of {[s.value for s in Sport]}.")
        
    if sport not in SPORT_MARKETS_MAPPING:
        raise ValueError(f"Unsupported sport: {sport}")

    market_list = []
    for market_enum in SPORT_MARKETS_MAPPING[sport]:
        market_list.extend([market.value for market in market_enum])
    
    return market_list

def is_running_in_docker() -> bool:
    """Detect if the app is running inside a Docker container."""
    return os.path.exists('/.dockerenv')