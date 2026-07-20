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
@click.option(
    "--include-started/--no-include-started",
    "include_started",
    default=False,
    envvar="OH_INCLUDE_STARTED",
    help="Also return matches that have already started or finished (default: upcoming-only).",
)
@click.option(
    "--kickoff-within-hours",
    "kickoff_within_hours",
    type=click.FloatRange(min=0, min_open=True),
    default=None,
    help="Only scrape matches kicking off within this many hours from now (reduces request volume).",
)
@click.pass_context
def upcoming(ctx, **kwargs):
    """Scrape odds for upcoming matches."""
    # Validate: need either date, leagues, or match_links
    if not kwargs.get("date") and not kwargs.get("leagues") and not kwargs.get("match_links"):
        raise click.UsageError("You must provide --date, --league, or --match-link for upcoming matches.")

    links_only = kwargs.get("links_only", False)
    local_kickoff = kwargs.get("local_kickoff", False)
    if links_only and kwargs.get("match_links"):
        raise click.UsageError("--links-only cannot be combined with --match-link (links are already collected).")
    if links_only and local_kickoff:
        raise click.UsageError("--links-only cannot be combined with --local-kickoff (no match pages are visited).")

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
                seasons=None,
                markets=kwargs.get("markets"),
                max_pages=None,
                proxy_url=kwargs.get("proxy_url"),
                proxy_user=kwargs.get("proxy_user"),
                proxy_pass=kwargs.get("proxy_pass"),
                browser_user_agent=kwargs.get("browser_user_agent"),
                browser_locale_timezone=kwargs.get("browser_locale_timezone"),
                browser_timezone_id=kwargs.get("browser_timezone_id"),
                base_url=kwargs.get("base_url"),
                target_bookmaker=kwargs.get("target_bookmaker"),
                scrape_odds_history=kwargs.get("scrape_odds_history", False),
                headless=kwargs.get("headless", False),
                preview_submarkets_only=kwargs.get("preview_submarkets_only", False),
                bookies_filter=bookies_filter.value if bookies_filter else "all",
                period=kwargs.get("period"),
                request_delay=kwargs.get("request_delay", 1.0),
                concurrency_tasks=kwargs.get("concurrency_tasks", 3),
                include_started=kwargs.get("include_started", False),
                kickoff_within_hours=kwargs.get("kickoff_within_hours"),
                links_only=links_only,
                local_kickoff=local_kickoff,
            )
        )

        if scraped_data and scraped_data.success:
            store_data(
                storage_type=storage.value if storage else "local",
                data=scraped_data.success,
                storage_format=storage_format.value if storage_format else "json",
                file_path=kwargs.get("file_path"),
                append=kwargs.get("append", False),
            )
            if links_only:
                click.echo(
                    f"Collected {scraped_data.stats.successful} match links "
                    f"({scraped_data.stats.failed} listing pages failed)."
                )
            else:
                click.echo(
                    f"Successfully scraped {scraped_data.stats.successful} matches "
                    f"({scraped_data.stats.failed} failed, {scraped_data.stats.success_rate:.1f}% success rate)."
                )
            if scraped_data.failed:
                click.echo(f"Failed URLs: {[f.url for f in scraped_data.failed]}", err=True)
        else:
            logger.error("Scraper did not return valid data.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        sys.exit(1)
