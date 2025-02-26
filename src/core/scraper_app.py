import logging
from .playwright_manager import PlaywrightManager
from .browser_helper import BrowserHelper
from .odds_portal_market_extractor import OddsPortalMarketExtractor
from .odds_portal_scraper import OddsPortalScraper
from .sport_market_registry import SportMarketRegistrar
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
    logger.info(f"Starting scraper with parameters: command={command} sport={sport}, date={date}, league={league}, season={season}, markets={markets} headless={headless}")
    
    SportMarketRegistrar.register_all_markets()
    playwright_manager = PlaywrightManager()
    browser_helper = BrowserHelper()
    market_extractor = OddsPortalMarketExtractor(browser_helper=browser_helper)

    scraper = OddsPortalScraper(
        playwright_manager=playwright_manager,
        browser_helper=browser_helper,
        market_extractor=market_extractor
    )

    try:
        await scraper.start_playwright(headless=headless, proxy=None)

        if command == CommandEnum.HISTORIC:
            if not sport or not league or not season:
                raise ValueError("Both 'sport', 'league' and 'season' must be provided for historic scraping.")
            
            logger.info(f"Scraping historical odds for sport={sport} league={league}, season={season}, markets={markets}")
            return await scraper.scrape_historic(sport=sport, league=league, season=season, markets=markets, max_pages=None)

        elif command == CommandEnum.UPCOMING_MATCHES:
            if not date:
                raise ValueError("A valid 'date' must be provided for upcoming matches scraping.")
                
            logger.info(f"Scraping upcoming matches for sport={sport}, date={date}, league={league}, markets={markets}")
            return await scraper.scrape_upcoming(sport=sport, date=date, league=league, markets=markets)
        
        else:
            raise ValueError(f"Unknown command: {command}. Supported commands are 'upcoming-matches' and 'historic'.")

    except Exception as e:
        logger.error(f"An error occured: {e}")
        return None

    finally:
        await scraper.stop_playwright()