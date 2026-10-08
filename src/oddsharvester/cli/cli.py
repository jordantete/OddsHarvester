"""Main CLI entry point for OddsHarvester."""

import logging

import click

from oddsharvester import __version__
from oddsharvester.cli.commands import community, historic, live, search, team, upcoming
from oddsharvester.utils.setup_logging import setup_logger


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress all output except errors.")
@click.version_option(version=__version__, prog_name="oddsharvester")
def cli(verbose, quiet):
    """OddsHarvester - Scrape sports betting odds from OddsPortal.

    Six commands: 'upcoming' (matches to come), 'historic' (past seasons), 'live' (matches in play),
    'community' (community predictions and votes), 'team' (team pages) and 'search' (a team by name,
    then its matches).

    Examples (YYYYMMDD stands for a date, today or later):

        oddsharvester upcoming -s football -d YYYYMMDD -m 1x2

        oddsharvester historic -s football -l england-premier-league --season 2024-2025 -m 1x2

        oddsharvester community -s football -o top_predictions.json

        oddsharvester team --team lId4TMwf -o teams.json

        oddsharvester search --query "Nacional" -s football -o teams.json
    """
    # Configure logging based on verbosity
    if quiet:
        log_level = logging.ERROR
    elif verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    setup_logger(log_level=log_level)


# Register commands
cli.add_command(upcoming)
cli.add_command(historic)
cli.add_command(community)
cli.add_command(live)
cli.add_command(team)
cli.add_command(search)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
