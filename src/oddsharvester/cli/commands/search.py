"""CLI command for OddsPortal's search: find a team by name, then list its matches."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.commands._output import write_output
from oddsharvester.cli.options import browser_options, output_options, request_delay_option
from oddsharvester.cli.types import SPORT
from oddsharvester.cli.validators import validate_max_pages, validate_team_id
from oddsharvester.core.exceptions import ScraperError
from oddsharvester.core.search.search_scraper import run_search

logger = logging.getLogger(__name__)


@click.command("search")
@click.option("--query", help="Team name to search for within --sport. Lists the matching teams.")
@click.option(
    "--team-id",
    "team_id",
    callback=validate_team_id,
    help="Team to list the matches of, as an OddsPortal team id or a team page URL.",
)
# No OH_SPORT: exported for the other commands, it would refuse every --team-id call.
@click.option("--sport", "-s", type=SPORT, help="Sport to search in. Needed with --query, refused with --team-id.")
@click.option(
    "--max-pages",
    type=int,
    callback=validate_max_pages,
    help="With --team-id: result pages to read, 20 matches each (default: 1).",
)
@output_options
@browser_options
@request_delay_option
def search(**kwargs):
    """Find a team by name, or list a team's matches.

    Two steps, one call each: --query with --sport lists the matching teams; --team-id lists the
    upcoming matches and the latest results of one of them.
    """
    query, team_id, sport, max_pages = kwargs["query"], kwargs["team_id"], kwargs["sport"], kwargs["max_pages"]
    if (query is None) == (team_id is None):
        raise click.UsageError("Provide exactly one of --query or --team-id.")
    if query is not None:
        query = query.strip()
        if not query:
            raise click.UsageError("--query must not be empty.")
        if sport is None:
            raise click.UsageError("--query needs --sport: the search runs within one sport.")
        if max_pages is not None:
            raise click.UsageError("--max-pages applies to --team-id only.")
    elif sport is not None:
        raise click.UsageError("--sport does not apply to --team-id: the id already names the team and its sport.")

    try:
        rows = asyncio.run(
            run_search(
                query=query,
                sport=sport.value if sport else None,
                team_id=team_id,
                max_pages=max_pages or 1,
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
    except ScraperError as e:
        logger.error(f"Search failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during search: {e}", exc_info=True)
        sys.exit(1)

    written = write_output(rows, kwargs, kwargs["storage"], kwargs["storage_format"])
    if query is not None:
        click.echo(f"Found {len(rows)} team(s) matching '{query}' in {sport.value}.")
    else:
        click.echo(f"Found {len(rows)} match(es) for team {team_id}.")
    if not written:
        sys.exit(1)
