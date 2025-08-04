import asyncio
import logging

from src.core.browser_helper import BrowserHelper
from src.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from src.core.odds_portal_scraper import OddsPortalScraper
from src.core.playwright_manager import PlaywrightManager
from src.core.sport_market_registry import SportMarketRegistrar
from src.utils.command_enum import CommandEnum
from src.utils.proxy_manager import ProxyManager

logger = logging.getLogger("ScraperApp")
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 20
TRANSIENT_ERRORS = (
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_TIMED_OUT",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_SOCKS_CONNECTION_FAILED",
    "ERR_CERT_AUTHORITY_INVALID",
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_NETWORK_CHANGED",
    "Timeout",  # generic timeout from Playwright
    "net::ERR_FAILED",
    "net::ERR_CONNECTION_ABORTED",
    "net::ERR_INTERNET_DISCONNECTED",
    "Navigation timeout",
    "TimeoutError",
    "Target closed",
)


async def run_scraper(
    command: CommandEnum,
    match_links: list | None = None,
    sport: str | None = None,
    date: str | None = None,
    leagues: list[str] | None = None,
    season: str | None = None,
    markets: list | None = None,
    max_pages: int | None = None,
    proxies: list | None = None,
    browser_user_agent: str | None = None,
    browser_locale_timezone: str | None = None,
    browser_timezone_id: str | None = None,
    target_bookmaker: str | None = None,
    scrape_odds_history: bool = False,
    headless: bool = True,
) -> dict:
    """Runs the scraping process and handles execution."""
    logger.info(f"""
        Starting scraper with parameters: command={command}, match_links={match_links}, sport={sport}, date={date}, leagues={leagues},
        season={season}, markets={markets}, max_pages={max_pages}, proxies={proxies}, browser_user_agent={browser_user_agent},
        browser_locale_timezone={browser_locale_timezone}, browser_timezone_id={browser_timezone_id},
        scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker}, headless={headless}""")

    proxy_manager = ProxyManager(cli_proxies=proxies)
    SportMarketRegistrar.register_all_markets()
    playwright_manager = PlaywrightManager()
    browser_helper = BrowserHelper()
    market_extractor = OddsPortalMarketExtractor(browser_helper=browser_helper)

    scraper = OddsPortalScraper(
        playwright_manager=playwright_manager, browser_helper=browser_helper, market_extractor=market_extractor
    )

    try:
        proxy_config = proxy_manager.get_current_proxy()
        await scraper.start_playwright(
            headless=headless,
            browser_user_agent=browser_user_agent,
            browser_locale_timezone=browser_locale_timezone,
            browser_timezone_id=browser_timezone_id,
            proxy=proxy_config,
        )

        if match_links and sport:
            logger.info(f"""
                Scraping specific matches: {match_links} for sport: {sport}, markets={markets},
                scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker}
            """)
            return await retry_scrape(
                scraper.scrape_matches,
                match_links=match_links,
                sport=sport,
                markets=markets,
                scrape_odds_history=scrape_odds_history,
                target_bookmaker=target_bookmaker,
            )

        if command == CommandEnum.HISTORIC:
            if not sport or not leagues or not season:
                raise ValueError("Both 'sport', 'leagues' and 'season' must be provided for historic scraping.")

            logger.info(f"""
                Scraping historical odds for sport={sport}, leagues={leagues}, season={season}, markets={markets},
                scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker}, max_pages={max_pages}
            """)

            if len(leagues) == 1:
                return await retry_scrape(
                    scraper.scrape_historic,
                    sport=sport,
                    league=leagues[0],
                    season=season,
                    markets=markets,
                    scrape_odds_history=scrape_odds_history,
                    target_bookmaker=target_bookmaker,
                    max_pages=max_pages,
                )
            else:
                return await _scrape_multiple_leagues(
                    scraper=scraper,
                    scrape_func=scraper.scrape_historic,
                    leagues=leagues,
                    sport=sport,
                    season=season,
                    markets=markets,
                    scrape_odds_history=scrape_odds_history,
                    target_bookmaker=target_bookmaker,
                    max_pages=max_pages,
                )

        elif command == CommandEnum.UPCOMING_MATCHES:
            if not date and not leagues:
                raise ValueError("Either 'date' or 'leagues' must be provided for upcoming matches scraping.")

            if leagues:
                logger.info(f"""
                    Scraping upcoming matches for sport={sport}, date={date}, leagues={leagues}, markets={markets},
                    scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker}
                """)

                if len(leagues) == 1:
                    return await retry_scrape(
                        scraper.scrape_upcoming,
                        sport=sport,
                        date=date,
                        league=leagues[0],
                        markets=markets,
                        scrape_odds_history=scrape_odds_history,
                        target_bookmaker=target_bookmaker,
                    )
                else:
                    return await _scrape_multiple_leagues(
                        scraper=scraper,
                        scrape_func=scraper.scrape_upcoming,
                        leagues=leagues,
                        sport=sport,
                        date=date,
                        markets=markets,
                        scrape_odds_history=scrape_odds_history,
                        target_bookmaker=target_bookmaker,
                    )
            else:
                logger.info(f"""
                    Scraping upcoming matches for sport={sport}, date={date}, markets={markets},
                    scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker}
                """)
                return await retry_scrape(
                    scraper.scrape_upcoming,
                    sport=sport,
                    date=date,
                    league=None,
                    markets=markets,
                    scrape_odds_history=scrape_odds_history,
                    target_bookmaker=target_bookmaker,
                )

        else:
            raise ValueError(f"Unknown command: {command}. Supported commands are 'upcoming-matches' and 'historic'.")

    except Exception as e:
        logger.error(f"An error occured: {e}")
        return None

    finally:
        await scraper.stop_playwright()


