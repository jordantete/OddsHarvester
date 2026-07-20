"""CLI command for scraping historical matches."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.options import common_options
from oddsharvester.cli.types import COMMA_LIST
from oddsharvester.cli.validators import validate_max_pages, validate_seasons
from oddsharvester.core.scrape_result import ErrorType
from oddsharvester.core.scraper_app import run_scraper
from oddsharvester.storage.storage_manager import store_data
from oddsharvester.utils.sport_market_constants import Sport

logger = logging.getLogger(__name__)


def _format_combo_summary(combo_stats: list[dict], links_only: bool) -> str:
    """Render the per-combo breakdown shown at the end of a multi-combo run."""
    unit = "links" if links_only else "matches"
    labels = [f"{c['league']} {c['season']}".strip() if c["season"] else c["league"] for c in combo_stats]
    width = max(len(label) for label in labels)

    lines = [f"Collected {unit} across {len(combo_stats)} combos:"]
    empty = errored = 0

    for label, combo in zip(labels, combo_stats, strict=True):
        if combo["errored"]:
            lines.append(f"  {label:<{width}}  error")
            errored += 1
        else:
            lines.append(f"  {label:<{width}}  {combo['successful']}")
            if combo["successful"] == 0:
                empty += 1

    if empty:
        lines.append(f"{empty} combo(s) returned nothing.")
    if errored:
        lines.append(f"{errored} combo(s) errored.")

    return "\n".join(lines)


@click.command("historic")
@common_options
@click.option(
    "--season",
    "seasons",
    required=True,
    type=COMMA_LIST,
    callback=validate_seasons,
    help="Comma-separated seasons to scrape (YYYY, YYYY-YYYY, or 'current').",
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
    seasons = kwargs.get("seasons")
    sport_value = sport.value if isinstance(sport, Sport) else sport

    links_only = kwargs.get("links_only", False)
    local_kickoff = kwargs.get("local_kickoff", False)
    if links_only and kwargs.get("match_links"):
        raise click.UsageError("--links-only cannot be combined with --match-link (links are already collected).")
    if links_only and local_kickoff:
        raise click.UsageError("--links-only cannot be combined with --local-kickoff (no match pages are visited).")

    try:
        scraped_data = asyncio.run(
            run_scraper(
                command="scrape_historic",
                match_links=kwargs.get("match_links"),
                sport=sport_value,
                date=None,
                leagues=kwargs.get("leagues"),
                seasons=seasons,
                markets=kwargs.get("markets"),
                max_pages=kwargs.get("max_pages"),
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
                links_only=links_only,
                local_kickoff=local_kickoff,
            )
        )

        if scraped_data:
            if scraped_data.success:
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

            if len(scraped_data.combo_stats) > 1:
                click.echo(_format_combo_summary(scraped_data.combo_stats, links_only=links_only))
            if scraped_data.failed:
                click.echo(f"Failed URLs: {[f.url for f in scraped_data.failed]}", err=True)

            if not scraped_data.success:
                logger.error("Scraper did not return valid data.")
                sys.exit(1)

            # A failed listing page hides an unknown number of matches: they were
            # never discovered, so nothing downstream can detect the gap from the
            # data itself. Signal it through the exit code, but keep what was
            # collected so it can be inspected or re-run.
            listing_failures = [f for f in scraped_data.failed if f.error_type is ErrorType.LISTING_PAGE]
            if listing_failures:
                logger.error(f"Incomplete collection: {len(listing_failures)} listing page(s) failed.")
                click.echo(
                    f"Incomplete collection: {len(listing_failures)} listing page(s) failed, so an unknown "
                    f"number of matches were never discovered. The partial data was still written.",
                    err=True,
                )
                sys.exit(1)
        else:
            logger.error("Scraper did not return valid data.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        sys.exit(1)
