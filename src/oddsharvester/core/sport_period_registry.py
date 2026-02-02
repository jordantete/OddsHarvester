from enum import Enum
import logging
from typing import ClassVar

from oddsharvester.utils.period_constants import (
    AmericanFootballPeriod,
    BaseballPeriod,
    BasketballPeriod,
    FootballPeriod,
    IceHockeyPeriod,
    RugbyLeaguePeriod,
    RugbyUnionPeriod,
    TennisPeriod,
)
from oddsharvester.utils.sport_market_constants import Sport

logger = logging.getLogger(__name__)


class SportPeriodRegistry:
    """
    Registry to store and manage period configurations for each sport.

    Auto-registers all supported sports on module import.
    """

    _registry: ClassVar[dict] = {}

    @classmethod
    def register(cls, sport: Sport, period_enum: type[Enum], default_period: Enum):
        """
        Register a period enum for a sport.

        Args:
            sport: The sport enum.
            period_enum: The period enum class for this sport.
            default_period: The default period for this sport.
        """
        cls._registry[sport.value] = {"enum": period_enum, "default": default_period}

    @classmethod
    def get_period_enum(cls, sport: str) -> type[Enum] | None:
        """
        Get the period enum class for a sport.

        Args:
            sport: The sport name (e.g., 'football', 'tennis').

        Returns:
            The period enum class, or None if not registered.
        """
        config = cls._registry.get(sport.lower())
        return config["enum"] if config else None

    @classmethod
    def get_default_period(cls, sport: str) -> Enum | None:
        """
        Get the default period for a sport.

        Args:
            sport: The sport name (e.g., 'football', 'tennis').

        Returns:
            The default period enum, or None if not registered.
        """
        config = cls._registry.get(sport.lower())
        return config["default"] if config else None

    @classmethod
    def get_all_cli_values(cls, sport: str) -> list[str]:
        """
        Get all valid CLI values for a sport's periods.

        Args:
            sport: The sport name (e.g., 'football', 'tennis').

        Returns:
            List of CLI values, or empty list if sport not registered.
        """
        period_enum = cls.get_period_enum(sport)
        if not period_enum:
            return []
        return [period.value for period in period_enum]

    @classmethod
    def is_sport_registered(cls, sport: str) -> bool:
        """Check if a sport has period configuration registered."""
        return sport.lower() in cls._registry

    @classmethod
    def from_internal_value(cls, internal_value: str, sport: str) -> Enum | None:
        """
        Convert internal period value (e.g., 'FullTime', 'FirstSet') to sport-specific enum.

        Args:
            internal_value (str): Internal value like "FullTime", "FirstSet", etc.
            sport (str): The sport name (e.g., "football", "tennis").

        Returns:
            Enum | None: The period enum member, or None if conversion fails.
        """
        if not sport:
            logger.warning("No sport provided for internal value conversion.")
            return None

        period_enum_class = cls.get_period_enum(sport.lower())
        if not period_enum_class:
            logger.warning(f"Sport '{sport}' does not have period configuration.")
            return None

        # Build reverse mapping from internal value to enum member
        internal_to_enum = {period_enum_class.get_internal_value(p): p for p in period_enum_class}

        if internal_value not in internal_to_enum:
            valid_values = ", ".join(internal_to_enum.keys())
            logger.warning(
                f"Invalid internal value '{internal_value}' for sport '{sport}'. Valid values: {valid_values}"
            )
            return None

        return internal_to_enum[internal_value]


# Auto-register all sports on module import
SportPeriodRegistry.register(sport=Sport.FOOTBALL, period_enum=FootballPeriod, default_period=FootballPeriod.FULL_TIME)
SportPeriodRegistry.register(sport=Sport.TENNIS, period_enum=TennisPeriod, default_period=TennisPeriod.FULL_TIME)
SportPeriodRegistry.register(
    sport=Sport.BASKETBALL, period_enum=BasketballPeriod, default_period=BasketballPeriod.FULL_INCLUDING_OT
)
SportPeriodRegistry.register(
    sport=Sport.RUGBY_LEAGUE, period_enum=RugbyLeaguePeriod, default_period=RugbyLeaguePeriod.FULL_TIME
)
SportPeriodRegistry.register(
    sport=Sport.RUGBY_UNION, period_enum=RugbyUnionPeriod, default_period=RugbyUnionPeriod.FULL_TIME
)
SportPeriodRegistry.register(
    sport=Sport.AMERICAN_FOOTBALL,
    period_enum=AmericanFootballPeriod,
    default_period=AmericanFootballPeriod.FULL_INCLUDING_OT,
)
SportPeriodRegistry.register(
    sport=Sport.ICE_HOCKEY, period_enum=IceHockeyPeriod, default_period=IceHockeyPeriod.FULL_TIME
)
SportPeriodRegistry.register(
    sport=Sport.BASEBALL, period_enum=BaseballPeriod, default_period=BaseballPeriod.FULL_INCLUDING_OT
)
