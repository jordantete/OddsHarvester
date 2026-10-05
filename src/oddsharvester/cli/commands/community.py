"""CLI command for scraping OddsPortal Community data (top predictions)."""

import asyncio
import logging
import sys

import click
from click.core import ParameterSource

from oddsharvester.cli.commands._output import write_output
from oddsharvester.cli.options import browser_options, output_options
from oddsharvester.cli.types import SPORT
from oddsharvester.core.community.match_community_scraper import run_match_community
from oddsharvester.core.community.top_predictions_scraper import run_top_predictions
from oddsharvester.core.community.user_profile_scraper import run_user_profile

logger = logging.getLogger(__name__)


@click.command("community")
@click.option("--sport", "-s", type=SPORT, envvar="OH_SPORT", help="Top-predictions mode: sport to scrape.")
@click.option("--user", "username", envvar="OH_USER", help="User-profile mode: OddsPortal username.")
@click.option("--match-url", "match_url", envvar="OH_MATCH_URL", help="Match-community mode: OddsPortal match URL.")
@output_options
@browser_options
@click.pass_context
def community(ctx, **kwargs):
    """Scrape OddsPortal Community data.

    Exactly one mode: --sport (top predictions), --user (profile), --match-url (match votes).
    """
    modes = {name: kwargs.get(name) for name in ("sport", "username", "match_url")}
    exported = {name for name in modes if ctx.get_parameter_source(name) is ParameterSource.ENVIRONMENT}
    typed = any(ctx.get_parameter_source(name) is ParameterSource.COMMANDLINE for name in modes)

    # A mode typed on the command line wins over the other modes' variables, exported for other runs;
    # OH_SPORT, shared with the other commands, also yields to OH_USER or OH_MATCH_URL.
    if typed:
        modes.update(dict.fromkeys(exported))
    elif (modes["username"] or modes["match_url"]) and "sport" in exported:
        modes["sport"] = None
    sport, username, match_url = modes["sport"], modes["username"], modes["match_url"]

    storage = kwargs["storage"]
    storage_format = kwargs["storage_format"]

    flags = [("--sport", sport), ("--user", username), ("--match-url", match_url)]
    chosen = [name for name, value in flags if value]
    if len(chosen) != 1:
        raise click.UsageError("Provide exactly one of --sport, --user or --match-url.")

    browser_kwargs = {
        "headless": kwargs.get("headless", False),
        "proxy_url": kwargs.get("proxy_url"),
        "proxy_user": kwargs.get("proxy_user"),
        "proxy_pass": kwargs.get("proxy_pass"),
        "browser_user_agent": kwargs.get("browser_user_agent"),
        "browser_locale_timezone": kwargs.get("browser_locale_timezone"),
        "browser_timezone_id": kwargs.get("browser_timezone_id"),
        "base_url": kwargs.get("base_url"),
    }

    try:
        if sport:
            records = asyncio.run(run_top_predictions(sport=sport.value, **browser_kwargs))
            _store_or_exit(
                records,
                bool(records),
                kwargs,
                storage,
                storage_format,
                f"Successfully scraped {len(records)} community top predictions.",
                "No community top predictions scraped.",
            )
        elif username:
            record = asyncio.run(run_user_profile(username=username, **browser_kwargs))
            has_data = bool(record.get("username"))
            _store_or_exit(
                [record],
                has_data,
                kwargs,
                storage,
                storage_format,
                f"Successfully scraped profile '{username}' (privacy={record.get('privacy')}).",
                f"No profile data scraped for '{username}'.",
            )
        else:
            record = asyncio.run(run_match_community(match_url=match_url, **browser_kwargs))
            has_data = bool(record.get("markets"))
            _store_or_exit(
                [record],
                has_data,
                kwargs,
                storage,
                storage_format,
                f"Successfully scraped {len(record['markets'])} community markets for the match.",
                "No community vote data for this match: its page shows no vote row.",
            )
    except Exception as e:
        logger.error(f"Error during community scraping: {e}", exc_info=True)
        sys.exit(1)


def _store_or_exit(data, has_data, kwargs, storage, storage_format, ok_msg, empty_msg):
    if not has_data:
        logger.error(empty_msg)
        sys.exit(1)

    written = write_output(data, kwargs, storage, storage_format)
    click.echo(ok_msg)
    if not written:
        sys.exit(1)
