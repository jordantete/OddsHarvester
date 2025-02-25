import logging
from core.browser_helper import BrowserHelper
from core.odds_portal_scrapper import OddsPortalScrapper
from utils.command_enum import CommandEnum

logger = logging.getLogger("ScraperApp")

async def run_scraper(
    command: CommandEnum,
    sport: str | None = None,
    date: str | None = None,
    league: str | None = None,
    season: str | None = None,
    markets: list | None = None,
    headless: bool = True
) -> dict:
    """Runs the scraping process and handles execution."""
    logger.info(f"Starting scraper with parameters: command={command} sport={sport}, date={date}, league={league}, season={season}, headless={headless}")
    browser_helper = BrowserHelper()
    scraper = OddsPortalScrapper(browser_helper=browser_helper)

    try:
        await scraper.initialize_and_start_playwright(is_webdriver_headless=headless, proxy=None)
        return await scraper.scrape(
            command=command,
            sport=sport, 
            date=date, 
            league=league, 
            season=season, 
            markets=markets
        )

    except Exception as e:
        logger.error(f"An error occured: {e}")
        return None

    finally:
        await scraper.cleanup()