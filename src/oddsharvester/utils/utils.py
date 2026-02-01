from enum import Enum
import logging
import os

from bs4 import BeautifulSoup

from oddsharvester.core.sport_period_registry import SportPeriodRegistry
from oddsharvester.utils.sport_market_constants import (
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


def validate_and_convert_period(period: str | None, sport: str | None):
    """
    Validate and convert period string to the appropriate sport-specific period enum.

    Args:
        period: The period CLI value to convert, or None to use sport's default.
        sport: The sport being scraped (used for validation).

    Returns:
        The validated period enum for the specific sport, or None if sport not provided or not registered.
    """
    # If no sport provided, cannot determine period
    if not sport:
        logger.error("No sport provided for period validation")
        return None

    # Check if sport has period configuration
    if not SportPeriodRegistry.is_sport_registered(sport.lower()):
        logger.error(f"Sport '{sport}' does not have period configuration registered")
        return None

    # Get the period enum class and default for this sport
    period_enum_cls = SportPeriodRegistry.get_period_enum(sport)
    default_period = SportPeriodRegistry.get_default_period(sport)

    # If no period provided, use sport's default
    if period is None:
        logger.info(f"No period specified, using default for {sport}: '{default_period.value}'")
        return default_period

    # Try to find matching period in the sport's enum
    for p in period_enum_cls:
        if p.value == period:
            return p

    # Period not found - log error and fallback to sport's default
    valid_periods = ", ".join(SportPeriodRegistry.get_all_cli_values(sport))
    logger.error(
        f"Invalid period '{period}' for sport '{sport}'. "
        f"Valid periods are: {valid_periods}. "
        f"Falling back to default: '{default_period.value}'"
    )
    return default_period


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
