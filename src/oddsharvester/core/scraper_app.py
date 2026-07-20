import logging
from urllib.parse import urlsplit

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.market_navigation import MarketTabNavigator
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.browser.selection import SelectionManager
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import OddsPortalScraper
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import RetryConfig, is_retryable_error, retry_with_backoff
from oddsharvester.core.scrape_result import ScrapeResult
from oddsharvester.core.sport_market_registry import SportMarketRegistrar
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.command_enum import CommandEnum
from oddsharvester.utils.constants import (
    DEFAULT_REQUEST_DELAY_S,
    OPERATION_RETRY_BASE_DELAY,
    OPERATION_RETRY_MAX_ATTEMPTS,
    OPERATION_RETRY_MAX_DELAY,
)
from oddsharvester.utils.proxy_manager import ProxyManager
from oddsharvester.utils.utils import validate_and_convert_period

logger = logging.getLogger("ScraperApp")


async def run_scraper(
    command: CommandEnum,
    match_links: list | None = None,
    sport: str | None = None,
    date: str | None = None,
    leagues: list[str] | None = None,
    seasons: list[str] | None = None,
    markets: list | None = None,
    max_pages: int | None = None,
    proxy_url: str | None = None,
    proxy_user: str | None = None,
    proxy_pass: str | None = None,
    browser_user_agent: str | None = None,
    browser_locale_timezone: str | None = None,
    browser_timezone_id: str | None = None,
    base_url: str | None = None,
    target_bookmaker: str | None = None,
    scrape_odds_history: bool = False,
    headless: bool = True,
    preview_submarkets_only: bool = False,
    bookies_filter: str = BookiesFilter.ALL.value,
    period: str | None = None,
    request_delay: float = DEFAULT_REQUEST_DELAY_S,
    concurrency_tasks: int = 3,
    include_started: bool = False,
    kickoff_within_hours: float | None = None,
    links_only: bool = False,
    local_kickoff: bool = False,
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
        f"sport={sport}, date={date}, leagues={leagues}, seasons={seasons}, markets={markets}, "
        f"max_pages={max_pages}, proxy_url={proxy_url}, browser_user_agent={browser_user_agent}, "
        f"browser_locale_timezone={browser_locale_timezone}, browser_timezone_id={browser_timezone_id}, "
        f"scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker}, "
        f"headless={headless}, preview_submarkets_only={preview_submarkets_only}, "
        f"bookies_filter={bookies_filter}, period={period}, base_url={base_url}, local_kickoff={local_kickoff}"
    )

    if base_url:
        host = urlsplit(base_url).netloc.lower()
        if (
            host != "oddsportal.com"
            and not host.endswith(".oddsportal.com")
            and not browser_locale_timezone
            and not browser_timezone_id
        ):
            logger.warning(
                "Regional base URL '%s' is set but no --locale/--timezone provided. "
                "OddsPortal mirrors localise content; pass --locale and --timezone matching "
                "the region (see GitHub issue #45) for consistent results.",
                base_url,
            )

    if isinstance(proxy_url, list | tuple):
        proxy_manager = ProxyManager(proxy_urls=list(proxy_url), proxy_user=proxy_user, proxy_pass=proxy_pass)
    else:
        proxy_manager = ProxyManager(proxy_url=proxy_url, proxy_user=proxy_user, proxy_pass=proxy_pass)
    SportMarketRegistrar.register_all_markets()
    playwright_manager = PlaywrightManager()
    cookie_dismisser = CookieDismisser()
    selection_manager = SelectionManager()
    tab_navigator = MarketTabNavigator()
    scroller = PageScroller()

    market_extractor = OddsPortalMarketExtractor(
        scroller=scroller,
        tab_navigator=tab_navigator,
        selection_manager=selection_manager,
    )

    scraper = OddsPortalScraper(
        playwright_manager=playwright_manager,
        market_extractor=market_extractor,
        scroller=scroller,
        cookie_dismisser=cookie_dismisser,
        selection_manager=selection_manager,
        preview_submarkets_only=preview_submarkets_only,
        local_kickoff=local_kickoff,
        base_url=base_url,
    )

    try:
        await scraper.start_playwright(
            headless=headless,
            browser_user_agent=browser_user_agent,
            browser_locale_timezone=browser_locale_timezone,
            browser_timezone_id=browser_timezone_id,
            proxy_manager=proxy_manager,
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
                request_delay=request_delay,
                concurrent_scraping_task=concurrency_tasks,
            )

        if command == CommandEnum.HISTORIC:
            if not sport or not leagues:
                raise ValueError("Both 'sport' and 'leagues' must be provided for historic scraping.")

            printable_seasons = ", ".join(seasons) if seasons else "current"
            logger.info(
                "\n                Scraping historical odds for "
                f"sport={sport}, leagues={leagues}, seasons={printable_seasons}, "
                f"markets={markets}, scrape_odds_history={scrape_odds_history}, "
                f"target_bookmaker={target_bookmaker}, max_pages={max_pages}\n            "
            )

            if len(leagues) == 1 and len(seasons or [None]) == 1:
                return await retry_scrape(
                    scraper.scrape_historic,
                    sport=sport,
                    league=leagues[0],
                    season=seasons[0] if seasons else None,
                    markets=markets,
                    scrape_odds_history=scrape_odds_history,
                    target_bookmaker=target_bookmaker,
                    max_pages=max_pages,
                    bookies_filter=bookies_filter_enum,
                    period=period_enum,
                    request_delay=request_delay,
                    concurrent_scraping_task=concurrency_tasks,
                    links_only=links_only,
                )
            else:
                return await _scrape_league_season_combos(
                    scraper=scraper,
                    scrape_func=scraper.scrape_historic,
                    leagues=leagues,
                    seasons=seasons or [None],
                    sport=sport,
                    markets=markets,
                    scrape_odds_history=scrape_odds_history,
                    target_bookmaker=target_bookmaker,
                    max_pages=max_pages,
                    bookies_filter=bookies_filter_enum,
                    period=period_enum,
                    request_delay=request_delay,
                    concurrent_scraping_task=concurrency_tasks,
                    links_only=links_only,
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
                        request_delay=request_delay,
                        concurrent_scraping_task=concurrency_tasks,
                        include_started=include_started,
                        kickoff_within_hours=kickoff_within_hours,
                        links_only=links_only,
                    )
                else:
                    return await _scrape_league_season_combos(
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
                        request_delay=request_delay,
                        concurrent_scraping_task=concurrency_tasks,
                        include_started=include_started,
                        kickoff_within_hours=kickoff_within_hours,
                        links_only=links_only,
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
                    request_delay=request_delay,
                    concurrent_scraping_task=concurrency_tasks,
                    include_started=include_started,
                    kickoff_within_hours=kickoff_within_hours,
                    links_only=links_only,
                )

        else:
            raise ValueError(f"Unknown command: {command}. Supported commands are 'upcoming-matches' and 'historic'.")

    except Exception as e:
        logger.error(f"An error occured: {e}")
        return None

    finally:
        await scraper.stop_playwright()


async def _scrape_league_season_combos(
    scraper,
    scrape_func,
    leagues: list[str],
    sport: str,
    seasons: list[str] | None = None,
    **kwargs,
) -> ScrapeResult:
    """
    Scrape every (league, season) combination sequentially, league outer.

    `seasons=None` degenerates to one pass per league with no `season` kwarg,
    which is the upcoming-matches behaviour (`scrape_upcoming` has no such parameter).

    Args:
        scraper: The scraper instance
        scrape_func: scrape_historic or scrape_upcoming
        leagues: Leagues to scrape
        sport: The sport being scraped
        seasons: Seasons to scrape per league, or None for a seasonless run
        **kwargs: Additional arguments forwarded to the scrape function

    Returns:
        ScrapeResult: Merged results, with a per-combo breakdown in `combo_stats`.
    """
    combined_result = ScrapeResult()
    pass_season = seasons is not None
    combos = [(league, season) for league in leagues for season in (seasons or [None])]

    logger.info(f"Starting scraping for {len(combos)} league/season combo(s)")

    for i, (league, season) in enumerate(combos, 1):
        label = f"{league} {season}" if season is not None else league
        combo_kwargs = {**kwargs, "season": season} if pass_season else kwargs

        try:
            logger.info(f"[{i}/{len(combos)}] Processing: {label}")

            combo_result = await retry_scrape(scrape_func, sport=sport, league=league, **combo_kwargs)

            if combo_result is None:
                logger.warning(f"No data returned for {label}")
                combined_result.combo_stats.append(
                    {"league": league, "season": season, "successful": 0, "failed": 0, "errored": True}
                )
                continue

            combined_result.merge(combo_result)
            combined_result.combo_stats.append(
                {
                    "league": league,
                    "season": season,
                    "successful": combo_result.stats.successful,
                    "failed": combo_result.stats.failed,
                    "errored": False,
                }
            )

            if combo_result.success:
                logger.info(
                    f"Successfully scraped {combo_result.stats.successful} matches from {label} "
                    f"({combo_result.stats.failed} failed)"
                )
            else:
                logger.warning(f"No successful matches for {label} ({combo_result.stats.failed} failed)")

        except Exception as e:
            logger.error(f"Failed to scrape {label}: {e}")
            combined_result.combo_stats.append(
                {"league": league, "season": season, "successful": 0, "failed": 0, "errored": True}
            )
            continue

    errored = [c for c in combined_result.combo_stats if c["errored"]]
    if errored:
        logger.warning(f"Failed to scrape {len(errored)} combo(s)")

    logger.info(
        f"Scraping completed: {len(combos) - len(errored)}/{len(combos)} combos successful, "
        f"{combined_result.stats.successful} total matches scraped, "
        f"{combined_result.stats.failed} failed ({combined_result.stats.success_rate:.1f}% success rate)"
    )

    return combined_result


async def retry_scrape(scrape_func, *args, **kwargs) -> ScrapeResult | None:
    """
    Retry a scrape function with exponential backoff for transient errors.

    Uses the unified retry_with_backoff mechanism with operation-level retry config
    (larger delays suitable for full scraping operations).

    Args:
        scrape_func: The async scraping function to execute.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.

    Returns:
        ScrapeResult from the scrape function, or None if max retries exceeded.

    Raises:
        Exception: Re-raises non-retryable errors immediately.
    """
    config = RetryConfig(
        max_attempts=OPERATION_RETRY_MAX_ATTEMPTS,
        base_delay=OPERATION_RETRY_BASE_DELAY,
        max_delay=OPERATION_RETRY_MAX_DELAY,
    )

    retry_result = await retry_with_backoff(scrape_func, *args, config=config, **kwargs)

    if retry_result.success:
        return retry_result.result

    # Preserve existing contract: non-retryable errors are re-raised
    if retry_result.last_error and not is_retryable_error(retry_result.last_error):
        logger.error(f"Non-retryable error encountered: {retry_result.last_error}")
        raise Exception(retry_result.last_error)

    logger.error(f"Max retries exceeded after {retry_result.attempts} attempts.")
    return None
