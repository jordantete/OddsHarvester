"""Upcoming matches command for CLI."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.options import common_options
from oddsharvester.cli.types import DATE
from oddsharvester.cli.validators import validate_date_not_past
from oddsharvester.utils.command_enum import CommandEnum


@click.command()
@click.option(
    "--date",
    "-d",
    type=DATE,
    callback=validate_date_not_past,
    envvar="OH_DATE",
    help="Date for upcoming matches (YYYY-MM-DD format, e.g., 2025-02-27).",
)
@common_options
@click.pass_context
def upcoming(
    ctx: click.Context,
    date: str | None,
    sport: str | None,
    league: tuple,
    market: tuple,
    match_link: tuple,
    storage: str,
    format: str,
    file_path: str | None,
    proxy_url: str | None,
    proxy_user: str | None,
    proxy_pass: str | None,
    user_agent: str | None,
    locale: str | None,
    timezone: str | None,
    headless: bool,
    debug_logs: bool,
    bookmaker: tuple,
    with_odds_history: bool,
    odds_format: str,
    concurrency: int,
    preview_only: bool,
    bookmakers: str,
    period: str | None,
):
    """Scrape odds for upcoming matches.

    \b
    Requires either --date, --league, or --match-link.

    \b
    Examples:
      oh upcoming -s football -d 2025-02-27
      oh upcoming -s football --league england-premier-league --league spain-laliga
      oh upcoming -s tennis --match-link https://www.oddsportal.com/tennis/...
    """
    # Setup logging based on verbosity
    from oddsharvester.utils.setup_logging import setup_logger

    verbose = ctx.parent.params.get("verbose", False) if ctx.parent else False
    quiet = ctx.parent.params.get("quiet", False) if ctx.parent else False

    if quiet:
        log_level = logging.WARNING
    elif verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    setup_logger(log_level=log_level, save_to_file=debug_logs)
    logger = logging.getLogger("upcoming")

    # Validate required arguments
    if not match_link and not sport:
        raise click.UsageError("--sport is required unless using --match-link.")

    if not date and not league and not match_link:
        raise click.UsageError("Must provide --date, --league, or --match-link.")

    # Build proxy configuration
    proxies = None
    if proxy_url:
        proxy_config = proxy_url
        if proxy_user and proxy_pass:
            # Format: scheme://user:pass@host:port
            from urllib.parse import urlparse

            parsed = urlparse(proxy_url)
            proxy_config = f"{parsed.scheme}://{proxy_user}:{proxy_pass}@{parsed.netloc}"
        proxies = [proxy_config]

    # Convert tuples to lists (Click uses tuples for multiple values)
    leagues_list = list(league) if league else None
    markets_list = list(market) if market else None
    match_links_list = list(match_link) if match_link else None
    bookmaker_list = list(bookmaker) if bookmaker else None

    # Log configuration
    logger.info(f"Starting upcoming scrape: sport={sport}, date={date}")
    if leagues_list:
        logger.info(f"Leagues: {', '.join(leagues_list)}")
    if markets_list:
        logger.info(f"Markets: {', '.join(markets_list)}")

    # Run scraper
    from oddsharvester.core.scraper_app import run_scraper
    from oddsharvester.storage.storage_manager import store_data

    try:
        scraped_data = asyncio.run(
            run_scraper(
                command=CommandEnum.UPCOMING_MATCHES,
                match_links=match_links_list,
                sport=sport,
                date=date,
                leagues=leagues_list,
                season=None,
                markets=markets_list,
                max_pages=None,
                proxies=proxies,
                browser_user_agent=user_agent,
                browser_locale_timezone=locale,
                browser_timezone_id=timezone,
                target_bookmaker=bookmaker_list[0] if bookmaker_list else None,
                scrape_odds_history=with_odds_history,
                headless=headless,
                preview_submarkets_only=preview_only,
                bookies_filter=bookmakers,
                period=period,
            )
        )

        if scraped_data:
            store_data(
                storage_type=storage,
                data=scraped_data,
                storage_format=format,
                file_path=file_path,
            )
            if not quiet:
                click.echo(f"Successfully scraped {len(scraped_data)} matches.")
        else:
            logger.error("No data scraped.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Scraping failed: {e}", exc_info=verbose)
        sys.exit(1)
