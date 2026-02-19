"""Click callback validators for OddsHarvester CLI."""

from datetime import datetime
import re

import click

from oddsharvester.core.sport_period_registry import SportPeriodRegistry
from oddsharvester.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from oddsharvester.utils.sport_market_constants import Sport
from oddsharvester.utils.utils import get_supported_markets


def validate_date(ctx, param, value):
    """Validate date format (YYYYMMDD) and ensure it's today or future."""
    if value is None:
        return None

    try:
        parsed_date = datetime.strptime(value, "%Y%m%d")
    except ValueError:
        raise click.BadParameter(f"Invalid date format '{value}'. Expected YYYYMMDD (e.g., 20250227).") from None

    if parsed_date.date() < datetime.now().date():
        raise click.BadParameter(f"Date '{value}' must be today or in the future.")

    return value


def validate_season(ctx, param, value):
    """Validate season format (YYYY, YYYY-YYYY, or 'current')."""
    if value is None:
        return None

    if value.lower() == "current":
        return value

    single_year = re.compile(r"^\d{4}$")
    range_pattern = re.compile(r"^\d{4}-\d{4}$")

    if single_year.match(value):
        return value

    if range_pattern.match(value):
        start_year, end_year = map(int, value.split("-"))
        if end_year != start_year + 1:
            raise click.BadParameter(
                f"Invalid season range '{value}'. Second year must be exactly one year after the first."
            )
        return value

    raise click.BadParameter(f"Invalid season format '{value}'. Expected YYYY, YYYY-YYYY, or 'current'.")


def validate_match_links(ctx, param, value):
    """Validate match links format."""
    if not value:
        return None

    url_pattern = re.compile(r"https?://www\.oddsportal\.com/.+")
    invalid = [link for link in value if not url_pattern.match(link)]

    if invalid:
        raise click.BadParameter(f"Invalid match link(s): {', '.join(invalid)}")

    return list(value)


def validate_markets(ctx, param, value):
    """Validate markets against the selected sport."""
    if not value:
        return None

    sport = ctx.params.get("sport")
    if not sport:
        return value  # Will be validated later or sport is required

    if isinstance(sport, str):
        try:
            sport = Sport(sport.lower())
        except ValueError:
            return value

    supported = get_supported_markets(sport)
    invalid = [m for m in value if m not in supported]

    if invalid:
        raise click.BadParameter(
            f"Invalid market(s) for {sport.value}: {', '.join(invalid)}. Supported: {', '.join(supported)}"
        )

    return value


def validate_leagues(ctx, param, value):
    """Validate leagues against the selected sport."""
    if not value:
        return None

    sport = ctx.params.get("sport")
    if not sport:
        return value

    if isinstance(sport, str):
        try:
            sport = Sport(sport.lower())
        except ValueError:
            return value

    if sport not in SPORTS_LEAGUES_URLS_MAPPING:
        return value

    supported = SPORTS_LEAGUES_URLS_MAPPING[sport]
    invalid = [lg for lg in value if lg not in supported]

    if invalid:
        raise click.BadParameter(f"Invalid league(s) for {sport.value}: {', '.join(invalid)}")

    return value


def validate_period(ctx, param, value):
    """Validate period against the selected sport."""
    if value is None:
        return None

    sport = ctx.params.get("sport")
    if not sport:
        return value

    sport_str = sport.value if isinstance(sport, Sport) else sport

    if not SportPeriodRegistry.is_sport_registered(sport_str.lower()):
        return value

    valid_periods = SportPeriodRegistry.get_all_cli_values(sport_str.lower())

    if value not in valid_periods:
        raise click.BadParameter(
            f"Invalid period '{value}' for sport '{sport_str}'. Supported: {', '.join(valid_periods)}"
        )

    return value


def validate_proxy_url(ctx, param, value):
    """Validate proxy URL format."""
    if not value:
        return None

    proxy_pattern = re.compile(r"^(?P<scheme>https?|socks5|socks4)://(?P<host>[\w\.-]+):(?P<port>\d+)$")

    if not proxy_pattern.match(value):
        raise click.BadParameter(
            f"Invalid proxy URL '{value}'. Expected format: 'http[s]://host:port' or 'socks5://host:port'"
        )

    return value


def validate_concurrency(ctx, param, value):
    """Validate concurrency is a positive integer."""
    if value is not None and value <= 0:
        raise click.BadParameter("Concurrency must be a positive integer.")
    return value


def validate_max_pages(ctx, param, value):
    """Validate max_pages is a positive integer."""
    if value is not None and value <= 0:
        raise click.BadParameter("Max pages must be a positive integer.")
    return value


def validate_file_path(ctx, param, value):
    """Validate output file path to prevent path traversal and other unsafe patterns."""
    if value is None:
        return None

    from pathlib import Path

    path = Path(value)

    # Reject '..' path segments (no traversal)
    if ".." in path.parts:
        raise click.BadParameter(f"Output path must not contain '..' segments: '{value}'")

    # Reject paths pointing to existing directories
    if path.exists() and path.is_dir():
        raise click.BadParameter(f"Output path must not be an existing directory: '{value}'")

    return value
