from oddsharvester.core.sport_period_registry import SportPeriodRegistry
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

    def test_rugby_league_is_registered(self):
        """Test that rugby league is auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("rugby-league")
        assert SportPeriodRegistry.get_period_enum("rugby-league") == RugbyLeaguePeriod
        assert SportPeriodRegistry.get_default_period("rugby-league") == RugbyLeaguePeriod.FULL_TIME

    def test_rugby_union_is_registered(self):
        """Test that rugby union is auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("rugby-union")
        assert SportPeriodRegistry.get_period_enum("rugby-union") == RugbyUnionPeriod
        assert SportPeriodRegistry.get_default_period("rugby-union") == RugbyUnionPeriod.FULL_TIME

    def test_american_football_is_registered(self):
        """Test that american football is auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("american-football")
        assert SportPeriodRegistry.get_period_enum("american-football") == AmericanFootballPeriod
        assert SportPeriodRegistry.get_default_period("american-football") == AmericanFootballPeriod.FULL_INCLUDING_OT

    def test_ice_hockey_is_registered(self):
        """Test that ice hockey is auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("ice-hockey")
        assert SportPeriodRegistry.get_period_enum("ice-hockey") == IceHockeyPeriod
        assert SportPeriodRegistry.get_default_period("ice-hockey") == IceHockeyPeriod.FULL_TIME

    def test_baseball_is_registered(self):
        """Test that baseball is auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("baseball")
        assert SportPeriodRegistry.get_period_enum("baseball") == BaseballPeriod
        assert SportPeriodRegistry.get_default_period("baseball") == BaseballPeriod.FULL_INCLUDING_OT

    def test_all_sports_registered(self):
        """Test that all sports are auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("football")
        assert SportPeriodRegistry.is_sport_registered("tennis")
        assert SportPeriodRegistry.is_sport_registered("basketball")
        assert SportPeriodRegistry.is_sport_registered("rugby-league")
        assert SportPeriodRegistry.is_sport_registered("rugby-union")
        assert SportPeriodRegistry.is_sport_registered("american-football")
        assert SportPeriodRegistry.is_sport_registered("ice-hockey")
        assert SportPeriodRegistry.is_sport_registered("baseball")

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

    def test_rugby_league_cli_values(self):
        """Test that rugby league has the correct CLI values."""
        cli_values = SportPeriodRegistry.get_all_cli_values("rugby-league")
        assert "full_time" in cli_values
        assert "1st_half" in cli_values
        assert len(cli_values) == 2

    def test_american_football_cli_values(self):
        """Test that american football has the correct CLI values."""
        cli_values = SportPeriodRegistry.get_all_cli_values("american-football")
        assert "full_including_ot" in cli_values
        assert "1st_quarter" in cli_values
        assert "4th_quarter" in cli_values
        assert len(cli_values) == 7

    def test_ice_hockey_cli_values(self):
        """Test that ice hockey has the correct CLI values."""
        cli_values = SportPeriodRegistry.get_all_cli_values("ice-hockey")
        assert "full_time" in cli_values
        assert "1st_period" in cli_values
        assert "3rd_period" in cli_values
        assert len(cli_values) == 4

    def test_baseball_cli_values(self):
        """Test that baseball has the correct CLI values."""
        cli_values = SportPeriodRegistry.get_all_cli_values("baseball")
        assert "full_including_ot" in cli_values
        assert "full_time" in cli_values
        assert "1st_half" in cli_values
        assert len(cli_values) == 3


