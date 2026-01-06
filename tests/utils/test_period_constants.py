from src.utils.period_constants import (
    AmericanFootballPeriod,
    BaseballPeriod,
    BasketballPeriod,
    FootballPeriod,
    IceHockeyPeriod,
    RugbyLeaguePeriod,
    RugbyUnionPeriod,
    TennisPeriod,
)


class TestFootballPeriod:
    """Tests for the FootballPeriod enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert FootballPeriod.FULL_TIME.value == "full_time"
        assert FootballPeriod.FIRST_HALF.value == "1st_half"
        assert FootballPeriod.SECOND_HALF.value == "2nd_half"

    def test_get_display_label(self):
        """Test getting display labels for UI."""
        assert FootballPeriod.get_display_label(FootballPeriod.FULL_TIME) == "Full Time"
        assert FootballPeriod.get_display_label(FootballPeriod.FIRST_HALF) == "1st Half"
        assert FootballPeriod.get_display_label(FootballPeriod.SECOND_HALF) == "2nd Half"

    def test_get_internal_value(self):
        """Test getting internal values for scraper functions."""
        assert FootballPeriod.get_internal_value(FootballPeriod.FULL_TIME) == "FullTime"
        assert FootballPeriod.get_internal_value(FootballPeriod.FIRST_HALF) == "FirstHalf"
        assert FootballPeriod.get_internal_value(FootballPeriod.SECOND_HALF) == "SecondHalf"


class TestTennisPeriod:
    """Tests for the TennisPeriod enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert TennisPeriod.FULL_TIME.value == "full_time"
        assert TennisPeriod.FIRST_SET.value == "1st_set"

    def test_get_display_label(self):
        """Test getting display labels for UI."""
        assert TennisPeriod.get_display_label(TennisPeriod.FULL_TIME) == "Full Time"
        assert TennisPeriod.get_display_label(TennisPeriod.FIRST_SET) == "1st Set"

    def test_get_internal_value(self):
        """Test getting internal values for scraper functions."""
        assert TennisPeriod.get_internal_value(TennisPeriod.FULL_TIME) == "FullTime"
        assert TennisPeriod.get_internal_value(TennisPeriod.FIRST_SET) == "FirstSet"


class TestBasketballPeriod:
    """Tests for the BasketballPeriod enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert BasketballPeriod.FULL_INCLUDING_OT.value == "full_including_ot"
        assert BasketballPeriod.FIRST_HALF.value == "1st_half"
        assert BasketballPeriod.FIRST_QUARTER.value == "1st_quarter"
        assert BasketballPeriod.FOURTH_QUARTER.value == "4th_quarter"

    def test_get_display_label(self):
        """Test getting display labels for UI."""
        assert BasketballPeriod.get_display_label(BasketballPeriod.FULL_INCLUDING_OT) == "FT including OT"
        assert BasketballPeriod.get_display_label(BasketballPeriod.FIRST_HALF) == "1st Half"
        assert BasketballPeriod.get_display_label(BasketballPeriod.FIRST_QUARTER) == "1st Quarter"

    def test_get_internal_value(self):
        """Test getting internal values for scraper functions."""
        assert BasketballPeriod.get_internal_value(BasketballPeriod.FULL_INCLUDING_OT) == "FullIncludingOT"
        assert BasketballPeriod.get_internal_value(BasketballPeriod.FIRST_HALF) == "FirstHalf"
        assert BasketballPeriod.get_internal_value(BasketballPeriod.FIRST_QUARTER) == "FirstQuarter"


class TestRugbyLeaguePeriod:
    """Tests for the RugbyLeaguePeriod enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert RugbyLeaguePeriod.FULL_TIME.value == "full_time"
        assert RugbyLeaguePeriod.FIRST_HALF.value == "1st_half"

    def test_get_display_label(self):
        """Test getting display labels for UI."""
        assert RugbyLeaguePeriod.get_display_label(RugbyLeaguePeriod.FULL_TIME) == "Full Time"
        assert RugbyLeaguePeriod.get_display_label(RugbyLeaguePeriod.FIRST_HALF) == "1st Half"

    def test_get_internal_value(self):
        """Test getting internal values for scraper functions."""
        assert RugbyLeaguePeriod.get_internal_value(RugbyLeaguePeriod.FULL_TIME) == "FullTime"
        assert RugbyLeaguePeriod.get_internal_value(RugbyLeaguePeriod.FIRST_HALF) == "FirstHalf"


class TestRugbyUnionPeriod:
    """Tests for the RugbyUnionPeriod enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert RugbyUnionPeriod.FULL_TIME.value == "full_time"
        assert RugbyUnionPeriod.FIRST_HALF.value == "1st_half"

    def test_get_display_label(self):
        """Test getting display labels for UI."""
        assert RugbyUnionPeriod.get_display_label(RugbyUnionPeriod.FULL_TIME) == "Full Time"
        assert RugbyUnionPeriod.get_display_label(RugbyUnionPeriod.FIRST_HALF) == "1st Half"

    def test_get_internal_value(self):
        """Test getting internal values for scraper functions."""
        assert RugbyUnionPeriod.get_internal_value(RugbyUnionPeriod.FULL_TIME) == "FullTime"
        assert RugbyUnionPeriod.get_internal_value(RugbyUnionPeriod.FIRST_HALF) == "FirstHalf"


class TestAmericanFootballPeriod:
    """Tests for the AmericanFootballPeriod enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert AmericanFootballPeriod.FULL_INCLUDING_OT.value == "full_including_ot"
        assert AmericanFootballPeriod.FIRST_HALF.value == "1st_half"
        assert AmericanFootballPeriod.FIRST_QUARTER.value == "1st_quarter"

    def test_get_display_label(self):
        """Test getting display labels for UI."""
        assert AmericanFootballPeriod.get_display_label(AmericanFootballPeriod.FULL_INCLUDING_OT) == "FT including OT"
        assert AmericanFootballPeriod.get_display_label(AmericanFootballPeriod.FIRST_HALF) == "1st Half"
        assert AmericanFootballPeriod.get_display_label(AmericanFootballPeriod.FIRST_QUARTER) == "1st Quarter"

    def test_get_internal_value(self):
        """Test getting internal values for scraper functions."""
        assert AmericanFootballPeriod.get_internal_value(AmericanFootballPeriod.FULL_INCLUDING_OT) == "FullIncludingOT"
        assert AmericanFootballPeriod.get_internal_value(AmericanFootballPeriod.FIRST_HALF) == "FirstHalf"
        assert AmericanFootballPeriod.get_internal_value(AmericanFootballPeriod.FIRST_QUARTER) == "FirstQuarter"


class TestIceHockeyPeriod:
    """Tests for the IceHockeyPeriod enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert IceHockeyPeriod.FULL_TIME.value == "full_time"
        assert IceHockeyPeriod.FIRST_PERIOD.value == "1st_period"
        assert IceHockeyPeriod.THIRD_PERIOD.value == "3rd_period"

    def test_get_display_label(self):
        """Test getting display labels for UI."""
        assert IceHockeyPeriod.get_display_label(IceHockeyPeriod.FULL_TIME) == "Full Time"
        assert IceHockeyPeriod.get_display_label(IceHockeyPeriod.FIRST_PERIOD) == "1st Period"
        assert IceHockeyPeriod.get_display_label(IceHockeyPeriod.THIRD_PERIOD) == "3rd Period"

    def test_get_internal_value(self):
        """Test getting internal values for scraper functions."""
        assert IceHockeyPeriod.get_internal_value(IceHockeyPeriod.FULL_TIME) == "FullTime"
        assert IceHockeyPeriod.get_internal_value(IceHockeyPeriod.FIRST_PERIOD) == "FirstPeriod"
        assert IceHockeyPeriod.get_internal_value(IceHockeyPeriod.THIRD_PERIOD) == "ThirdPeriod"


class TestBaseballPeriod:
    """Tests for the BaseballPeriod enum."""

    def test_enum_values(self):
        """Test that enum values are correct."""
        assert BaseballPeriod.FULL_INCLUDING_OT.value == "full_including_ot"
        assert BaseballPeriod.FULL_TIME.value == "full_time"
        assert BaseballPeriod.FIRST_HALF.value == "1st_half"

    def test_get_display_label(self):
        """Test getting display labels for UI."""
        assert BaseballPeriod.get_display_label(BaseballPeriod.FULL_INCLUDING_OT) == "FT including OT"
        assert BaseballPeriod.get_display_label(BaseballPeriod.FULL_TIME) == "Full Time"
        assert BaseballPeriod.get_display_label(BaseballPeriod.FIRST_HALF) == "1st Half"

    def test_get_internal_value(self):
        """Test getting internal values for scraper functions."""
        assert BaseballPeriod.get_internal_value(BaseballPeriod.FULL_INCLUDING_OT) == "FullIncludingOT"
        assert BaseballPeriod.get_internal_value(BaseballPeriod.FULL_TIME) == "FullTime"
        assert BaseballPeriod.get_internal_value(BaseballPeriod.FIRST_HALF) == "FirstHalf"
