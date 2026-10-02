"""The body upcoming, historic and live share: their common checks, their ScrapeOptions and the run."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.commands._output import format_combo_summary, report_incomplete_collection, write_output
from oddsharvester.core.scrape_options import ScrapeOptions
from oddsharvester.core.scrape_result import ScrapeResult
from oddsharvester.core.scraper_app import run_scrape
from oddsharvester.storage.ndjson_stream import NdjsonStreamWriter
from oddsharvester.storage.storage_type import StorageType
from oddsharvester.utils.command_enum import CommandEnum

logger = logging.getLogger(__name__)


def scrape_options(command: CommandEnum, kwargs: dict, match_links: list[str] | None) -> ScrapeOptions:
    """Reject the option pairs no scrape command accepts, then build the run's options from the parsed ones."""
    links_only = kwargs["links_only"]
    if links_only and match_links:
        raise click.UsageError("--links-only cannot be combined with --match-link (links are already collected).")
    if links_only and kwargs["local_kickoff"]:
        raise click.UsageError("--links-only cannot be combined with --local-kickoff (no match pages are visited).")

    stream_ndjson = kwargs["stream_ndjson"]
    if stream_ndjson and links_only:
        raise click.UsageError("--stream-ndjson cannot be combined with --links-only (no match records are produced).")
    if stream_ndjson and kwargs["storage"] is StorageType.REMOTE and not kwargs.get("file_path"):
        raise click.UsageError(
            "--storage remote with --stream-ndjson needs --output: the stream alone writes no file to upload."
        )

    if match_links and kwargs.get("leagues"):
        logger.warning("--league is ignored with --match-link: the given matches are scraped whatever their league.")

    return ScrapeOptions(
        command=command,
        match_links=match_links,
        sport=kwargs["sport"],
        date=kwargs.get("date"),
        leagues=kwargs.get("leagues"),
        seasons=kwargs.get("seasons"),
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
        scrape_odds_history=kwargs["scrape_odds_history"],
        headless=kwargs["headless"],
        preview_submarkets_only=kwargs["preview_submarkets_only"],
        bookies_filter=kwargs["bookies_filter"],
        period=kwargs.get("period"),
        request_delay=kwargs["request_delay"],
        concurrency_tasks=kwargs["concurrency_tasks"],
        include_started=kwargs.get("include_started", False),
        kickoff_within_hours=kwargs.get("kickoff_within_hours"),
        links_only=links_only,
        local_kickoff=kwargs["local_kickoff"],
        on_match=NdjsonStreamWriter().emit if stream_ndjson else None,
    )


def run(options: ScrapeOptions) -> ScrapeResult | None:
    return asyncio.run(run_scrape(options))


def scrape_and_report(command: CommandEnum, kwargs: dict, match_links: list[str] | None) -> None:
    """Run upcoming or historic and report it: exit 1 when nothing was scraped, a listing failed or the write did."""
    options = scrape_options(command, kwargs, match_links)
    stream_ndjson = kwargs["stream_ndjson"]
    links_only = options.links_only

    try:
        scraped_data = run(options)

        if scraped_data:
            write_failed = False
            if scraped_data.success:
                # Without --output the stream is the output: skip the default scraped_data.json.
                if not stream_ndjson or kwargs.get("file_path"):
                    write_failed = not write_output(
                        scraped_data.success, kwargs, kwargs["storage"], kwargs["storage_format"]
                    )
                if links_only:
                    click.echo(
                        f"Collected {scraped_data.stats.successful} match links "
                        f"({scraped_data.stats.failed} listing pages failed).",
                        err=stream_ndjson,
                    )
                else:
                    click.echo(
                        f"Successfully scraped {scraped_data.stats.successful} matches "
                        f"({scraped_data.stats.failed} failed, {scraped_data.stats.success_rate:.1f}% success rate).",
                        err=stream_ndjson,
                    )

            if len(scraped_data.combo_stats) > 1:
                click.echo(format_combo_summary(scraped_data.combo_stats, links_only=links_only), err=stream_ndjson)
            if scraped_data.failed:
                click.echo(f"Failed URLs: {[f.url for f in scraped_data.failed]}", err=True)

            if not scraped_data.success:
                logger.error("Scraper did not return valid data.")
                sys.exit(1)

            if report_incomplete_collection(scraped_data) or write_failed:
                sys.exit(1)
        else:
            logger.error("Scraper did not return valid data.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        sys.exit(1)
