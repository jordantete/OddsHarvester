from enum import Enum


class CommandEnum(str, Enum):
    UPCOMING_MATCHES = "scrape_upcoming"
    HISTORIC = "scrape_historic"