async def _scrape_multiple_leagues(scraper, scrape_func, leagues: list[str], sport: str, **kwargs) -> list[dict]:
    """
    Helper function to handle multi-league scraping with error handling and logging.

    Args:
        scraper: The scraper instance
        scrape_func: The function to call for each league (scrape_historic or scrape_upcoming)
        leagues: List of leagues to scrape
        sport: The sport being scraped
        **kwargs: Additional arguments to pass to the scrape function

    Returns:
        List of combined results from all leagues
    """
    all_results = []
    failed_leagues = []

    logger.info(f"Starting multi-league scraping for {len(leagues)} leagues: {leagues}")

    for i, league in enumerate(leagues, 1):
        try:
            logger.info(f"[{i}/{len(leagues)}] Processing league: {league}")

            league_data = await retry_scrape(scrape_func, sport=sport, league=league, **kwargs)

            if league_data:
                all_results.extend(league_data)
                logger.info(f"Successfully scraped {len(league_data)} matches from league: {league}")
            else:
                logger.warning(f"No data returned for league: {league}")

        except Exception as e:
            logger.error(f"Failed to scrape league '{league}': {e}")
            failed_leagues.append(league)
            continue

    total_matches = len(all_results)
    successful_leagues = len(leagues) - len(failed_leagues)

    if failed_leagues:
        logger.warning(f"ailed to scrape {len(failed_leagues)} leagues: {failed_leagues}")

    logger.info(
        f"Multi-league scraping completed: {successful_leagues}/{len(leagues)} leagues successful, {total_matches} total matches scraped"
    )

    return all_results


async def retry_scrape(scrape_func, *args, **kwargs):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await scrape_func(*args, **kwargs)
        except Exception as e:
            if any(keyword in str(e) for keyword in TRANSIENT_ERRORS):
                logger.warning(
                    f"[Attempt {attempt}] Transient error detected: {e}. Retrying in {RETRY_DELAY_SECONDS}s..."
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Non-retryable error encountered: {e}")
                raise
    logger.error("Max retries exceeded.")
    return None
