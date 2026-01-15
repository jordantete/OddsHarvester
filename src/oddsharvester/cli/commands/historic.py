"""Historic matches command for CLI."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.options import common_options
from oddsharvester.cli.types import SEASON
from oddsharvester.cli.validators import validate_max_pages
from oddsharvester.utils.command_enum import CommandEnum


@click.command()
@click.option(
    "--season",
    type=SEASON,
    required=True,
    envvar="OH_SEASON",
    help="Season to scrape (YYYY, YYYY-YYYY, or 'current').",
)
@click.option(
    "--max-pages",
    type=int,
    default=None,
    callback=validate_max_pages,
    envvar="OH_MAX_PAGES",
    help="Maximum number of result pages to scrape.",
)
@common_options
@click.pass_context
def historic(
    ctx: click.Context,
    season: str,
    max_pages: int | None,
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
    """Scrape historical odds for past matches.

    \b
    Requires --season and --sport (unless using --match-link).

    \b
    Examples:
      oh historic -s football --season 2024 --league england-premier-league
      oh historic -s tennis --season 2023-2024 --max-pages 10
      oh historic -s basketball --season current
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
    logger = logging.getLogger("historic")

    # Validate required arguments
    if not match_link and not sport:
        raise click.UsageError("--sport is required unless using --match-link.")

    # Build proxy configuration
    proxies = None
    if proxy_url:
        proxy_config = proxy_url
        if proxy_user and proxy_pass:
            from urllib.parse import urlparse

            parsed = urlparse(proxy_url)
            proxy_config = f"{parsed.scheme}://{proxy_user}:{proxy_pass}@{parsed.netloc}"
        proxies = [proxy_config]

    # Convert tuples to lists
    leagues_list = list(league) if league else None
    markets_list = list(market) if market else None
    match_links_list = list(match_link) if match_link else None
    bookmaker_list = list(bookmaker) if bookmaker else None

    # Log configuration
    logger.info(f"Starting historic scrape: sport={sport}, season={season}")
    if leagues_list:
        logger.info(f"Leagues: {', '.join(leagues_list)}")
    if max_pages:
        logger.info(f"Max pages: {max_pages}")

    # Run scraper
    from oddsharvester.core.scraper_app import run_scraper
    from oddsharvester.storage.storage_manager import store_data

    try:
        scraped_data = asyncio.run(
            run_scraper(
                command=CommandEnum.HISTORIC,
                match_links=match_links_list,
                sport=sport,
                date=None,
                leagues=leagues_list,
                season=season,
                markets=markets_list,
                max_pages=max_pages,
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
