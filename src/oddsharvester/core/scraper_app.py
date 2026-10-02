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
from oddsharvester.core.retry import OPERATION_RETRY_CONFIG, RequestPacer, is_retryable_error, retry_with_backoff
from oddsharvester.core.scrape_options import ScrapeOptions
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult
from oddsharvester.core.sport_market_registry import SportMarketRegistrar
from oddsharvester.utils.command_enum import CommandEnum
from oddsharvester.utils.proxy_manager import ProxyManager

logger = logging.getLogger("ScraperApp")

Combo = tuple[str | None, str | None]


async def run_scraper(command: CommandEnum | str, **options: Any) -> ScrapeResult | None:
    """Run a scrape from keywords: the fields of `ScrapeOptions`, with their names and defaults."""
    return await run_scrape(ScrapeOptions(command=command, **options))


async def run_scrape(options: ScrapeOptions) -> ScrapeResult | None:
    """
    Runs the scrape `options` describes.

    Returns:
        ScrapeResult containing successful matches, failed URLs, and statistics.
        Returns None when the options cannot make a run or a fatal error stops it; the error is logged.
    """
    _log_start(options)

    if options.base_url:
        host = urlsplit(options.base_url).netloc.lower()
        if (
            host != "oddsportal.com"
            and not host.endswith(".oddsportal.com")
            and not options.browser_locale_timezone
            and not options.browser_timezone_id
        ):
            logger.warning(
                "Regional base URL '%s' is set but no --locale/--timezone provided. "
                "OddsPortal mirrors localise content; pass --locale and --timezone matching "
                "the region (see GitHub issue #45) for consistent results.",
                options.base_url,
            )

    proxy_manager = ProxyManager(
        proxy_urls=list(options.proxy_url), proxy_user=options.proxy_user, proxy_pass=options.proxy_pass
    )
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
        preview_submarkets_only=options.preview_submarkets_only,
        local_kickoff=options.local_kickoff,
        base_url=options.base_url,
        on_match=options.on_match,
    )

    try:
        _check(options)
        await scraper.start_playwright(
            headless=options.headless,
            browser_user_agent=options.browser_user_agent,
            browser_locale_timezone=options.browser_locale_timezone,
            browser_timezone_id=options.browser_timezone_id,
            proxy_manager=proxy_manager,
        )

        # Checked before the match-links branch: live scraping needs its own
        # in-play flow even when specific match links are supplied.
        if options.command is CommandEnum.LIVE:
            return await _scrape_live(scraper, options)
        if options.match_links and options.sport:
            return await _scrape_match_links(scraper, options)
        return await _scrape_listings(scraper, options)

    except Exception as e:
        logger.error(f"Scraping failed: {type(e).__name__}: {e}", exc_info=True)
        return None

    finally:
        await scraper.stop_playwright()


def _log_start(options: ScrapeOptions) -> None:
    proxies = [ProxyManager._sanitize_url_for_logging(url) for url in options.proxy_url]
    period = options.period.value if options.period else None
    logger.info(
        f"Starting scraper with parameters: command={options.command.value}, match_links={options.match_links}, "
        f"sport={options.sport}, date={options.date}, leagues={options.leagues}, seasons={options.seasons}, "
        f"markets={options.markets}, max_pages={options.max_pages}, proxy_url={proxies}, "
        f"browser_user_agent={options.browser_user_agent}, "
        f"browser_locale_timezone={options.browser_locale_timezone}, "
        f"browser_timezone_id={options.browser_timezone_id}, scrape_odds_history={options.scrape_odds_history}, "
        f"target_bookmaker={options.target_bookmaker}, headless={options.headless}, "
        f"preview_submarkets_only={options.preview_submarkets_only}, "
        f"bookies_filter={options.bookies_filter.value}, period={period}, base_url={options.base_url}, "
        f"local_kickoff={options.local_kickoff}"
    )


def _check(options: ScrapeOptions) -> None:
    """Raise ValueError for options no run can satisfy, before the browser starts."""
    if options.command is CommandEnum.LIVE:
        if not options.sport:
            raise ValueError("'sport' must be provided for live scraping.")
        return
    if options.match_links and options.sport:
        return
    if options.command is CommandEnum.HISTORIC and (not options.sport or not options.leagues):
        raise ValueError("Both 'sport' and 'leagues' must be provided for historic scraping.")
    if options.command is CommandEnum.UPCOMING_MATCHES and not options.date and not options.leagues:
        raise ValueError("Either 'date' or 'leagues' must be provided for upcoming matches scraping.")


