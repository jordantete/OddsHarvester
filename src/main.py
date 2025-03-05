import asyncio, logging, sys
from cli.cli_argument_handler import CLIArgumentHandler
from utils.setup_logging import setup_logger
from core.scraper_app import run_scraper
from storage.storage_manager import store_data

def main():
    """Main entry point for CLI usage."""    
    setup_logger(log_level=logging.DEBUG, save_to_file=False)
    logger = logging.getLogger("Main")

    try:
        args = CLIArgumentHandler().parse_and_validate_args()
        logger.info(f"Parsed arguments: {args}")

        scraped_data = asyncio.run(run_scraper(
            command=args["command"],
            sport=args["sport"],
            date=args["date"],
            league=args["league"],
            season=args["season"],
            markets=args["markets"],
            max_pages=args["max_pages"],
            proxies=args["proxies"],
            browser_user_agent=args["browser_user_agent"],
            browser_locale_timezone=args["browser_locale_timezone"],
            browser_timezone_id=args["browser_timezone_id"],
            headless=args["headless"]
        ))

        if scraped_data:
            store_data(
                storage_type=args["storage_type"],
                data=scraped_data,
                storage_format=args["storage_format"],
                file_path=args["file_path"]
            )
        else:
            logger.error("Scraper did not return valid data.")
            sys.exit(1)

    except ValueError as e:
        logger.error(f"Argument validation failed: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()