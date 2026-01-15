"""Shared Click option decorators for CLI commands."""

import functools

import click

from oddsharvester.cli.constants import (
    ALL_PERIOD_CHOICES,
    BOOKMAKERS_CHOICES,
    FORMAT_CHOICES,
    ODDS_FORMAT_CHOICES,
    STORAGE_CHOICES,
)
from oddsharvester.cli.types import MATCH_LINK, PROXY_URL, SPORT
from oddsharvester.cli.validators import (
    validate_concurrency,
    validate_file_format_match,
    validate_leagues,
    validate_markets,
    validate_odds_format,
    validate_period,
)


def common_options(f):
    """Decorator that adds all common options shared between commands."""

    @click.option(
        "--sport",
        "-s",
        type=SPORT,
        envvar="OH_SPORT",
        help="Sport to scrape (football, tennis, basketball, etc.).",
    )
    @click.option(
        "--league",
        "-l",
        "league",
        multiple=True,
        callback=validate_leagues,
        envvar="OH_LEAGUES",
        help="League to scrape (repeatable). E.g., --league england-premier-league --league spain-laliga",
    )
    @click.option(
        "--market",
        "-m",
        "market",
        multiple=True,
        callback=validate_markets,
        envvar="OH_MARKETS",
        help="Market to scrape (repeatable). E.g., --market 1x2 --market btts",
    )
    @click.option(
        "--match-link",
        "match_link",
        multiple=True,
        type=MATCH_LINK,
        help="Specific OddsPortal match URL (repeatable). Overrides sport/league/date.",
    )
    @click.option(
        "--storage",
        type=click.Choice(STORAGE_CHOICES),
        default="local",
        envvar="OH_STORAGE",
        help="Storage type: local or remote.",
    )
    @click.option(
        "--format",
        "-f",
        "format",
        type=click.Choice(FORMAT_CHOICES),
        default="json",
        envvar="OH_FORMAT",
        help="Output format: json or csv.",
    )
    @click.option(
        "--file-path",
        "-o",
        "file_path",
        type=str,
        callback=validate_file_format_match,
        envvar="OH_FILE_PATH",
        help="Output file path (must match --format extension).",
    )
    @click.option(
        "--proxy-url",
        type=PROXY_URL,
        envvar="OH_PROXY_URL",
        help="Proxy server URL (e.g., http://proxy.com:8080 or socks5://proxy.com:1080).",
    )
    @click.option(
        "--proxy-user",
        type=str,
        envvar="OH_PROXY_USER",
        help="Proxy username for authentication.",
    )
    @click.option(
        "--proxy-pass",
        type=str,
        envvar="OH_PROXY_PASS",
        help="Proxy password for authentication.",
    )
    @click.option(
        "--user-agent",
        type=str,
        envvar="OH_USER_AGENT",
        help="Custom browser user agent string.",
    )
    @click.option(
        "--locale",
        type=str,
        envvar="OH_LOCALE",
        help="Browser locale (e.g., fr-BE, en-US).",
    )
    @click.option(
        "--timezone",
        type=str,
        envvar="OH_TIMEZONE",
        help="Browser timezone ID (e.g., Europe/Brussels, America/New_York).",
    )
    @click.option(
        "--headless/--no-headless",
        default=False,
        envvar="OH_HEADLESS",
        help="Run browser in headless mode.",
    )
    @click.option(
        "--debug-logs",
        is_flag=True,
        default=False,
        envvar="OH_DEBUG_LOGS",
        help="Save debug logs to file.",
    )
    @click.option(
        "--bookmaker",
        "-b",
        "bookmaker",
        multiple=True,
        help="Filter to specific bookmaker(s) (repeatable). E.g., --bookmaker bet365",
    )
    @click.option(
        "--with-odds-history",
        is_flag=True,
        default=False,
        envvar="OH_ODDS_HISTORY",
        help="Include historical odds movement data.",
    )
    @click.option(
        "--odds-format",
        type=click.Choice(ODDS_FORMAT_CHOICES),
        default="decimal",
        callback=validate_odds_format,
        envvar="OH_ODDS_FORMAT",
        help="Odds display format: decimal, fractional, american, hong-kong.",
    )
    @click.option(
        "--concurrency",
        "-c",
        type=int,
        default=3,
        callback=validate_concurrency,
        envvar="OH_CONCURRENCY",
        help="Number of concurrent scraping tasks.",
    )
    @click.option(
        "--preview-only",
        is_flag=True,
        default=False,
        help="Only scrape visible submarkets (faster, limited data).",
    )
    @click.option(
        "--bookmakers",
        type=click.Choice(BOOKMAKERS_CHOICES),
        default="all",
        envvar="OH_BOOKMAKERS",
        help="Bookmaker filter: all, classic, or crypto.",
    )
    @click.option(
        "--period",
        type=click.Choice(ALL_PERIOD_CHOICES),
        default=None,
        callback=validate_period,
        envvar="OH_PERIOD",
        help="Match period: ft (full-time), 1h/2h (halves), 1q-4q (quarters), 1s/2s (sets), 1p-3p (periods).",
    )
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper
