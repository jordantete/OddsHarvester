"""
Validate that league/season URLs on OddsPortal return match links.

Quick diagnostic tool to verify league URLs without running a full scrape.

Usage:
    # Single league
    uv run python scripts/validate_league.py -s football -l brazil-serie-a --season 2024

    # All leagues for a sport (current season)
    uv run python scripts/validate_league.py -s football --all

    # Season selector map: every season with the slug it actually lives under.
    # This is what LEAGUE_SEASON_ALIASES is built from (gotcha 4).
    uv run python scripts/validate_league.py -s football -l spain-laliga --dump-seasons
"""

import argparse
import asyncio
import logging
import re
import sys

from playwright.async_api import Page

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.market_navigation import MarketTabNavigator
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.browser.selection import SelectionManager
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import OddsPortalScraper
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.url_builder import URLBuilder
from oddsharvester.utils.proxy_manager import ProxyManager
from oddsharvester.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from oddsharvester.utils.sport_market_constants import Sport

SEASON_HREF_PATTERN = re.compile(r"^/(?P<sport>[^/]+)/(?P<country>[^/]+)/(?P<slug>.+?)-(?P<season>\d{4}(?:-\d{4})?)/")


def build_scraper(playwright_manager: PlaywrightManager) -> OddsPortalScraper:
    scroller = PageScroller()
    selection_manager = SelectionManager()
    return OddsPortalScraper(
        playwright_manager=playwright_manager,
        market_extractor=OddsPortalMarketExtractor(
            scroller=scroller,
            tab_navigator=MarketTabNavigator(),
            selection_manager=selection_manager,
        ),
        scroller=scroller,
        cookie_dismisser=CookieDismisser(),
        selection_manager=selection_manager,
    )


async def load_listing(page: Page, scraper: OddsPortalScraper, url: str) -> None:
    await page.goto(url, timeout=30000, wait_until="domcontentloaded")
    await scraper.cookie_dismisser.dismiss(page)
    await page.wait_for_timeout(5000)
    await scraper.scroller.scroll_until_loaded(
        page=page,
        timeout=30,
        scroll_pause_time=2,
        max_scroll_attempts=3,
        content_check_selector=OddsPortalSelectors.LISTING_ROW_SELECTOR,
    )


async def validate_one(
    page: Page,
    scraper: OddsPortalScraper,
    sport: str,
    league: str,
    season: str | None,
) -> bool:
    """Validate a single league/season. Returns True if match links found."""
    try:
        url = URLBuilder.get_historic_matches_url(sport=sport, league=league, season=season)
    except ValueError as e:
        print(f"  {league:<40} ERROR  {e}")
        return False

    try:
        await load_listing(page, scraper, url)
        links = await scraper.extract_match_links(page=page)
        count = len(set(links))
        status = "OK" if count > 0 else "KO"
        print(f"  {league:<40} {status:>3}    {count:>3} links    {url}")
        return count > 0

    except Exception as e:
        print(f"  {league:<40}  KO    err    {url}  ({e})")
        return False


async def dump_seasons(page: Page, scraper: OddsPortalScraper, sport: str, league: str) -> bool:
    """Print the season selector map of a league: season -> the slug it lives under."""
    url = URLBuilder.get_historic_matches_url(sport=sport, league=league, season=None)

    try:
        await load_listing(page, scraper, url)
        hrefs = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    except Exception as e:
        print(f"  {league:<40}  KO    err    {url}  ({e})")
        return False

    # The page also links to unrelated competitions (a World Cup promo, for one), so keep
    # only the seasons under this league's own country.
    country = URLBuilder.get_league_url(sport, league).rstrip("/").split("/")[-2]

    seasons: dict[str, str] = {}
    for href in dict.fromkeys(h for h in hrefs if h):
        match = SEASON_HREF_PATTERN.match(href)
        if match and match["sport"] == sport and match["country"] == country:
            seasons[match["season"]] = f"{match['country']}/{match['slug']}"

    if not seasons:
        print(f"  {league:<40} no season links found on {url}")
        return False

    print(f"  {league}")
    for season, slug in sorted(seasons.items()):
        print(f"      {season:<10} {slug}")
    return True


async def run(args: argparse.Namespace) -> int:
    sport = args.sport
    season_label = args.season or "current"

    # Determine leagues to validate
    if args.all:
        sport_enum = Sport(sport)
        leagues = list(SPORTS_LEAGUES_URLS_MAPPING.get(sport_enum, {}).keys())
        print(f"\nValidating {len(leagues)} {sport} leagues (season: {season_label})...\n")
    else:
        leagues = [args.league]
        print(f"\nValidating {args.league} (season: {season_label})...\n")

    proxy_manager = ProxyManager(proxy_url=args.proxy_url, proxy_user=args.proxy_user, proxy_pass=args.proxy_pass)

    # Launch browser once, validate all leagues
    pm = PlaywrightManager()
    scraper = build_scraper(pm)
    ok_count = 0
    ko_count = 0

    try:
        await pm.initialize(headless=args.headless, user_agent=args.user_agent, proxy_manager=proxy_manager)

        for league in leagues:
            if args.dump_seasons:
                success = await dump_seasons(pm.page, scraper, sport, league)
            else:
                success = await validate_one(pm.page, scraper, sport, league, args.season)
            if success:
                ok_count += 1
            else:
                ko_count += 1

    finally:
        await pm.cleanup()

    # Summary
    total = ok_count + ko_count
    print(f"\n{'=' * 70}")
    print(f"Results: {ok_count}/{total} OK, {ko_count} KO")

    return 0 if ko_count == 0 else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate league/season URLs on OddsPortal.")
    parser.add_argument("-s", "--sport", required=True, choices=[s.value for s in Sport], help="Sport to validate.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", "--league", help="League slug (e.g., brazil-serie-a).")
    group.add_argument("--all", action="store_true", help="Validate all leagues for the sport.")
    parser.add_argument("--season", default=None, help="Season (e.g., 2024 or 2023-2024). Omit for current.")
    parser.add_argument(
        "--dump-seasons",
        action="store_true",
        help="Print each season with the slug it lives under, instead of validating one season.",
    )
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True, help="Run browser headless.")
    parser.add_argument("--proxy-url", default=None, help="Proxy URL.")
    parser.add_argument("--proxy-user", default=None, help="Proxy username.")
    parser.add_argument("--proxy-pass", default=None, help="Proxy password.")
    parser.add_argument("--user-agent", default=None, help="Custom browser user agent.")
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    args = parse_args()
    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)
