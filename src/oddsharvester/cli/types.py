"""Custom Click parameter types for CLI validation."""

from datetime import datetime
import re

import click

from oddsharvester.utils.sport_market_constants import Sport


class DateType(click.ParamType):
    """Click parameter type for ISO date format (YYYY-MM-DD)."""

    name = "date"

    def convert(self, value, param, ctx):
        if value is None:
            return None

        # Handle special values
        if value.lower() == "today":
            return datetime.now().strftime("%Y%m%d")
        if value.lower() == "tomorrow":
            from datetime import timedelta

            return (datetime.now() + timedelta(days=1)).strftime("%Y%m%d")

        # Try ISO format first (YYYY-MM-DD)
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
            return parsed.strftime("%Y%m%d")  # Convert to internal format
        except ValueError:
            pass

        # Try legacy format (YYYYMMDD) for backward compatibility
        try:
            parsed = datetime.strptime(value, "%Y%m%d")
            return value
        except ValueError:
            self.fail(f"Invalid date format: '{value}'. Use YYYY-MM-DD (e.g., 2025-02-27).", param, ctx)


class MatchLinkType(click.ParamType):
    """Click parameter type for OddsPortal match URLs."""

    name = "url"
    URL_PATTERN = re.compile(r"https?://www\.oddsportal\.com/.+")

    def convert(self, value, param, ctx):
        if value is None:
            return None

        if not self.URL_PATTERN.match(value):
            self.fail(
                f"Invalid match link: '{value}'. Must be an OddsPortal URL (https://www.oddsportal.com/...).",
                param,
                ctx,
            )
        return value


class SportType(click.ParamType):
    """Click parameter type for sport selection."""

    name = "sport"

    def convert(self, value, param, ctx):
        if value is None:
            return None

        try:
            sport = Sport(value.lower())
            return sport.value
        except ValueError:
            valid_sports = ", ".join(s.value for s in Sport)
            self.fail(f"Invalid sport: '{value}'. Choose from: {valid_sports}.", param, ctx)


class SeasonType(click.ParamType):
    """Click parameter type for season format (YYYY, YYYY-YYYY, or 'current')."""

    name = "season"
    SINGLE_YEAR = re.compile(r"^\d{4}$")
    RANGE_YEAR = re.compile(r"^\d{4}-\d{4}$")

    def convert(self, value, param, ctx):
        if value is None:
            return None

        # Handle 'current' keyword
        if value.lower() == "current":
            return "current"

        # Single year (e.g., 2024)
        if self.SINGLE_YEAR.match(value):
            return value

        # Range format (e.g., 2023-2024)
        if self.RANGE_YEAR.match(value):
            start, end = map(int, value.split("-"))
            if end != start + 1:
                self.fail(f"Invalid season range: '{value}'. Second year must be exactly one after first.", param, ctx)
            return value

        self.fail(f"Invalid season format: '{value}'. Use YYYY, YYYY-YYYY, or 'current'.", param, ctx)


class ProxyUrlType(click.ParamType):
    """Click parameter type for proxy URL validation."""

    name = "proxy_url"
    PROXY_PATTERN = re.compile(r"^(?:https?|socks[45])://[\w.-]+:\d+$")

    def convert(self, value, param, ctx):
        if value is None:
            return None

        if not self.PROXY_PATTERN.match(value):
            self.fail(
                f"Invalid proxy URL: '{value}'. Expected format: http[s]://host:port or socks5://host:port.",
                param,
                ctx,
            )
        return value


# Instantiate types for use in decorators
DATE = DateType()
MATCH_LINK = MatchLinkType()
SPORT = SportType()
SEASON = SeasonType()
PROXY_URL = ProxyUrlType()
