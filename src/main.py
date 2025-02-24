import asyncio, pytz, logging
from datetime import datetime, timedelta
from typing import Any, Dict, List
from utils.cli_argument_handler import CLIArgumentHandler
from core.browser_helper import BrowserHelper
from core.odds_portal_scrapper import OddsPortalScrapper
from utils.setup_logging import setup_logger
from utils.utils import build_response
from utils.command_enum import CommandEnum
from storage.storage_type import StorageType
from storage.storage_format import StorageFormat

class OddsPortalScrapperApp:
    def __init__(
        self, 
        save_log_to_file: bool = False
    ):
        setup_logger(log_level=logging.DEBUG, save_to_file=save_log_to_file)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def run_scraper(
        self,
        command: CommandEnum,
        sport: str | None = None,
        date: str | None = None,
        league: str | None = None,
        season: str | None = None,
        storage_type: str = 'local',
        storage_format: str = 'csv',
        file_path: str = 'scraped_data',
        headless: bool = True,
        markets: List[str] | None = None
    ) -> dict:
        """Core scraping function that can be called from CLI or Lambda"""
        self.logger.info(
            f"""Starting scraper with parameters: 
            command={command} sport={sport}, date={date}, league={league},
            season={season}, storage_type={storage_type}, storage_format={storage_format},
            file_path={file_path}, headless={headless}
            """
        )
        
        try:
            scraped_data = await self._perform_scraping(
                command=command,
                sport=sport, 
                date=date, 
                league=league, 
                season=season, 
                markets=markets, 
                is_webdriver_headless=headless
            )

            if not scraped_data:
                return build_response(400, "No data was scraped")

            storage = self._initialize_storage(storage_type)
            await self._store_data(
                storage=storage, 
                data=scraped_data, 
                storage_type=storage_type, 
                storage_format=storage_format, 
                file_path=file_path
            )
            return build_response(200, "Data scraped and stored successfully")

        except Exception as e:
            return build_response(500, f"{str(e)}")
    
    def _initialize_storage(self, storage_type: str):
        """Initialize storage based on the provided storage type."""
        try:
            storage_enum = StorageType(storage_type)
            return storage_enum.get_storage_instance()
        
        except Exception as e:
            self.logger.error(f"Failed to initialize storage: {str(e)}")
            raise

    async def _perform_scraping(
        self,
        command: CommandEnum,
        sport: str | None,
        date: str | None,
        league: str | None,
        season: str | None,
        markets: List[str] | None,
        is_webdriver_headless: bool = True
    ) -> list:
        """Perform the actual scraping using OddsPortalScrapper."""
        try:
            browser_helper = BrowserHelper()
            scraper = OddsPortalScrapper(browser_helper=browser_helper)

            await scraper.initialize_and_start_playwright(
                is_webdriver_headless=is_webdriver_headless,
                proxy=None
            )

            return await scraper.scrape(
                command=command,
                sport=sport, 
                date=date, 
                league=league, 
                season=season, 
                markets=markets
            )
        
        except Exception as e:
            self.logger.error(f"Error during scraping: {str(e)}")
            raise
        
        finally:
            await scraper.cleanup()

    async def _store_data(
        self, 
        storage, 
        data: list, 
        storage_type: StorageType, 
        storage_format: StorageFormat,
        file_path: str
    ):
        """Store the scraped data."""
        try:
            if storage_type == StorageType.REMOTE.value:
                storage.process_and_upload(
                    data=data, 
                    file_path=file_path
                )
            elif storage_type == StorageType.LOCAL.value:
                storage.save_data(
                    data=data, 
                    file_path=file_path, 
                    storage_format=storage_format
                )
            else:
                self.logger.error("Unsupported StorageType. Data will not be stored")
                raise Exception

            self.logger.info(f"Successfully stored {len(data)} records.")

        except Exception as e:
            self.logger.error(f"Error during data storage: {str(e)}")
            raise

    def lambda_handler(
        self, 
        event: Dict[str, Any], 
        context: Any
    ):
        """Entry point for AWS Lambda"""
        self.logger.info(f"Lambda invocation with event: {event} and context: {context}")
        
        paris_tz = pytz.timezone('Europe/Paris')
        next_day = datetime.now(paris_tz) + timedelta(days=1)
        formatted_date = next_day.strftime('%Y%m%d')
        
        return asyncio.get_event_loop().run_until_complete(
            self.run_scraper(
                sport="football",
                date=formatted_date,
                league="premier-league",
                storage_type="remote",
                headless=True,
                markets=["1x2"]
            )
        )

def main():
    """Main entry point for CLI usage."""
    handler = CLIArgumentHandler()

    try:
        args = handler.parse_and_validate_args()
        logging.info(f"Parsed arguments: {args}")

        app = OddsPortalScrapperApp(save_log_to_file=args.save_logs)
        asyncio.run(
            app.run_scraper(
                command=args.command,
                sport=args.sport if hasattr(args, "sport") else None,
                date=args.date if hasattr(args, "date") else None,
                league=args.league if hasattr(args, "league") else None,
                season=args.season if hasattr(args, "season") else None,
                storage_type=args.storage,
                storage_format=args.format if hasattr(args, "format") else None,
                file_path=args.file_path if hasattr(args, "file_path") else None,
                headless=args.headless,
                markets=args.markets
            )
        )

    except ValueError as e:
        logging.error(f"Argument validation failed: {str(e)}")
        print(f"Error: {str(e)}\nUse '--help' for more information.")
    
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}", exc_info=True)
        print(f"An unexpected error occurred: {str(e)}")

def lambda_handler(event: Dict[str, Any], context: Any):
    app = OddsPortalScrapperApp()
    return app.lambda_handler(event, context)

if __name__ == "__main__":
    main()