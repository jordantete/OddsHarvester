"""Main CLI entry point for OddsHarvester."""

import logging

import click

from oddsharvester import __version__
from oddsharvester.cli.commands import historic, upcoming
from oddsharvester.utils.setup_logging import setup_logger


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress all output except errors.")
@click.version_option(version=__version__, prog_name="oddsharvester")
@click.pass_context
def cli(ctx, verbose, quiet):
    """OddsHarvester - Scrape sports betting odds from OddsPortal.

    Use 'upcoming' to scrape upcoming matches or 'historic' for historical data.

    Examples:

        oddsharvester upcoming -s football -d 20250201 -m 1x2

        oddsharvester historic -s football -l england-premier-league --season 2024-2025 -m 1x2
    """
    # Configure logging based on verbosity
    if quiet:
        log_level = logging.ERROR
    elif verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    setup_logger(log_level=log_level, save_to_file=False)

    # Store context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


# Register commands
cli.add_command(upcoming)
cli.add_command(historic)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
