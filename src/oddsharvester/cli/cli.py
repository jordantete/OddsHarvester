"""Main CLI entry point using Click."""

import logging
import sys

import click

# Version from pyproject.toml - we'll read it dynamically
__version__ = "0.1.0"


class Context:
    """CLI context object to pass state between commands."""

    def __init__(self):
        self.verbose = False
        self.quiet = False
        self.debug = False

    def setup_logging(self):
        """Configure logging based on verbosity settings."""
        if self.quiet:
            level = logging.WARNING
        elif self.verbose:
            level = logging.DEBUG
        else:
            level = logging.INFO

        from oddsharvester.utils.setup_logging import setup_logger

        setup_logger(log_level=level, save_to_file=self.debug)


pass_context = click.make_pass_decorator(Context, ensure=True)


@click.group(invoke_without_command=True)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose/debug output.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-error output.")
@click.version_option(__version__, "-V", "--version", prog_name="OddsHarvester")
@click.pass_context
def cli(ctx, verbose, quiet):
    """OddsHarvester - Scrape betting odds from OddsPortal.

    \b
    Commands:
      upcoming   Scrape odds for upcoming matches
      historic   Scrape historical odds for past matches

    \b
    Examples:
      oh upcoming -s football -d 2025-02-27 --league england-premier-league
      oh historic -s tennis --season 2024 --max-pages 5

    Use 'oh <command> --help' for command-specific options.
    """
    # Initialize context
    ctx.ensure_object(Context)
    ctx.obj.verbose = verbose
    ctx.obj.quiet = quiet

    # If no command provided, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _register_commands():
    """Register commands lazily to avoid circular imports."""
    from oddsharvester.cli.commands.historic import historic
    from oddsharvester.cli.commands.upcoming import upcoming

    cli.add_command(upcoming)
    cli.add_command(historic)


def main():
    """Entry point for the CLI."""
    _register_commands()
    try:
        cli()
    except KeyboardInterrupt:
        # Immediate exit on Ctrl+C (per user preference)
        click.echo("\nAborted.", err=True)
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
