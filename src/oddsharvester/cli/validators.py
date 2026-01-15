"""Click validation callbacks for CLI arguments."""

from datetime import datetime

import click

from oddsharvester.cli.constants import (
    ODDS_FORMAT_SHORT_TO_INTERNAL,
    PERIOD_SHORT_TO_INTERNAL,
    SPORT_PERIODS,
)
from oddsharvester.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from oddsharvester.utils.sport_market_constants import Sport
from oddsharvester.utils.utils import get_supported_markets


def validate_markets(ctx: click.Context, param: click.Parameter, value: tuple) -> tuple:
    """Validate that markets are valid for the selected sport."""
    if not value:
        return value

    sport = ctx.params.get("sport")
    if not sport:
        # Sport not yet parsed; validation will happen in command
        return value

    try:
        sport_enum = Sport(sport.lower())
    except ValueError:
        return value  # Sport validation will fail elsewhere

    supported = get_supported_markets(sport_enum)
    invalid = [m for m in value if m not in supported]

    if invalid:
        supported_sample = ", ".join(sorted(supported)[:10])
        raise click.BadParameter(
            f"Invalid market(s) for {sport}: {', '.join(invalid)}. Supported: {supported_sample}..."
        )
    return value


def validate_leagues(ctx: click.Context, param: click.Parameter, value: tuple) -> tuple:
    """Validate that leagues are valid for the selected sport."""
    if not value:
        return value

    sport = ctx.params.get("sport")
    if not sport:
        return value

    try:
        sport_enum = Sport(sport.lower())
    except ValueError:
        return value

    if sport_enum not in SPORTS_LEAGUES_URLS_MAPPING:
        raise click.BadParameter(f"Sport '{sport}' does not support league filtering.")

    supported = SPORTS_LEAGUES_URLS_MAPPING[sport_enum]
    invalid = [lg for lg in value if lg not in supported]

    if invalid:
        available = ", ".join(sorted(supported.keys()))
        raise click.BadParameter(
            f"Invalid league(s) for {sport}: {', '.join(invalid)}. "
            f"Available: {available}"
        )
    return value


def validate_period(ctx: click.Context, param: click.Parameter, value: str | None) -> str | None:
    """Validate that period is valid for the selected sport and convert to internal format."""
    if value is None:
        return None

    sport = ctx.params.get("sport")
    if not sport:
        return value

    sport_lower = sport.lower()
    valid_periods = SPORT_PERIODS.get(sport_lower, [])

    if value not in valid_periods:
        raise click.BadParameter(
            f"Invalid period '{value}' for {sport}. " f"Valid periods: {', '.join(valid_periods)}."
        )

    # Convert short form to internal value
    return PERIOD_SHORT_TO_INTERNAL.get(value, value)


def validate_date_not_past(ctx: click.Context, param: click.Parameter, value: str | None) -> str | None:
    """Validate that date is today or in the future (for upcoming command)."""
    if value is None:
        return None

    try:
        parsed = datetime.strptime(value, "%Y%m%d")
        if parsed.date() < datetime.now().date():
            raise click.BadParameter(f"Date '{value}' is in the past. Must be today or future.")
    except ValueError:
        pass  # Let the type handle format errors

    return value


def validate_odds_format(ctx: click.Context, param: click.Parameter, value: str | None) -> str | None:
    """Convert odds format short name to internal value."""
    if value is None:
        return "Decimal Odds"  # Default

    internal = ODDS_FORMAT_SHORT_TO_INTERNAL.get(value)
    if internal is None:
        valid = ", ".join(ODDS_FORMAT_SHORT_TO_INTERNAL.keys())
        raise click.BadParameter(f"Invalid odds format '{value}'. Choose from: {valid}.")
    return internal


def validate_file_format_match(ctx: click.Context, param: click.Parameter, value: str | None) -> str | None:
    """Validate that file path extension matches the format option."""
    if value is None:
        return None

    fmt = ctx.params.get("format", "json")

    if "." not in value:
        raise click.BadParameter(f"File path must include extension (e.g., output.{fmt}).")

    ext = value.rsplit(".", 1)[-1].lower()
    if ext != fmt:
        raise click.BadParameter(f"File extension '.{ext}' doesn't match --format={fmt}. Use '.{fmt}'.")

    return value


def validate_concurrency(ctx: click.Context, param: click.Parameter, value: int) -> int:
    """Validate concurrency is a positive integer."""
    if value <= 0:
        raise click.BadParameter("Concurrency must be a positive integer.")
    return value


def validate_max_pages(ctx: click.Context, param: click.Parameter, value: int | None) -> int | None:
    """Validate max_pages is a positive integer if provided."""
    if value is not None and value <= 0:
        raise click.BadParameter("Max pages must be a positive integer.")
    return value


def validate_sport_required(ctx: click.Context) -> None:
    """Validate that sport is provided when required."""
    if not ctx.params.get("sport"):
        raise click.UsageError("Missing required option '--sport' / '-s'.")


def validate_date_or_leagues_required(ctx: click.Context) -> None:
    """Validate that either date or leagues is provided for upcoming command."""
    has_date = ctx.params.get("date")
    has_leagues = ctx.params.get("league")
    has_match_links = ctx.params.get("match_link")

    if not has_date and not has_leagues and not has_match_links:
        raise click.UsageError("Must provide --date, --league, or --match-link for upcoming command.")
