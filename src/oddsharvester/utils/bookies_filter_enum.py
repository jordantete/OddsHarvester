from enum import Enum


class BookiesFilter(Enum):
    ALL = "all"
    CLASSIC = "classic"
    CRYPTO = "crypto"

    @classmethod
    def get_display_label(cls, filter_value: "BookiesFilter") -> str:
        labels = {
            cls.ALL: "All Bookies",
            cls.CLASSIC: "Classic Bookies",
            cls.CRYPTO: "Crypto Bookies",
        }
        return labels[filter_value]
