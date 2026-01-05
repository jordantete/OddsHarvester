from enum import Enum
from typing import ClassVar

from src.utils.period_constants import BasketballPeriod, FootballPeriod, TennisPeriod
from src.utils.sport_market_constants import Sport


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


# Auto-register all sports on module import
SportPeriodRegistry.register(sport=Sport.FOOTBALL, period_enum=FootballPeriod, default_period=FootballPeriod.FULL_TIME)
SportPeriodRegistry.register(sport=Sport.TENNIS, period_enum=TennisPeriod, default_period=TennisPeriod.FULL_TIME)
SportPeriodRegistry.register(
    sport=Sport.BASKETBALL, period_enum=BasketballPeriod, default_period=BasketballPeriod.FULL_INCLUDING_OT
)
