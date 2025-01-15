import asyncio, pytz, uuid, logging
from datetime import datetime, timedelta
from cli.arguments import parse_args
from src.core.odds_portal_scrapper import OddsPortalScrapper
from storage.local_data_storage import LocalDataStorage
from storage.remote_data_storage import RemoteDataStorage
from playwright.async_api import async_playwright
from src.utils.setup_logging import setup_logger
from src.utils.constants import PLAYWRIGHT_BROWSER_ARGS

class OddsPortalScrapperApp:
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
        headless: bool = True
    ) -> dict:
        """Core scraping function that can be called from CLI or Lambda"""
        self.logger.info(f"Starting scraper with parameters: sport={sport}, date={date}, "
                    f"league={league}, season={season}, storage_type={storage_type}")
        storage = LocalDataStorage() if storage_type == 'local' else RemoteDataStorage()
        
        try:
            self._initialize_and_start_playwright(is_webdriver_headless=headless)
            scraper = OddsPortalScrapper(page=self.page, sport=sport)
            data = await scraper.scrape(date=date, league=league, season=season)

            if data:
                if storage_type == 'remote':
                    current_date = datetime.now(pytz.timezone('UTC'))
                    file_id = uuid.uuid4().hex[:8]
                    filename = f'/tmp/odds_data_{current_date.strftime("%Y%m%d")}_{file_id}.csv'
                    storage.process_and_upload(data, current_date.strftime("%m/%d/%Y, %H:%M:%S"), filename)
                else:
                    storage.append_data(data)
                    
                self.logger.info(f"Successfully stored {len(data)} records")
                return {'statusCode': 200, 'body': 'Data scraped and stored successfully'}
            else:
                self.logger.warning("No data was scraped")
                return {'statusCode': 400, 'body': 'No data was scraped'}
                
        except Exception as e:
            self.logger.error(f"Error during scraping process: {str(e)}", exc_info=True)
            return {'statusCode': 500, 'body': f'Error during scraping: {str(e)}'}
        
        finally:
            await self.__cleanup()
    
    async def _initialize_and_start_playwright(self, is_webdriver_headless: bool):
        try:
            self.logger.info("Starting Playwright...")
            self.playwright = await async_playwright().start()

            self.logger.info("Launching browser...")
            self.browser = await self.playwright.chromium.launch(headless=is_webdriver_headless, args=PLAYWRIGHT_BROWSER_ARGS)

            self.logger.info("Opening new page from browser...")
            self.page = await self.browser.new_page()
        
        except Exception as e:
            self.logger.error(f"Failed to initialize Playwright: {str(e)}")
            raise
    
    async def __cleanup(self):
        """Cleanup resources to avoid leaks in case of initialization failure."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.logger.info("Cleaned up Playwright resources.")

    async def cli_main(self):
        """Entry point for CLI usage"""
        args = parse_args()
        return await self.run_scraper(
            sport=args.sport,
            date=args.date,
            league=args.league,
            season=args.season,
            storage_type=args.storage,
            headless=args.headless
        )

    def lambda_handler(self, event, context):
        """Entry point for AWS Lambda"""
        self.logger.info(f"Lambda invocation with event: {event}")
        
        paris_tz = pytz.timezone('Europe/Paris')
        next_day = datetime.now(paris_tz) + timedelta(days=1)
        formatted_date = next_day.strftime('%Y%m%d')
        
        return asyncio.get_event_loop().run_until_complete(
            self.run_scraper(
                sport="football",
                date=formatted_date,
                storage_type="remote",
                headless=True
            )
        )

def main():
    app = OddsPortalScrapperApp()
    asyncio.run(app.cli_main())

def lambda_handler(event, context):
    app = OddsPortalScrapperApp()
    return app.lambda_handler(event, context)

if __name__ == "__main__":
    main()