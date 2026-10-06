from enum import StrEnum


class CommandEnum(StrEnum):
    UPCOMING_MATCHES = "scrape_upcoming"
    HISTORIC = "scrape_historic"
    LIVE = "scrape_live"
