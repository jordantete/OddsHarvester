"""CLI command for scraping historical matches."""

import click

from oddsharvester.cli.commands._scrape import scrape_and_report
from oddsharvester.cli.options import common_options, merged_match_links
from oddsharvester.cli.types import COMMA_LIST
from oddsharvester.cli.validators import validate_max_pages, validate_seasons
from oddsharvester.utils.command_enum import CommandEnum


@click.command("historic")
@common_options
@click.option(
    "--season",
    "seasons",
    type=COMMA_LIST,
    callback=validate_seasons,
    help="Comma-separated seasons to scrape (YYYY, YYYY-YYYY, or 'current'). Required with --league; with "
    "--match-link, the one season written into the records.",
)
@click.option(
    "--max-pages",
    type=int,
    callback=validate_max_pages,
    help="Maximum number of pages to scrape.",
)
def historic(**kwargs):
    """Scrape historical odds for a league/season."""
    match_links = merged_match_links(kwargs)
    seasons = kwargs["seasons"]

    if not match_links and not kwargs.get("leagues"):
        raise click.UsageError("You must provide --league or --match-link for historic matches.")
    if not match_links and not seasons:
        raise click.UsageError("Missing option '--season' (required with --league).")
    if match_links and seasons and len(seasons) > 1:
        raise click.UsageError("--match-link takes one --season at most: the season the matches belong to.")

    scrape_and_report(CommandEnum.HISTORIC, kwargs, match_links)
