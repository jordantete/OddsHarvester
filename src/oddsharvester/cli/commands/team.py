"""CLI command for scraping OddsPortal team pages."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.commands._output import write_output
from oddsharvester.cli.options import browser_options, output_options, request_delay_option
from oddsharvester.cli.types import COMMA_LIST
from oddsharvester.cli.validators import validate_teams, validate_teams_file
from oddsharvester.core.team.team_scraper import run_teams

logger = logging.getLogger(__name__)


@click.command("team")
@click.option(
    "--team",
    "teams",
    multiple=True,
    type=COMMA_LIST,
    callback=validate_teams,
    envvar="OH_TEAMS",
    help="Team to scrape, as an OddsPortal team id or a team page URL. Comma-separated and/or repeated.",
)
@click.option(
    "--teams-file",
    "teams_file",
    type=click.Path(exists=True, dir_okay=False),
    callback=validate_teams_file,
    help="File with teams to scrape, one id or URL per line. Combines with --team.",
)
@output_options
@browser_options
@request_delay_option
def team(**kwargs):
    """Scrape team metadata: names, venue, coach and recent form.

    Teams are given as ids or team page URLs, via --team and/or --teams-file.
    """
    team_ids = list(dict.fromkeys((kwargs.get("teams") or []) + (kwargs.get("teams_file") or [])))
    if not team_ids:
        raise click.UsageError("You must provide --team or --teams-file.")

    storage = kwargs["storage"]
    storage_format = kwargs["storage_format"]

    try:
        result = asyncio.run(
            run_teams(
                team_ids=team_ids,
                headless=kwargs.get("headless", False),
                proxy_url=kwargs.get("proxy_url"),
                proxy_user=kwargs.get("proxy_user"),
                proxy_pass=kwargs.get("proxy_pass"),
                browser_user_agent=kwargs.get("browser_user_agent"),
                browser_locale_timezone=kwargs.get("browser_locale_timezone"),
                browser_timezone_id=kwargs.get("browser_timezone_id"),
                base_url=kwargs.get("base_url"),
                request_delay=kwargs["request_delay"],
            )
        )

        if not result.success:
            logger.error("No team data scraped.")
            sys.exit(1)

        written = write_output(result.success, kwargs, storage, storage_format)
        click.echo(
            f"Successfully scraped {result.stats.successful} team(s) ({result.stats.failed} failed, "
            f"{result.stats.success_rate:.1f}% success rate)."
        )
        if result.failed:
            click.echo(f"Failed teams: {[f.url for f in result.failed]}", err=True)

        if not written:
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during team scraping: {e}", exc_info=True)
        sys.exit(1)
