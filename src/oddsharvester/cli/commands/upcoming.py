"""CLI command for scraping upcoming matches."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.options import common_options
from oddsharvester.cli.validators import validate_date
from oddsharvester.core.scraper_app import run_scraper
from oddsharvester.storage.storage_manager import store_data

logger = logging.getLogger(__name__)


@click.command("upcoming")
@common_options
@click.option(
    "--date",
    "-d",
    callback=validate_date,
    help="Date for upcoming matches (format: YYYYMMDD).",
)
@click.pass_context
def upcoming(ctx, **kwargs):
    """Scrape odds for upcoming matches."""
    # Validate: need either date, leagues, or match_links
    if not kwargs.get("date") and not kwargs.get("leagues") and not kwargs.get("match_links"):
        raise click.UsageError("You must provide --date, --league, or --match-link for upcoming matches.")

    # Convert enums to values for the scraper
    sport = kwargs["sport"]
    storage = kwargs["storage"]
    storage_format = kwargs["storage_format"]
    bookies_filter = kwargs.get("bookies_filter")

    try:
        scraped_data = asyncio.run(
            run_scraper(
                command="scrape_upcoming",
                match_links=kwargs.get("match_links"),
                sport=sport.value if sport else None,
                date=kwargs.get("date"),
                leagues=kwargs.get("leagues"),
                season=None,
                markets=kwargs.get("markets"),
                max_pages=None,
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
