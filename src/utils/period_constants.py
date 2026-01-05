from enum import Enum


class FootballPeriod(Enum):
    """Periods available for football matches."""

    FULL_TIME = "full_time"
    FIRST_HALF = "1st_half"
    SECOND_HALF = "2nd_half"

    @classmethod
    def get_display_label(cls, period: "FootballPeriod") -> str:
        """Get the display label for OddsPortal UI."""
        labels = {
            cls.FULL_TIME: "Full Time",
            cls.FIRST_HALF: "1st Half",
            cls.SECOND_HALF: "2nd Half",
        }
        return labels[period]

    @classmethod
    def get_internal_value(cls, period: "FootballPeriod") -> str:
        """Get the internal value used in scraper functions."""
        internal_values = {
            cls.FULL_TIME: "FullTime",
            cls.FIRST_HALF: "FirstHalf",
            cls.SECOND_HALF: "SecondHalf",
        }
        return internal_values[period]


class TennisPeriod(Enum):
    """Periods available for tennis matches."""

    FULL_TIME = "full_time"
    FIRST_SET = "1st_set"
    SECOND_SET = "2nd_set"

    @classmethod
    def get_display_label(cls, period: "TennisPeriod") -> str:
        """Get the display label for OddsPortal UI."""
        labels = {
            cls.FULL_TIME: "Full Time",
            cls.FIRST_SET: "1st Set",
            cls.SECOND_SET: "2nd Set",
        }
        return labels[period]

    @classmethod
    def get_internal_value(cls, period: "TennisPeriod") -> str:
        """Get the internal value used in scraper functions."""
        internal_values = {
            cls.FULL_TIME: "FullTime",
            cls.FIRST_SET: "FirstSet",
            cls.SECOND_SET: "SecondSet",
        }
        return internal_values[period]


class BasketballPeriod(Enum):
    """Periods available for basketball matches."""

    FULL_INCLUDING_OT = "full_including_ot"
    FIRST_HALF = "1st_half"
    SECOND_HALF = "2nd_half"
    FIRST_QUARTER = "1st_quarter"
    SECOND_QUARTER = "2nd_quarter"
    THIRD_QUARTER = "3rd_quarter"
    FOURTH_QUARTER = "4th_quarter"

    @classmethod
    def get_display_label(cls, period: "BasketballPeriod") -> str:
        """Get the display label for OddsPortal UI."""
        labels = {
            cls.FULL_INCLUDING_OT: "FT including OT",
            cls.FIRST_HALF: "1st Half",
            cls.SECOND_HALF: "2nd Half",
            cls.FIRST_QUARTER: "1st Quarter",
            cls.SECOND_QUARTER: "2nd Quarter",
            cls.THIRD_QUARTER: "3rd Quarter",
            cls.FOURTH_QUARTER: "4th Quarter",
        }
        return labels[period]

    @classmethod
    def get_internal_value(cls, period: "BasketballPeriod") -> str:
        """Get the internal value used in scraper functions."""
        internal_values = {
            cls.FULL_INCLUDING_OT: "FullIncludingOT",
            cls.FIRST_HALF: "FirstHalf",
            cls.SECOND_HALF: "SecondHalf",
            cls.FIRST_QUARTER: "FirstQuarter",
            cls.SECOND_QUARTER: "SecondQuarter",
            cls.THIRD_QUARTER: "ThirdQuarter",
            cls.FOURTH_QUARTER: "FourthQuarter",
        }
        return internal_values[period]