async def _scrape_live(scraper: OddsPortalScraper, options: ScrapeOptions) -> ScrapeResult:
    logger.info(
        f"Scraping live matches for sport={options.sport}, leagues={options.leagues}, markets={options.markets}, "
        f"target_bookmaker={options.target_bookmaker}, bookies_filter={options.bookies_filter.value}"
    )
    return await retry_scrape(
        scraper.scrape_live,
        sport=options.sport,
        league=options.leagues[0] if options.leagues else None,
        markets=options.markets,
        match_links=list(options.match_links) if options.match_links else None,
        target_bookmaker=options.target_bookmaker,
        bookies_filter=options.bookies_filter,
        request_delay=options.request_delay,
        concurrent_scraping_task=options.concurrency_tasks,
        links_only=options.links_only,
    )


async def _scrape_match_links(scraper: OddsPortalScraper, options: ScrapeOptions) -> ScrapeResult:
    logger.info(
        f"Scraping specific matches: {options.match_links} for sport: {options.sport}, markets={options.markets}, "
        f"scrape_odds_history={options.scrape_odds_history}, target_bookmaker={options.target_bookmaker}, "
        f"bookies_filter={options.bookies_filter.value}, period={options.period}"
    )
    return await retry_scrape(
        scraper.scrape_matches,
        match_links=options.match_links,
        sport=options.sport,
        markets=options.markets,
        scrape_odds_history=options.scrape_odds_history,
        target_bookmaker=options.target_bookmaker,
        bookies_filter=options.bookies_filter,
        period=options.period,
        request_delay=options.request_delay,
        concurrent_scraping_task=options.concurrency_tasks,
    )


async def _scrape_listings(scraper: OddsPortalScraper, options: ScrapeOptions) -> ScrapeResult:
    """List the run's (league, season) combos, then scrape the matches they hold."""
    sport = options.sport

    if options.command is CommandEnum.HISTORIC:
        printable_seasons = ", ".join(options.seasons) if options.seasons else "current"
        logger.info(
            f"Scraping historical odds for sport={sport}, leagues={options.leagues}, seasons={printable_seasons}, "
            f"markets={options.markets}, scrape_odds_history={options.scrape_odds_history}, "
            f"target_bookmaker={options.target_bookmaker}, max_pages={options.max_pages}"
        )
        combos = [(league, season) for league in options.leagues for season in (options.seasons or [None])]

        async def collect_historic(league: str | None, season: str | None) -> ListingResult:
            return await scraper.collect_historic_links(
                sport=sport, league=league, season=season, max_pages=options.max_pages
            )

        def historic_context(league: str | None, season: str | None) -> dict[str, Any]:
            return {"sport": sport, "league": league, "season": season}

        collect, links_only_context = collect_historic, historic_context

    else:
        logger.info(
            f"Scraping upcoming matches for sport={sport}, date={options.date}, leagues={options.leagues}, "
            f"markets={options.markets}, scrape_odds_history={options.scrape_odds_history}, "
            f"target_bookmaker={options.target_bookmaker}"
        )
        combos = [(league, None) for league in (options.leagues or [None])]

        async def collect_upcoming(league: str | None, season: str | None) -> ListingResult:
            return await scraper.collect_upcoming_links(
                sport=sport,
                date=options.date,
                league=league,
                include_started=options.include_started,
                kickoff_within_hours=options.kickoff_within_hours,
                collect_kickoff=options.links_only,
            )

        def upcoming_context(league: str | None, season: str | None) -> dict[str, Any]:
            return {"sport": sport, "league": league, "date": options.date, "season": None}

        collect, links_only_context = collect_upcoming, upcoming_context

    return await _scrape_combos(
        scraper=scraper,
        combos=combos,
        collect=collect,
        links_only_context=links_only_context,
        concurrency=options.concurrency_tasks,
        request_delay=options.request_delay,
        links_only=options.links_only,
        odds_kwargs={
            "sport": sport,
            "markets": options.markets,
            "scrape_odds_history": options.scrape_odds_history,
            "target_bookmaker": options.target_bookmaker,
            "concurrent_scraping_task": options.concurrency_tasks,
            "preview_submarkets_only": scraper.preview_submarkets_only,
            "bookies_filter": options.bookies_filter,
            "period": options.period,
            "request_delay": options.request_delay,
        },
    )


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
                result.add_failure(_combo_failure(league, season, listing_errors[index]))
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
            result.add_failure(_combo_failure(*combos[index], listing_errors[index]))
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
    retry_result = await retry_with_backoff(scrape_func, *args, config=OPERATION_RETRY_CONFIG, **kwargs)

    if retry_result.success:
        return retry_result.result

    if retry_result.is_retryable:
        logger.error(f"Max retries exceeded after {retry_result.attempts} attempts: {retry_result.last_error}")
    else:
        logger.error(f"Non-retryable error encountered: {retry_result.last_error}")
    raise retry_result.exception
