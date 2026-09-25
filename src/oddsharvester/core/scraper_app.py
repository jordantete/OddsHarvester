import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import Any
from urllib.parse import urlsplit

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.market_navigation import MarketTabNavigator
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.browser.selection import SelectionManager
from oddsharvester.core.exceptions import ScraperError, SeasonNotFoundError
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import ListingResult, OddsPortalScraper
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.retry import RequestPacer, RetryConfig, is_retryable_error, retry_with_backoff
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult
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

Combo = tuple[str | None, str | None]


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
    on_match: Callable[[dict[str, Any]], None] | None = None,
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
        on_match=on_match,
    )

    try:
        await scraper.start_playwright(
            headless=headless,
            browser_user_agent=browser_user_agent,
            browser_locale_timezone=browser_locale_timezone,
            browser_timezone_id=browser_timezone_id,
            proxy_manager=proxy_manager,
        )

        # Checked before the generic match_links branch: live scraping needs its own
        # in-play flow even when specific match links are supplied.
        if command == CommandEnum.LIVE:
            if not sport:
                raise ValueError("'sport' must be provided for live scraping.")

            logger.info(f"""
                Scraping live matches for sport={sport}, leagues={leagues}, markets={markets},
                target_bookmaker={target_bookmaker}, bookies_filter={bookies_filter}
            """)
            return await retry_scrape(
                scraper.scrape_live,
                sport=sport,
                league=leagues[0] if leagues else None,
                markets=markets,
                match_links=list(match_links) if match_links else None,
                target_bookmaker=target_bookmaker,
                bookies_filter=bookies_filter_enum,
                request_delay=request_delay,
                concurrent_scraping_task=concurrency_tasks,
                links_only=links_only,
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

        odds_kwargs = {
            "sport": sport,
            "markets": markets,
            "scrape_odds_history": scrape_odds_history,
            "target_bookmaker": target_bookmaker,
            "concurrent_scraping_task": concurrency_tasks,
            "preview_submarkets_only": preview_submarkets_only,
            "bookies_filter": bookies_filter_enum,
            "period": period_enum,
            "request_delay": request_delay,
        }

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
            combos = [(league, season) for league in leagues for season in (seasons or [None])]

            async def collect_historic(league: str | None, season: str | None) -> ListingResult:
                return await scraper.collect_historic_links(
                    sport=sport, league=league, season=season, max_pages=max_pages
                )

            def historic_context(league: str | None, season: str | None) -> dict[str, Any]:
                return {"sport": sport, "league": league, "season": season}

            collect, links_only_context = collect_historic, historic_context

        elif command == CommandEnum.UPCOMING_MATCHES:
            if not date and not leagues:
                raise ValueError("Either 'date' or 'leagues' must be provided for upcoming matches scraping.")

            logger.info(f"""
                Scraping upcoming matches for sport={sport}, date={date}, leagues={leagues}, markets={markets},
                scrape_odds_history={scrape_odds_history}, target_bookmaker={target_bookmaker}
            """)
            combos = [(league, None) for league in (leagues or [None])]

            async def collect_upcoming(league: str | None, season: str | None) -> ListingResult:
                return await scraper.collect_upcoming_links(
                    sport=sport,
                    date=date,
                    league=league,
                    include_started=include_started,
                    kickoff_within_hours=kickoff_within_hours,
                    collect_kickoff=links_only,
                )

            def upcoming_context(league: str | None, season: str | None) -> dict[str, Any]:
                return {"sport": sport, "league": league, "date": date, "season": None}

            collect, links_only_context = collect_upcoming, upcoming_context

        else:
            raise ValueError(
                f"Unknown command: {command}. Supported commands are 'upcoming-matches', 'historic' and 'live'."
            )

        return await _scrape_combos(
            scraper=scraper,
            combos=combos,
            collect=collect,
            links_only_context=links_only_context,
            concurrency=concurrency_tasks,
            request_delay=request_delay,
            links_only=links_only,
            odds_kwargs=odds_kwargs,
        )

    except Exception as e:
        logger.error(f"Scraping failed: {type(e).__name__}: {e}", exc_info=True)
        return None

    finally:
        await scraper.stop_playwright()


def _combo_label(league: str | None, season: str | None) -> str:
    if league is None:
        return "all leagues"
    return f"{league} {season}" if season is not None else league


def _combo_stat(
    league: str | None, season: str | None, successful: int = 0, failed: int = 0, errored: bool = False
) -> dict[str, Any]:
    return {"league": league, "season": season, "successful": successful, "failed": failed, "errored": errored}


def _combo_failure(league: str | None, season: str | None, error: Exception | None) -> FailedUrl:
    """A combo whose listing failed hides all its matches, so it counts as one failed listing."""
    label = _combo_label(league, season)
    reason = f"{type(error).__name__}: {error}" if error else "no listing returned"
    is_scraper_error = isinstance(error, ScraperError)
    is_retryable = error.is_retryable if is_scraper_error else is_retryable_error(str(error or ""))
    url = error.url if is_scraper_error else None
    return FailedUrl(
        url=url or label,
        error_type=ErrorType.LISTING_PAGE,
        error_message=f"Listing failed for {label}: {reason}",
        is_retryable=is_retryable,
    )


def _add_failure(result: ScrapeResult, failure: FailedUrl) -> None:
    result.failed.append(failure)
    result.stats.failed += 1
    result.stats.total_urls += 1


async def _scrape_combos(
    scraper: OddsPortalScraper,
    combos: list[Combo],
    collect: Callable[..., Awaitable[ListingResult]],
    links_only_context: Callable[[str | None, str | None], dict[str, Any]],
    concurrency: int,
    request_delay: float,
    links_only: bool,
    odds_kwargs: dict[str, Any],
) -> ScrapeResult:
    """
    List every (league, season) combo in parallel, then scrape all matches in one batch.

    Listings run at most `concurrency` at a time, paced like match pages, each under
    the operation-level retry. A combo whose listing fails for good is recorded as
    errored and the others go on. The odds phase is a single `extract_match_odds`
    call over the flat, deduplicated link list, so `concurrency` stays the one cap
    on open pages. Results are attributed back to their combo through the link.

    Args:
        scraper: The scraper instance
        combos: (league, season) pairs, league outer, season inner
        collect: Async callable awaited as collect(league=..., season=...), returning a ListingResult
        links_only_context: Builds the context columns of a links-only row for a combo
        concurrency: Max listings in flight; also the odds-phase cap via odds_kwargs
        request_delay: Base delay between listing requests, jittered
        links_only: Stop after the listing phase
        odds_kwargs: Forwarded to `extract_match_odds` alongside `match_links`

    Returns:
        ScrapeResult: Merged results, with a per-combo breakdown in `combo_stats`.
    """
    logger.info(f"Starting scraping for {len(combos)} league/season combo(s)")

    listings: list[ListingResult | None] = [None] * len(combos)
    listing_errors: list[Exception | None] = [None] * len(combos)
    semaphore = asyncio.Semaphore(concurrency)
    pacer = RequestPacer(request_delay)

    async def list_combo(index: int, league: str | None, season: str | None) -> None:
        label = _combo_label(league, season)
        async with semaphore:
            await pacer.wait()
            logger.info(f"[{index + 1}/{len(combos)}] Listing: {label}")
            try:
                listings[index] = await retry_scrape(collect, league=league, season=season)
                if listings[index] is None:
                    logger.warning(f"No data returned for {label}")
            except SeasonNotFoundError:
                logger.info(f"Season does not exist for {label}, counting as zero links")
                listings[index] = ListingResult()
            except Exception as e:
                listing_errors[index] = e
                logger.error(f"Failed to scrape {label}: {e}")

    await asyncio.gather(*(list_combo(i, league, season) for i, (league, season) in enumerate(combos)))

    # A link seen by two combos is scraped once and attributed to the first.
    link_to_combo: dict[str, int] = {}
    for index, listing in enumerate(listings):
        for row in listing.rows if listing else []:
            link_to_combo.setdefault(row["match_link"], index)

    errored = sum(listing is None for listing in listings)
    logger.info(f"Collected {len(link_to_combo)} unique links across {len(combos)} combo(s) ({errored} errored)")

    if links_only:
        result = ScrapeResult()
        for index, (league, season) in enumerate(combos):
            listing = listings[index]
            if listing is None:
                result.combo_stats.append(_combo_stat(league, season, errored=True))
                _add_failure(result, _combo_failure(league, season, listing_errors[index]))
                continue
            rows = [row for row in listing.rows if link_to_combo[row["match_link"]] == index]
            combo_result = ScrapeResult.from_links(
                rows=rows, context=links_only_context(league, season), failed_page_urls=listing.failed_page_urls
            )
            result.merge(combo_result)
            result.combo_stats.append(
                _combo_stat(league, season, combo_result.stats.successful, combo_result.stats.failed)
            )
        _log_completion(result, combos)
        return result

    result = ScrapeResult()
    if link_to_combo:
        result = await scraper.extract_match_odds(match_links=list(link_to_combo), **odds_kwargs)

    successful = [0] * len(combos)
    failed = [0] * len(combos)
    for row in result.success:
        index = link_to_combo.get(row.get("match_link"))
        if index is None:
            continue
        row["season"] = combos[index][1]
        successful[index] += 1
    for failure in result.failed:
        index = link_to_combo.get(failure.url)
        if index is not None:
            failed[index] += 1
    for index, listing in enumerate(listings):
        if listing is None:
            _add_failure(result, _combo_failure(*combos[index], listing_errors[index]))
        elif listing.failed_page_urls:
            result.add_listing_failures(listing.failed_page_urls)
            failed[index] += len(listing.failed_page_urls)

    result.combo_stats = [
        _combo_stat(league, season, successful[i], failed[i], errored=listings[i] is None)
        for i, (league, season) in enumerate(combos)
    ]
    _log_completion(result, combos)
    return result


def _log_completion(result: ScrapeResult, combos: list[Combo]) -> None:
    errored = [c for c in result.combo_stats if c["errored"]]
    if errored:
        logger.warning(f"Failed to scrape {len(errored)} combo(s)")

    logger.info(
        f"Scraping completed: {len(combos) - len(errored)}/{len(combos)} combos successful, "
        f"{result.stats.successful} total matches scraped, "
        f"{result.stats.failed} failed ({result.stats.success_rate:.1f}% success rate)"
    )


async def retry_scrape(scrape_func, *args, **kwargs):
    """
    Retry a scrape function with exponential backoff for transient errors.

    Uses the unified retry_with_backoff mechanism with operation-level retry config
    (larger delays suitable for full scraping operations).

    Args:
        scrape_func: The async scraping function to execute.
        *args: Positional arguments for the function.
        **kwargs: Keyword arguments for the function.

    Returns:
        The scrape function's result.

    Raises:
        The last exception the function raised, once it is not retryable or the attempts run out.
    """
    config = RetryConfig(
        max_attempts=OPERATION_RETRY_MAX_ATTEMPTS,
        base_delay=OPERATION_RETRY_BASE_DELAY,
        max_delay=OPERATION_RETRY_MAX_DELAY,
    )

    retry_result = await retry_with_backoff(scrape_func, *args, config=config, **kwargs)

    if retry_result.success:
        return retry_result.result

    if retry_result.is_retryable:
        logger.error(f"Max retries exceeded after {retry_result.attempts} attempts: {retry_result.last_error}")
    else:
        logger.error(f"Non-retryable error encountered: {retry_result.last_error}")
    raise retry_result.exception
