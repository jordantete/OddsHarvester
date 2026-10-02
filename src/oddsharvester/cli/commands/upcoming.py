"""CLI command for scraping upcoming matches."""

import click

from oddsharvester.cli.commands._scrape import scrape_and_report
from oddsharvester.cli.options import common_options, merged_match_links
from oddsharvester.cli.validators import validate_date
from oddsharvester.utils.command_enum import CommandEnum


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
def upcoming(**kwargs):
    """Scrape odds for upcoming matches."""
    match_links = merged_match_links(kwargs)

    # Validate: need either date, leagues, or match_links
    if not kwargs.get("date") and not kwargs.get("leagues") and not match_links:
        raise click.UsageError("You must provide --date, --league, or --match-link for upcoming matches.")

    scrape_and_report(CommandEnum.UPCOMING_MATCHES, kwargs, match_links)
