from src.core.sport_period_registry import SportPeriodRegistry
from src.utils.period_constants import BasketballPeriod, FootballPeriod, TennisPeriod
from src.utils.sport_market_constants import Sport


class TestSportPeriodRegistry:
    """Tests for the SportPeriodRegistry class."""

    def test_football_is_registered(self):
        """Test that football is auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("football")
        assert SportPeriodRegistry.get_period_enum("football") == FootballPeriod
        assert SportPeriodRegistry.get_default_period("football") == FootballPeriod.FULL_TIME

    def test_tennis_is_registered(self):
        """Test that tennis is auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("tennis")
        assert SportPeriodRegistry.get_period_enum("tennis") == TennisPeriod
        assert SportPeriodRegistry.get_default_period("tennis") == TennisPeriod.FULL_TIME

    def test_basketball_is_registered(self):
        """Test that basketball is auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("basketball")
        assert SportPeriodRegistry.get_period_enum("basketball") == BasketballPeriod
        assert SportPeriodRegistry.get_default_period("basketball") == BasketballPeriod.FULL_INCLUDING_OT

    def test_all_sports_registered(self):
        """Test that all sports are auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("football")
        assert SportPeriodRegistry.is_sport_registered("tennis")
        assert SportPeriodRegistry.is_sport_registered("basketball")

    def test_football_cli_values(self):
        """Test that football has the correct CLI values."""
        cli_values = SportPeriodRegistry.get_all_cli_values("football")
        assert "full_time" in cli_values
        assert "1st_half" in cli_values
        assert "2nd_half" in cli_values
        assert len(cli_values) == 3

    def test_tennis_cli_values(self):
        """Test that tennis has the correct CLI values."""
        cli_values = SportPeriodRegistry.get_all_cli_values("tennis")
        assert "full_time" in cli_values
        assert "1st_set" in cli_values
        assert "2nd_set" in cli_values
        assert len(cli_values) == 3

    def test_basketball_cli_values(self):
        """Test that basketball has the correct CLI values."""
        cli_values = SportPeriodRegistry.get_all_cli_values("basketball")
        assert "full_including_ot" in cli_values
        assert "1st_quarter" in cli_values
        assert "4th_quarter" in cli_values
        assert len(cli_values) == 7

    def test_get_unregistered_sport_returns_none(self):
        """Test that getting an unregistered sport returns None."""
        assert SportPeriodRegistry.get_period_enum("unknown_sport") is None
        assert SportPeriodRegistry.get_default_period("unknown_sport") is None
        assert SportPeriodRegistry.get_all_cli_values("unknown_sport") == []

    def test_register_new_sport(self):
        """Test manually registering a new sport."""
        # Create a simple enum for testing
        from enum import Enum

        class TestPeriod(Enum):
            FULL = "full"

        SportPeriodRegistry.register(Sport.ICE_HOCKEY, TestPeriod, TestPeriod.FULL)

        assert SportPeriodRegistry.is_sport_registered("ice-hockey")
        assert SportPeriodRegistry.get_period_enum("ice-hockey") == TestPeriod
        assert SportPeriodRegistry.get_default_period("ice-hockey") == TestPeriod.FULL
