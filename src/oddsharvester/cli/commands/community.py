"""CLI command for scraping OddsPortal Community data (top predictions)."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.types import SPORT, STORAGE_FORMAT, STORAGE_TYPE
from oddsharvester.cli.validators import validate_base_url, validate_file_path, validate_proxy_url
from oddsharvester.core.community.top_predictions_scraper import run_top_predictions
from oddsharvester.storage.storage_manager import store_data

logger = logging.getLogger(__name__)


@click.command("community")
@click.option("--sport", "-s", type=SPORT, required=True, envvar="OH_SPORT", help="Sport to scrape predictions for.")
@click.option(
    "--storage", type=STORAGE_TYPE, default="local", envvar="OH_STORAGE", help="Storage type: local or remote."
)
@click.option(
    "--format",
    "-f",
    "storage_format",
    type=STORAGE_FORMAT,
    default="json",
    envvar="OH_FORMAT",
    help="Output format: json or csv.",
)
@click.option(
    "--output",
    "-o",
    "file_path",
    type=click.Path(),
    callback=validate_file_path,
    envvar="OH_FILE_PATH",
    help="Output file path.",
)
@click.option(
    "--append/--no-append",
    default=False,
    envvar="OH_APPEND",
    help="Append to the output file instead of overwriting it.",
)
@click.option("--headless/--no-headless", default=False, envvar="OH_HEADLESS", help="Run browser in headless mode.")
@click.option(
    "--proxy-url",
    "proxy_url",
    multiple=True,
    callback=validate_proxy_url,
    envvar="OH_PROXY_URL",
    help="Proxy URL (repeatable).",
)
@click.option("--proxy-user", envvar="OH_PROXY_USER", help="Proxy username (optional).")
@click.option("--proxy-pass", envvar="OH_PROXY_PASS", help="Proxy password (optional).")
@click.option("--user-agent", "browser_user_agent", envvar="OH_USER_AGENT", help="Custom browser user agent.")
@click.option("--locale", "browser_locale_timezone", envvar="OH_LOCALE", help="Browser locale (e.g., fr-BE).")
@click.option(
    "--timezone", "browser_timezone_id", envvar="OH_TIMEZONE", help="Browser timezone ID (e.g., Europe/Brussels)."
)
@click.option(
    "--base-url",
    callback=validate_base_url,
    envvar="OH_BASE_URL",
    help="Regional OddsPortal domain to scrape instead of www.oddsportal.com.",
)
@click.pass_context
def community(ctx, **kwargs):
    """Scrape the Community Top Predictions page (most-voted picks, next 7 days)."""
    sport = kwargs["sport"]
    storage = kwargs["storage"]
    storage_format = kwargs["storage_format"]

    try:
        records = asyncio.run(
            run_top_predictions(
                sport=sport.value,
                headless=kwargs.get("headless", False),
                proxy_url=kwargs.get("proxy_url"),
                proxy_user=kwargs.get("proxy_user"),
                proxy_pass=kwargs.get("proxy_pass"),
                browser_user_agent=kwargs.get("browser_user_agent"),
                browser_locale_timezone=kwargs.get("browser_locale_timezone"),
                browser_timezone_id=kwargs.get("browser_timezone_id"),
                base_url=kwargs.get("base_url"),
            )
        )

        if records:
            store_data(
                storage_type=storage.value if storage else "local",
                data=records,
                storage_format=storage_format.value if storage_format else "json",
                file_path=kwargs.get("file_path"),
                append=kwargs.get("append", False),
            )
            click.echo(f"Successfully scraped {len(records)} community top predictions.")
        else:
            logger.error("No community top predictions scraped.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during community scraping: {e}", exc_info=True)
        sys.exit(1)
