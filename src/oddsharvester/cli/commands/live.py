"""CLI command for scraping live (in-play) matches."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.options import common_options
from oddsharvester.core.scraper_app import run_scraper
from oddsharvester.storage.storage_manager import store_data

logger = logging.getLogger(__name__)


@click.command("live")
@common_options
@click.pass_context
def live(ctx, **kwargs):
    """Scrape a one-shot snapshot of in-play odds for currently live matches."""
    if kwargs.get("scrape_odds_history"):
        raise click.UsageError("--odds-history is not supported for live scraping.")
    if kwargs.get("period"):
        raise click.UsageError("--period is not supported for live scraping (current view only).")

    leagues = kwargs.get("leagues")
    if leagues and len(leagues) > 1:
        raise click.UsageError("live supports at most one --league.")

    links_only = kwargs.get("links_only", False)
    if links_only and kwargs.get("match_links"):
        raise click.UsageError("--links-only cannot be combined with --match-link (links are already collected).")

    sport = kwargs["sport"]
    storage = kwargs["storage"]
    storage_format = kwargs["storage_format"]
    bookies_filter = kwargs.get("bookies_filter")

    try:
        scraped_data = asyncio.run(
            run_scraper(
                command="scrape_live",
                match_links=kwargs.get("match_links"),
                sport=sport.value if sport else None,
                leagues=leagues,
                markets=kwargs.get("markets"),
                proxy_url=kwargs.get("proxy_url"),
                proxy_user=kwargs.get("proxy_user"),
                proxy_pass=kwargs.get("proxy_pass"),
                browser_user_agent=kwargs.get("browser_user_agent"),
                browser_locale_timezone=kwargs.get("browser_locale_timezone"),
                browser_timezone_id=kwargs.get("browser_timezone_id"),
                base_url=kwargs.get("base_url"),
                target_bookmaker=kwargs.get("target_bookmaker"),
                headless=kwargs.get("headless", False),
                bookies_filter=bookies_filter.value if bookies_filter else "all",
                request_delay=kwargs.get("request_delay", 1.0),
                concurrency_tasks=kwargs.get("concurrency_tasks", 3),
                links_only=links_only,
            )
        )

        if scraped_data is None:
            logger.error("Scraper did not return valid data.")
            sys.exit(1)

        # No live match is a normal outcome, not a failure: OddsPortal simply has
        # nothing in play right now.
        if not scraped_data.success:
            click.echo("No live matches found right now.")
            return

        store_data(
            storage_type=storage.value if storage else "local",
            data=scraped_data.success,
            storage_format=storage_format.value if storage_format else "json",
            file_path=kwargs.get("file_path"),
            append=kwargs.get("append", False),
        )

        if links_only:
            click.echo(f"Collected {scraped_data.stats.successful} live match links.")
        else:
            click.echo(
                f"Successfully scraped {scraped_data.stats.successful} live matches "
                f"({scraped_data.stats.failed} failed, {scraped_data.stats.success_rate:.1f}% success rate)."
            )

        if scraped_data.failed:
            click.echo(f"Failed URLs: {[f.url for f in scraped_data.failed]}", err=True)

    except click.UsageError:
        raise

    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        sys.exit(1)
