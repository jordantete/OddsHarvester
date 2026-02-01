import asyncio
import logging
import sys

from oddsharvester.cli.cli_argument_handler import CLIArgumentHandler
from oddsharvester.core.scraper_app import run_scraper
from oddsharvester.storage.storage_manager import store_data
from oddsharvester.utils.setup_logging import setup_logger


def _parse_legacy_proxy(proxies: list | None) -> tuple[str | None, str | None, str | None]:
    """Convert legacy proxy format to new format. Takes first proxy if multiple provided."""
    if not proxies:
        return None, None, None

    proxy_entry = proxies[0]
    parts = proxy_entry.strip().split()
    proxy_url = parts[0] if parts else None
    proxy_user = parts[1] if len(parts) >= 2 else None
    proxy_pass = parts[2] if len(parts) >= 3 else None

    return proxy_url, proxy_user, proxy_pass


def main():
    """Main entry point for legacy CLI usage. Prefer using the Click CLI instead."""
    setup_logger(log_level=logging.DEBUG, save_to_file=False)
    logger = logging.getLogger("Main")

    try:
        args = CLIArgumentHandler().parse_and_validate_args()
        logger.info(f"Parsed arguments: {args}")

        # Convert legacy proxy format
        proxy_url, proxy_user, proxy_pass = _parse_legacy_proxy(args.get("proxies"))

        scraped_data = asyncio.run(
            run_scraper(
                command=args["command"],
                match_links=args["match_links"],
                sport=args["sport"],
                date=args["date"],
                leagues=args["leagues"],
                season=args["season"],
                markets=args["markets"],
                max_pages=args["max_pages"],
                proxy_url=proxy_url,
                proxy_user=proxy_user,
                proxy_pass=proxy_pass,
                browser_user_agent=args["browser_user_agent"],
                browser_locale_timezone=args["browser_locale_timezone"],
                browser_timezone_id=args["browser_timezone_id"],
                target_bookmaker=args["target_bookmaker"],
                scrape_odds_history=args["scrape_odds_history"],
                headless=args["headless"],
                preview_submarkets_only=args["preview_submarkets_only"],
                bookies_filter=args["bookies_filter"],
                period=args["period"],
            )
        )

        if scraped_data:
            store_data(
                storage_type=args["storage_type"],
                data=scraped_data,
                storage_format=args["storage_format"],
                file_path=args["file_path"],
            )
        else:
            logger.error("Scraper did not return valid data.")
            sys.exit(1)

    except ValueError as e:
        logger.error(f"Argument validation failed: {e!s}")

    except Exception as e:
        logger.error(f"Unexpected error: {e!s}", exc_info=True)


if __name__ == "__main__":
    main()
