"""CLI commands for OddsHarvester."""

from oddsharvester.cli.commands.community import community
from oddsharvester.cli.commands.historic import historic
from oddsharvester.cli.commands.live import live
from oddsharvester.cli.commands.upcoming import upcoming

__all__ = ["community", "historic", "live", "upcoming"]
