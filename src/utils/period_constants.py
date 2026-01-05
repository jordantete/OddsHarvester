from enum import Enum


class MatchPeriod(Enum):
    FULL_TIME = "full_time"
    FIRST_HALF = "1st_half"
    SECOND_HALF = "2nd_half"

    @classmethod
    def get_display_label(cls, period: "MatchPeriod") -> str:
        labels = {
            cls.FULL_TIME: "Full Time",
            cls.FIRST_HALF: "1st Half",
            cls.SECOND_HALF: "2nd Half",
        }
        return labels[period]

    @classmethod
    def get_internal_value(cls, period: "MatchPeriod") -> str:
        internal_values = {
            cls.FULL_TIME: "FullTime",
            cls.FIRST_HALF: "FirstHalf",
            cls.SECOND_HALF: "SecondHalf",
        }
        return internal_values[period]

    @classmethod
    def from_cli_value(cls, cli_value: str) -> "MatchPeriod":
        for period in cls:
            if period.value == cli_value:
                return period
        raise ValueError(f"Invalid period value: '{cli_value}'")

    @classmethod
    def get_all_cli_values(cls) -> list[str]:
        return [period.value for period in cls]
