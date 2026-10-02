"""CLI command for scraping live (in-play) matches."""

import logging
import sys

import click

from oddsharvester.cli.commands._output import write_output
from oddsharvester.cli.commands._scrape import run, scrape_options
from oddsharvester.cli.options import common_options, merged_match_links
from oddsharvester.core.sport_period_registry import SportPeriodRegistry
from oddsharvester.utils.command_enum import CommandEnum

logger = logging.getLogger(__name__)


@click.command("live")
@common_options
def live(**kwargs):
    """Scrape a one-shot snapshot of in-play odds for currently live matches."""
    if kwargs.get("scrape_odds_history"):
        raise click.UsageError("--odds-history is not supported for live scraping.")

    # The in-play view has no period selector: only the sport's full-match period, its default, describes it.
    full_match = SportPeriodRegistry.get_default_period(kwargs["sport"].value).value
    if kwargs.get("period") not in (None, full_match):
        raise click.UsageError(
            f"--period accepts only {full_match} for live scraping (the in-play view has no period)."
        )

    leagues = kwargs.get("leagues")
    if leagues and len(leagues) > 1:
        raise click.UsageError("live supports at most one --league.")

    options = scrape_options(CommandEnum.LIVE, kwargs, merged_match_links(kwargs))
    stream_ndjson = kwargs["stream_ndjson"]
    links_only = options.links_only

    try:
        scraped_data = run(options)

        if scraped_data is None:
            logger.error("Scraper did not return valid data.")
            sys.exit(1)

        if not scraped_data.success:
            # An empty snapshot has two very different causes, and an external
            # sampler must be able to tell them apart: nothing in play (fine) vs
            # every request failing (not fine, and invisible if reported as fine).
            if scraped_data.failed:
                click.echo(f"Failed URLs: {[f.url for f in scraped_data.failed]}", err=True)
                logger.error(f"All {len(scraped_data.failed)} live matches failed to scrape.")
                sys.exit(1)

            click.echo("No live matches found right now.", err=stream_ndjson)
            return

        write_failed = False
        # Without --output the stream is the output: skip the default scraped_data.json.
        if not stream_ndjson or kwargs.get("file_path"):
            write_failed = not write_output(scraped_data.success, kwargs, kwargs["storage"], kwargs["storage_format"])

        if links_only:
            click.echo(f"Collected {scraped_data.stats.successful} live match links.", err=stream_ndjson)
        else:
            click.echo(
                f"Successfully scraped {scraped_data.stats.successful} live matches "
                f"({scraped_data.stats.failed} failed, {scraped_data.stats.success_rate:.1f}% success rate).",
                err=stream_ndjson,
            )

        if scraped_data.failed:
            click.echo(f"Failed URLs: {[f.url for f in scraped_data.failed]}", err=True)

        if write_failed:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        sys.exit(1)
