import asyncio, pytz, uuid, logging
from datetime import datetime, timedelta
from typing import Any, Dict, List
from utils.cli_arguments_parser import parse_args
from core.browser_helper import BrowserHelper
from core.odds_portal_scrapper import OddsPortalScrapper
from utils.setup_logging import setup_logger
from utils.utils import build_response
from storage.storage_type import StorageType

class OddsPortalScrapperApp:
    DEFAULT_TIMEZONE = 'Europe/Paris'

    def __init__(self):
        setup_logger()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def run_scraper(
        self,
        sport: str,
        date: str | None = None,
        league: str | None = None,
        season: str | None = None,
        storage_type: str = 'local',
        headless: bool = True,
        markets: List[str] | None = None
    ) -> dict:
        """Core scraping function that can be called from CLI or Lambda"""
        self.logger.info(f"Starting scraper with parameters: sport={sport}, date={date}, league={league}, season={season}, storage_type={storage_type}, headless={headless}")
        
        try:
            scraped_data = await self._perform_scraping(
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
            await self._store_data(storage, scraped_data, storage_type)
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
        sport: str,
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
            await scraper.initialize_playwright(is_webdriver_headless=is_webdriver_headless)
            return await scraper.scrape(sport= sport, date=date, league=league, season=season)
        
        except Exception as e:
            self.logger.error(f"Error during scraping: {str(e)}")
            raise
        
        finally:
            await scraper.cleanup()

    async def _store_data(
        self, 
        storage, 
        data: list, 
        storage_type: str
    ):
        """Store the scraped data."""
        try:
            if storage_type == StorageType.REMOTE.value:
                current_date = datetime.now(pytz.timezone('UTC'))
                file_id = uuid.uuid4().hex[:8]
                filename = f'/tmp/odds_data_{current_date.strftime("%Y%m%d")}_{file_id}.csv'
                storage.process_and_upload(data, current_date.strftime("%m/%d/%Y, %H:%M:%S"), filename)
            else:
                storage.append_data(data)

            self.logger.info(f"Successfully stored {len(data)} records.")

        except Exception as e:
            self.logger.error(f"Error during data storage: {str(e)}")
            raise

    async def cli_main(self):
        """Entry point for CLI usage"""
        args = parse_args()
        return await self.run_scraper(
            sport=args.sport,
            date=args.date,
            league=args.league,
            season=args.season,
            storage_type=args.storage,
            headless=args.headless,
            markets=args.markets
        )

    def lambda_handler(
        self, 
        event: Dict[str, Any], 
        context: Any
    ):
        """Entry point for AWS Lambda"""
        self.logger.info(f"Lambda invocation with event: {event} and context: {context}")
        
        paris_tz = pytz.timezone(self.DEFAULT_TIMEZONE)
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
    app = OddsPortalScrapperApp()
    asyncio.run(app.cli_main())

def lambda_handler(event: Dict[str, Any], context: Any):
    app = OddsPortalScrapperApp()
    return app.lambda_handler(event, context)

if __name__ == "__main__":
    main()