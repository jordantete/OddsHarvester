"""CLI command for scraping historical matches."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.options import common_options
from oddsharvester.cli.validators import validate_max_pages, validate_season
from oddsharvester.core.scraper_app import run_scraper
from oddsharvester.storage.storage_manager import store_data
from oddsharvester.utils.sport_market_constants import Sport

logger = logging.getLogger(__name__)

# Sports that support 'current' season
CURRENT_SEASON_SPORTS = {"tennis", "football", "baseball", "ice-hockey", "rugby-league", "rugby-union"}


@click.command("historic")
@common_options
@click.option(
    "--season",
    required=True,
    callback=validate_season,
    help="Season to scrape (YYYY, YYYY-YYYY, or 'current').",
)
@click.option(
    "--max-pages",
    type=int,
    callback=validate_max_pages,
    help="Maximum number of pages to scrape.",
)
@click.pass_context
def historic(ctx, **kwargs):
    """Scrape historical odds for a league/season."""
    sport = kwargs["sport"]
    storage = kwargs["storage"]
    storage_format = kwargs["storage_format"]
    bookies_filter = kwargs.get("bookies_filter")
    season = kwargs.get("season")

    # Normalize 'current' to None for allowed sports
    sport_value = sport.value if isinstance(sport, Sport) else sport
    if season and season.lower() == "current" and sport_value.lower() in CURRENT_SEASON_SPORTS:
        season = None

    try:
        scraped_data = asyncio.run(
            run_scraper(
                command="scrape_historic",
                match_links=kwargs.get("match_links"),
                sport=sport_value,
                date=None,
                leagues=kwargs.get("leagues"),
                season=season,
                markets=kwargs.get("markets"),
                max_pages=kwargs.get("max_pages"),
                proxies=list(kwargs.get("proxies")) if kwargs.get("proxies") else None,
                browser_user_agent=kwargs.get("browser_user_agent"),
                browser_locale_timezone=kwargs.get("browser_locale_timezone"),
                browser_timezone_id=kwargs.get("browser_timezone_id"),
                target_bookmaker=kwargs.get("target_bookmaker"),
                scrape_odds_history=kwargs.get("scrape_odds_history", False),
                headless=kwargs.get("headless", False),
                preview_submarkets_only=kwargs.get("preview_submarkets_only", False),
                bookies_filter=bookies_filter.value if bookies_filter else "all",
                period=kwargs.get("period"),
            )
        )

        if scraped_data:
            store_data(
                storage_type=storage.value if storage else "local",
                data=scraped_data,
                storage_format=storage_format.value if storage_format else "json",
                file_path=kwargs.get("file_path"),
            )
            click.echo(f"Successfully scraped {len(scraped_data)} matches.")
        else:
            logger.error("Scraper did not return valid data.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        sys.exit(1)
