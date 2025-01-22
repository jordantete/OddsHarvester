from enum import Enum

class CommandEnum(str, Enum):
    UPCOMING_MATCHES = "scrape-upcoming"
    HISTORIC = "scrape-historic"