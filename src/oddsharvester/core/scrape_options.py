"""The settings of one scrape run."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.command_enum import CommandEnum
from oddsharvester.utils.constants import DEFAULT_REQUEST_DELAY_S
from oddsharvester.utils.sport_market_constants import Sport
from oddsharvester.utils.utils import validate_and_convert_period


@dataclass(frozen=True)
class ScrapeOptions:
    """Everything `run_scrape` needs, with the names and defaults `run_scraper` has always taken.

    Strings and enums are both accepted and normalized once, here: `command`, `bookies_filter` and `period`
    become enums (the period that of the sport, or its default when None), `sport` its site value and
    `proxy_url` a tuple of URLs. An unknown command or bookies filter raises ValueError. The proxy settings
    stay out of the repr, so a logged ScrapeOptions never shows a credential.
    """

    command: CommandEnum | str
    match_links: list[str] | None = None
    sport: Sport | str | None = None
    date: str | None = None
    leagues: list[str] | None = None
    seasons: list[str] | None = None
    markets: list[str] | None = None
    max_pages: int | None = None
    proxy_url: str | list[str] | tuple[str, ...] | None = field(default=None, repr=False)
    proxy_user: str | None = field(default=None, repr=False)
    proxy_pass: str | None = field(default=None, repr=False)
    browser_user_agent: str | None = None
    browser_locale_timezone: str | None = None
    browser_timezone_id: str | None = None
    base_url: str | None = None
    target_bookmaker: str | None = None
    scrape_odds_history: bool = False
    headless: bool = True
    preview_submarkets_only: bool = False
    bookies_filter: BookiesFilter | str = BookiesFilter.ALL.value
    period: Enum | str | None = None
    request_delay: float = DEFAULT_REQUEST_DELAY_S
    concurrency_tasks: int = 3
    include_started: bool = False
    kickoff_within_hours: float | None = None
    links_only: bool = False
    local_kickoff: bool = False
    on_match: Callable[[dict[str, Any]], None] | None = None

    def __post_init__(self) -> None:
        sport = self.sport.value if isinstance(self.sport, Sport) else self.sport
        period = self.period.value if isinstance(self.period, Enum) else self.period
        proxy_url = (self.proxy_url,) if isinstance(self.proxy_url, str) else tuple(self.proxy_url or ())
        normalized = {
            "command": CommandEnum(self.command),
            "sport": sport,
            "bookies_filter": BookiesFilter(self.bookies_filter),
            "period": validate_and_convert_period(period, sport),
            "proxy_url": proxy_url,
        }
        for name, value in normalized.items():
            object.__setattr__(self, name, value)
