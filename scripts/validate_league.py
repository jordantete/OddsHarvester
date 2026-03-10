"""
Validate that league/season URLs on OddsPortal return match links.

Quick diagnostic tool to verify league URLs without running a full scrape.

Usage:
    # Single league
    uv run python scripts/validate_league.py -s football -l brazil-serie-a --season 2024

    # All leagues for a sport (current season)
    uv run python scripts/validate_league.py -s football --all
"""

import argparse
import asyncio
import logging
import re
import sys

from bs4 import BeautifulSoup
from playwright.async_api import Page

from oddsharvester.core.browser_helper import BrowserHelper
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.core.url_builder import URLBuilder
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL
from oddsharvester.utils.proxy_manager import ProxyManager
from oddsharvester.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from oddsharvester.utils.sport_market_constants import Sport


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate league/season URLs on OddsPortal.")
    parser.add_argument("-s", "--sport", required=True, choices=[s.value for s in Sport], help="Sport to validate.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-l", "--league", help="League slug (e.g., brazil-serie-a).")
    group.add_argument("--all", action="store_true", help="Validate all leagues for the sport.")
    parser.add_argument("--season", default=None, help="Season (e.g., 2024 or 2023-2024). Omit for current.")
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True, help="Run browser headless.")
    parser.add_argument("--proxy-url", default=None, help="Proxy URL.")
    parser.add_argument("--proxy-user", default=None, help="Proxy username.")
    parser.add_argument("--proxy-pass", default=None, help="Proxy password.")
    parser.add_argument("--user-agent", default=None, help="Custom browser user agent.")
    return parser.parse_args()


def extract_match_links(html_content: str) -> set[str]:
    soup = BeautifulSoup(html_content, "lxml")
    event_rows = soup.find_all(class_=re.compile(OddsPortalSelectors.EVENT_ROW_CLASS_PATTERN))
    return {
        f"{ODDSPORTAL_BASE_URL}{link['href']}"
        for row in event_rows
        for link in row.find_all("a", href=True)
        if len(link["href"].strip("/").split("/")) > 3
    }


async def validate_one(page: Page, bh: BrowserHelper, sport: str, league: str, season: str | None) -> bool:
    """Validate a single league/season. Returns True if match links found."""
    try:
        url = URLBuilder.get_historic_matches_url(sport=sport, league=league, season=season)
    except ValueError as e:
        print(f"  {league:<40} ERROR  {e}")
        return False

    try:
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await bh.dismiss_cookie_banner(page)
        await page.wait_for_timeout(7000)
        await bh.scroll_until_loaded(
            page=page,
            timeout=30,
            scroll_pause_time=2,
            max_scroll_attempts=3,
            content_check_selector="div[class*='eventRow']",
        )

        html_content = await page.content()
        match_links = extract_match_links(html_content)
        count = len(match_links)
        status = "OK" if count > 0 else "KO"
        print(f"  {league:<40} {status:>3}    {count:>3} links    {url}")
        return count > 0

    except Exception as e:
        print(f"  {league:<40}  KO    err    {url}  ({e})")
        return False


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

    # Setup proxy
    proxy_config = ProxyManager(
        proxy_url=args.proxy_url, proxy_user=args.proxy_user, proxy_pass=args.proxy_pass
    ).get_proxy()

    # Launch browser once, validate all leagues
    pm = PlaywrightManager()
    bh = BrowserHelper()
    ok_count = 0
    ko_count = 0

    try:
        await pm.initialize(headless=args.headless, user_agent=args.user_agent, proxy=proxy_config)

        for league in leagues:
            success = await validate_one(pm.page, bh, sport, league, args.season)
            if success:
                ok_count += 1
            else:
                ko_count += 1

    finally:
        await pm.cleanup()

    # Summary
    total = ok_count + ko_count
    print(f"\n{'='*70}")
    print(f"Results: {ok_count}/{total} OK, {ko_count} KO")

    return 0 if ko_count == 0 else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    args = parse_args()
    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)