class TestSportPeriodRegistryConversion:
    """Tests for SportPeriodRegistry internal value conversion."""

    def test_from_internal_value_football(self):
        """Test converting internal values to football enum."""
        assert SportPeriodRegistry.from_internal_value("FullTime", "football") == FootballPeriod.FULL_TIME
        assert SportPeriodRegistry.from_internal_value("FirstHalf", "football") == FootballPeriod.FIRST_HALF
        assert SportPeriodRegistry.from_internal_value("SecondHalf", "football") == FootballPeriod.SECOND_HALF

    def test_from_internal_value_tennis(self):
        """Test converting internal values to tennis enum."""
        assert SportPeriodRegistry.from_internal_value("FullTime", "tennis") == TennisPeriod.FULL_TIME
        assert SportPeriodRegistry.from_internal_value("FirstSet", "tennis") == TennisPeriod.FIRST_SET
        assert SportPeriodRegistry.from_internal_value("SecondSet", "tennis") == TennisPeriod.SECOND_SET

    def test_from_internal_value_basketball(self):
        """Test converting internal values to basketball enum."""
        assert (
            SportPeriodRegistry.from_internal_value("FullIncludingOT", "basketball")
            == BasketballPeriod.FULL_INCLUDING_OT
        )
        assert SportPeriodRegistry.from_internal_value("FirstQuarter", "basketball") == BasketballPeriod.FIRST_QUARTER
        assert SportPeriodRegistry.from_internal_value("FourthQuarter", "basketball") == BasketballPeriod.FOURTH_QUARTER

    def test_from_internal_value_rugby_league(self):
        """Test converting internal values to rugby league enum."""
        assert SportPeriodRegistry.from_internal_value("FullTime", "rugby-league") == RugbyLeaguePeriod.FULL_TIME
        assert SportPeriodRegistry.from_internal_value("FirstHalf", "rugby-league") == RugbyLeaguePeriod.FIRST_HALF

    def test_from_internal_value_american_football(self):
        """Test converting internal values to american football enum."""
        assert (
            SportPeriodRegistry.from_internal_value("FullIncludingOT", "american-football")
            == AmericanFootballPeriod.FULL_INCLUDING_OT
        )
        assert (
            SportPeriodRegistry.from_internal_value("FirstQuarter", "american-football")
            == AmericanFootballPeriod.FIRST_QUARTER
        )

    def test_from_internal_value_ice_hockey(self):
        """Test converting internal values to ice hockey enum."""
        assert SportPeriodRegistry.from_internal_value("FullTime", "ice-hockey") == IceHockeyPeriod.FULL_TIME
        assert SportPeriodRegistry.from_internal_value("FirstPeriod", "ice-hockey") == IceHockeyPeriod.FIRST_PERIOD
        assert SportPeriodRegistry.from_internal_value("ThirdPeriod", "ice-hockey") == IceHockeyPeriod.THIRD_PERIOD

    def test_from_internal_value_baseball(self):
        """Test converting internal values to baseball enum."""
        assert (
            SportPeriodRegistry.from_internal_value("FullIncludingOT", "baseball") == BaseballPeriod.FULL_INCLUDING_OT
        )
        assert SportPeriodRegistry.from_internal_value("FullTime", "baseball") == BaseballPeriod.FULL_TIME
        assert SportPeriodRegistry.from_internal_value("FirstHalf", "baseball") == BaseballPeriod.FIRST_HALF

    def test_from_internal_value_invalid(self):
        """Test that invalid internal values return None."""
        assert SportPeriodRegistry.from_internal_value("InvalidValue", "football") is None
        assert SportPeriodRegistry.from_internal_value("SecondSet", "football") is None  # Wrong sport

    def test_from_internal_value_unregistered_sport(self):
        """Test that unregistered sports return None."""
        assert SportPeriodRegistry.from_internal_value("FullTime", "cricket") is None

    def test_from_internal_value_none_sport(self):
        """Test that None sport returns None."""
        assert SportPeriodRegistry.from_internal_value("FullTime", None) is None

    def test_from_internal_value_case_insensitive(self):
        """Test that sport comparison is case-insensitive."""
        assert SportPeriodRegistry.from_internal_value("FullTime", "FOOTBALL") == FootballPeriod.FULL_TIME
        assert SportPeriodRegistry.from_internal_value("FirstSet", "Tennis") == TennisPeriod.FIRST_SET
