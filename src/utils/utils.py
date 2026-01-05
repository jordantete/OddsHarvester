from enum import Enum
import logging
import os

from bs4 import BeautifulSoup

from src.utils.period_constants import MatchPeriod
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

logger = logging.getLogger(__name__)

SPORT_MARKETS_MAPPING: dict[Sport, list[type[Enum]]] = {
    Sport.FOOTBALL: [
        FootballMarket,
        FootballOverUnderMarket,
        FootballEuropeanHandicapMarket,
        FootballAsianHandicapMarket,
    ],
    Sport.TENNIS: [
        TennisMarket,
        TennisOverUnderSetsMarket,
        TennisOverUnderGamesMarket,
        TennisAsianHandicapGamesMarket,
        TennisAsianHandicapSetsMarket,
        TennisCorrectScoreMarket,
    ],
    Sport.BASKETBALL: [BasketballMarket, BasketballAsianHandicapMarket, BasketballOverUnderMarket],
    Sport.RUGBY_LEAGUE: [RugbyLeagueMarket, RugbyOverUnderMarket, RugbyHandicapMarket],
    Sport.RUGBY_UNION: [RugbyUnionMarket, RugbyOverUnderMarket, RugbyHandicapMarket],
    Sport.ICE_HOCKEY: [IceHockeyMarket, IceHockeyOverUnderMarket],
    Sport.BASEBALL: [BaseballMarket, BaseballOverUnderMarket],
    Sport.AMERICAN_FOOTBALL: [
        AmericanFootballMarket,
        AmericanFootballOverUnderMarket,
        AmericanFootballAsianHandicapMarket,
    ],
}


def get_supported_markets(sport: Sport | str) -> list[str]:
    """
    Retrieve the list of supported markets for a given sport.

    Args:
        sport (Union[Sport, str]): The sport to get markets for. Can be a Sport enum or a string.

    Returns:
        List[str]: A list of market names supported for the given sport.

    Raises:
        ValueError: If the sport is not supported or the input is invalid.
    """
    if isinstance(sport, str):
        try:
            sport = Sport(sport.lower())
        except ValueError:
            valid_sports = [s.value for s in Sport]
            raise ValueError(f"Invalid sport name: {sport}. Expected one of {valid_sports}.") from None

    if sport not in SPORT_MARKETS_MAPPING:
        raise ValueError(f"Sport {sport.name} is not configured in the market mapping")

    market_list = []
    for market_enum in SPORT_MARKETS_MAPPING[sport]:
        market_list.extend([market.value for market in market_enum])

    return market_list


def is_running_in_docker() -> bool:
    """
    Detect if the app is running inside a Docker container.

    Returns:
        bool: True if running in Docker, False otherwise.
    """
    try:
        return os.path.exists("/.dockerenv")
    except (PermissionError, OSError) as e:
        logger.warning(f"Error checking Docker environment: {e!s}")
        return False


def validate_and_convert_period(period: str, sport: str | None) -> MatchPeriod:
    """
    Validate and convert period string to MatchPeriod enum.

    Args:
        period: The period CLI value to convert.
        sport: The sport being scraped (used for validation).

    Returns:
        MatchPeriod: The validated period enum.
    """
    # Convert period string to MatchPeriod enum
    try:
        period_enum = MatchPeriod.from_cli_value(period)
    except ValueError:
        logger.warning(f"Invalid period '{period}', defaulting to full_time")
        period_enum = MatchPeriod.FULL_TIME

    # Only apply non-default period for football
    if sport and sport.lower() != "football" and period_enum != MatchPeriod.FULL_TIME:
        logger.warning(
            f"Period selection '{period}' is only supported for football. "
            f"Using default period (full_time) for sport '{sport}'."
        )
        period_enum = MatchPeriod.FULL_TIME

    return period_enum


def clean_html_text(html_content: str | None) -> str | None:
    """
    Remove HTML tags from text content while preserving the text.

    Args:
        html_content (Optional[str]): HTML content that may contain tags.

    Returns:
        Optional[str]: Clean text content without HTML tags, or None if input is None.
    """
    if html_content is None:
        return None

    if not isinstance(html_content, str):
        html_content = str(html_content)

    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(strip=True)
