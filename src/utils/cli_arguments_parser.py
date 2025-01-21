import argparse, re
from typing import NamedTuple, List
from storage.storage_type import StorageType
from utils.utils import parse_over_under_market
from utils.constants import SUPPORTED_SPORTS, SUPPORTED_MARKETS, FOOTBALL_LEAGUES_URLS_MAPPING, DATE_FORMAT_REGEX

class ScraperArgs(NamedTuple):
    sport: str
    league: str | None
    season: str | None
    date: str | None
    storage: str
    headless: bool
    markets: List[str]

def validate_args(args: argparse.Namespace):
    """
    Validate parsed CLI arguments.
    """
    errors = []

    # Validate markets
    for market in args.markets:
        if market.startswith("over_under_"):
            try:
                parse_over_under_market(market)
            except ValueError as e:
                errors.append(str(e))
        elif market not in SUPPORTED_MARKETS:
            errors.append(f"Invalid market: {market}. Supported markets are: {', '.join(SUPPORTED_MARKETS)}.")

    # Validate sport
    if args.sport not in SUPPORTED_SPORTS:
        errors.append(f"Invalid sport: '{args.sport}'. Supported sports are: {', '.join(SUPPORTED_SPORTS)}.")

    # Validate league
    if args.league and args.league not in FOOTBALL_LEAGUES_URLS_MAPPING:
        errors.append(f"Invalid league: '{args.league}'. Supported leagues are: {', '.join(FOOTBALL_LEAGUES_URLS_MAPPING.keys())}.")

    # Validate date
    if args.date and not re.match(DATE_FORMAT_REGEX, args.date):
        errors.append(f"Invalid date format: '{args.date}'. Date must be in the format YYYY-MM-DD.")

    # Validate storage
    try:
        StorageType(args.storage)
    except ValueError:
        errors.append(f"Invalid storage type: '{args.storage}'. Supported storage types are: {', '.join([e.value for e in StorageType])}")

    # Raise errors if any
    if errors:
        raise ValueError("\n".join(errors))

def parse_args() -> ScraperArgs:
    """
    Parse and validate CLI arguments for OddsPortalScrapperApp.
    """
    parser = argparse.ArgumentParser(description='Odds Portal Scraper')
    
    parser.add_argument('--sport', type=str, default='football', help='Sport to scrape (default: football)')
    parser.add_argument('--league', type=str, help='League to scrape (e.g., premier-league)')
    parser.add_argument('--season', type=str, help='Season to scrape (format: YYYY-YYYY)')
    parser.add_argument('--date', type=str, help='Date to scrape (format: YYYYMMDD)')
    parser.add_argument('--storage', type=str, choices=['local', 'remote'], default='local', help='Storage type (default: local)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument(
        "--markets",
        type=str,
        nargs="+",
        default=["1x2"],
        help="List of markets to scrape (e.g., '1x2', 'over_under_2_5'). Default is ['1x2']."
    )
    
    args = parser.parse_args()
    validate_args(args)

    return ScraperArgs(
        sport=args.sport,
        league=args.league,
        season=args.season,
        date=args.date,
        storage=args.storage,
        headless=args.headless,
        markets=args.markets
    )