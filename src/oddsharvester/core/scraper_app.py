import asyncio
import logging

from oddsharvester.core.browser_helper import BrowserHelper
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import OddsPortalScraper
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import TRANSIENT_ERROR_KEYWORDS
from oddsharvester.core.scrape_result import ScrapeResult
from oddsharvester.core.sport_market_registry import SportMarketRegistrar
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.command_enum import CommandEnum
from oddsharvester.utils.proxy_manager import ProxyManager
from oddsharvester.utils.utils import validate_and_convert_period

logger = logging.getLogger("ScraperApp")
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 20


async def run_scraper(
    command: CommandEnum,
    match_links: list | None = None,
    sport: str | None = None,
    date: str | None = None,
    leagues: list[str] | None = None,
    season: str | None = None,
    markets: list | None = None,
    max_pages: int | None = None,
    proxy_url: str | None = None,
    proxy_user: str | None = None,
    proxy_pass: str | None = None,
    browser_user_agent: str | None = None,
    browser_locale_timezone: str | None = None,
    browser_timezone_id: str | None = None,
    target_bookmaker: str | None = None,
    scrape_odds_history: bool = False,
    headless: bool = True,
    preview_submarkets_only: bool = False,
    bookies_filter: str = BookiesFilter.ALL.value,
    period: str | None = None,
) -> ScrapeResult | None:
    """
    Runs the scraping process and handles execution.

    Returns:
        ScrapeResult containing successful matches, failed URLs, and statistics.
        Returns None if a fatal error occurs during initialization.
    """

    bookies_filter_enum = BookiesFilter(bookies_filter)
    period_enum = validate_and_convert_period(period, sport)

    logger.info(
        f"Starting scraper with parameters: command={command}, match_links={match_links}, "
        f"sport={sport}, date={date}, leagues={leagues}, season={season}, markets={markets}, "
        f"max_pages={max_pages}, proxy_url={proxy_url}, browser_user_agent={browser_user_agent}, "
        f"browser_locale_timezone={browser_locale_timezone}, browser_timezone_id={browser_timezone_id}, "
        f"scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker}, "
        f"headless={headless}, preview_submarkets_only={preview_submarkets_only}, "
        f"bookies_filter={bookies_filter}, period={period}"
    )

    proxy_manager = ProxyManager(proxy_url=proxy_url, proxy_user=proxy_user, proxy_pass=proxy_pass)
    SportMarketRegistrar.register_all_markets()
    playwright_manager = PlaywrightManager()
    browser_helper = BrowserHelper()
    market_extractor = OddsPortalMarketExtractor(browser_helper=browser_helper)

    scraper = OddsPortalScraper(
        playwright_manager=playwright_manager,
        browser_helper=browser_helper,
        market_extractor=market_extractor,
        preview_submarkets_only=preview_submarkets_only,
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
                scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker},
                bookies_filter={bookies_filter}, period={period}
            """)
            return await retry_scrape(
                scraper.scrape_matches,
                match_links=match_links,
                sport=sport,
                markets=markets,
                scrape_odds_history=scrape_odds_history,
                target_bookmaker=target_bookmaker,
                bookies_filter=bookies_filter_enum,
                period=period_enum,
            )

        if command == CommandEnum.HISTORIC:
            if not sport or not leagues:
                raise ValueError("Both 'sport' and 'leagues' must be provided for historic scraping.")

            printable_season = season if season else "current"
            logger.info(
                "\n                Scraping historical odds for "
                f"sport={sport}, leagues={leagues}, season={printable_season}, "
                f"markets={markets}, scrape_odds_history={scrape_odds_history}, "
                f"target_bookmaker={target_bookmaker}, max_pages={max_pages}\n            "
            )

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
                    bookies_filter=bookies_filter_enum,
                    period=period_enum,
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
                    bookies_filter=bookies_filter_enum,
                    period=period_enum,
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
                        bookies_filter=bookies_filter_enum,
                        period=period_enum,
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
                        bookies_filter=bookies_filter_enum,
                        period=period_enum,
                    )
            else:
                logger.info(f"""
                    Scraping upcoming matches for sport={sport}, date={date}, markets={markets},
                    scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker},
                    bookies_filter={bookies_filter}, period={period}
                """)
                return await retry_scrape(
                    scraper.scrape_upcoming,
                    sport=sport,
                    date=date,
                    league=None,
                    markets=markets,
                    scrape_odds_history=scrape_odds_history,
                    target_bookmaker=target_bookmaker,
                    bookies_filter=bookies_filter_enum,
                    period=period_enum,
                )

        else:
            raise ValueError(f"Unknown command: {command}. Supported commands are 'upcoming-matches' and 'historic'.")

    except Exception as e:
        logger.error(f"An error occured: {e}")
        return None

    finally:
        await scraper.stop_playwright()


async def _scrape_multiple_leagues(scraper, scrape_func, leagues: list[str], sport: str, **kwargs) -> ScrapeResult:
    """
    Helper function to handle multi-league scraping with error handling and logging.

    Args:
        scraper: The scraper instance
        scrape_func: The function to call for each league (scrape_historic or scrape_upcoming)
        leagues: List of leagues to scrape
        sport: The sport being scraped
        **kwargs: Additional arguments to pass to the scrape function

    Returns:
        ScrapeResult: Merged results from all leagues with combined statistics.
    """
    combined_result = ScrapeResult()
    failed_leagues = []

    logger.info(f"Starting multi-league scraping for {len(leagues)} leagues: {leagues}")

    for i, league in enumerate(leagues, 1):
        try:
            logger.info(f"[{i}/{len(leagues)}] Processing league: {league}")

            league_result = await retry_scrape(scrape_func, sport=sport, league=league, **kwargs)

            if league_result and league_result.success:
                combined_result.merge(league_result)
                logger.info(
                    f"Successfully scraped {league_result.stats.successful} matches from league: {league} "
                    f"({league_result.stats.failed} failed)"
                )
            elif league_result:
                # Result exists but no successful matches
                combined_result.merge(league_result)
                logger.warning(f"No successful matches for league: {league} ({league_result.stats.failed} failed)")
            else:
                logger.warning(f"No data returned for league: {league}")

        except Exception as e:
            logger.error(f"Failed to scrape league '{league}': {e}")
            failed_leagues.append(league)
            continue

    successful_leagues = len(leagues) - len(failed_leagues)

    if failed_leagues:
        logger.warning(f"Failed to scrape {len(failed_leagues)} leagues: {failed_leagues}")

    logger.info(
        f"Multi-league scraping completed: {successful_leagues}/{len(leagues)} leagues successful, "
        f"{combined_result.stats.successful} total matches scraped, "
        f"{combined_result.stats.failed} failed ({combined_result.stats.success_rate:.1f}% success rate)"
    )

    return combined_result


async def retry_scrape(scrape_func, *args, **kwargs) -> ScrapeResult | None:
    """
    Retry a scrape function with exponential backoff for transient errors.

    Args:
        scrape_func: The async scraping function to execute.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.

    Returns:
        ScrapeResult from the scrape function, or None if max retries exceeded.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await scrape_func(*args, **kwargs)
        except Exception as e:
            if any(keyword in str(e) for keyword in TRANSIENT_ERROR_KEYWORDS):
                logger.warning(
                    f"[Attempt {attempt}] Transient error detected: {e}. Retrying in {RETRY_DELAY_SECONDS}s..."
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Non-retryable error encountered: {e}")
                raise
    logger.error("Max retries exceeded.")
    return None
