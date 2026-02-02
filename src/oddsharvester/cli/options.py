"""Shared Click options for OddsHarvester CLI commands."""

import functools

import click

from oddsharvester.cli.types import BOOKIES_FILTER, COMMA_LIST, ODDS_FORMAT, SPORT, STORAGE_FORMAT, STORAGE_TYPE
from oddsharvester.cli.validators import (
    validate_concurrency,
    validate_leagues,
    validate_markets,
    validate_match_links,
    validate_period,
    validate_proxy_url,
)
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.odds_format_enum import OddsFormat
from oddsharvester.utils.period_constants import (
    AmericanFootballPeriod,
    BaseballPeriod,
    BasketballPeriod,
    FootballPeriod,
    IceHockeyPeriod,
    RugbyLeaguePeriod,
    RugbyUnionPeriod,
    TennisPeriod,
)


def _get_all_periods():
    """Get all valid period values across all sports."""
    periods = set()
    for period_enum in [
        FootballPeriod,
        TennisPeriod,
        BasketballPeriod,
        RugbyLeaguePeriod,
        RugbyUnionPeriod,
        AmericanFootballPeriod,
        IceHockeyPeriod,
        BaseballPeriod,
    ]:
        periods.update(p.value for p in period_enum)
    return sorted(periods)


def common_options(func):
    """Decorator that adds common options to both commands."""

    @click.option(
        "--sport",
        "-s",
        type=SPORT,
        required=True,
        envvar="OH_SPORT",
        help="Sport to scrape (football, tennis, basketball, etc.).",
    )
    @click.option(
        "--league",
        "-l",
        "leagues",
        type=COMMA_LIST,
        callback=validate_leagues,
        envvar="OH_LEAGUES",
        help="Comma-separated leagues (e.g., england-premier-league,spain-laliga).",
    )
    @click.option(
        "--market",
        "-m",
        "markets",
        type=COMMA_LIST,
        callback=validate_markets,
        envvar="OH_MARKETS",
        help="Comma-separated markets (e.g., 1x2,btts,over-under).",
    )
    @click.option(
        "--storage",
        type=STORAGE_TYPE,
        default="local",
        envvar="OH_STORAGE",
        help="Storage type: local or remote.",
    )
    @click.option(
        "--format",
        "-f",
        "storage_format",
        type=STORAGE_FORMAT,
        default="json",
        envvar="OH_FORMAT",
        help="Output format: json or csv.",
    )
    @click.option(
        "--output",
        "-o",
        "file_path",
        type=click.Path(),
        envvar="OH_FILE_PATH",
        help="Output file path.",
    )
    @click.option(
        "--headless/--no-headless",
        default=False,
        envvar="OH_HEADLESS",
        help="Run browser in headless mode.",
    )
    @click.option(
        "--concurrency",
        "-c",
        "concurrency_tasks",
        type=int,
        default=3,
        callback=validate_concurrency,
        envvar="OH_CONCURRENCY",
        help="Number of concurrent scraping tasks.",
    )
    @click.option(
        "--match-link",
        "match_links",
        multiple=True,
        callback=validate_match_links,
        help="Specific match URL(s) to scrape. Can be repeated.",
    )
    @click.option(
        "--proxy-url",
        "proxy_url",
        callback=validate_proxy_url,
        envvar="OH_PROXY_URL",
        help="Proxy URL (e.g., http://proxy.example.com:8080 or socks5://proxy:1080).",
    )
    @click.option(
        "--proxy-user",
        "proxy_user",
        envvar="OH_PROXY_USER",
        help="Proxy username (optional).",
    )
    @click.option(
        "--proxy-pass",
        "proxy_pass",
        envvar="OH_PROXY_PASS",
        help="Proxy password (optional).",
    )
    @click.option(
        "--user-agent",
        "browser_user_agent",
        envvar="OH_USER_AGENT",
        help="Custom browser user agent.",
    )
    @click.option(
        "--locale",
        "browser_locale_timezone",
        envvar="OH_LOCALE",
        help="Browser locale (e.g., fr-BE).",
    )
    @click.option(
        "--timezone",
        "browser_timezone_id",
        envvar="OH_TIMEZONE",
        help="Browser timezone ID (e.g., Europe/Brussels).",
    )
    @click.option(
        "--target-bookmaker",
        help="Filter for a specific bookmaker.",
    )
    @click.option(
        "--odds-history/--no-odds-history",
        "scrape_odds_history",
        default=False,
        help="Scrape historical odds movement.",
    )
    @click.option(
        "--odds-format",
        type=ODDS_FORMAT,
        default=OddsFormat.DECIMAL_ODDS.value,
        help="Odds display format.",
    )
    @click.option(
        "--preview-only/--full-scrape",
        "preview_submarkets_only",
        default=False,
        help="Only scrape visible submarkets (faster, limited data).",
    )
    @click.option(
        "--bookies-filter",
        type=BOOKIES_FILTER,
        default=BookiesFilter.ALL.value,
        help="Bookmaker filter: all, classic, or crypto.",
    )
    @click.option(
        "--period",
        type=click.Choice(_get_all_periods(), case_sensitive=False),
        callback=validate_period,
        help="Match period to scrape (sport-specific).",
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper
