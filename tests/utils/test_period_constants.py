from src.utils.period_constants import BasketballPeriod, FootballPeriod, TennisPeriod


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
