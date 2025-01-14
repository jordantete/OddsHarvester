import argparse
from typing import NamedTuple

class ScraperArgs(NamedTuple):
    sport: str
    league: str | None
    season: str | None
    date: str | None
    storage: str
    headless: bool

def parse_args() -> ScraperArgs:
    parser = argparse.ArgumentParser(description='Odds Portal Scraper')
    
    parser.add_argument('--sport', type=str, default='football', help='Sport to scrape (default: football)')
    parser.add_argument('--league', type=str,help='League to scrape (e.g., premier-league)')
    parser.add_argument('--season', type=str, help='Season to scrape (format: YYYY-YYYY)')
    parser.add_argument('--date', type=str, help='Date to scrape (format: YYYYMMDD)')
    parser.add_argument('--storage', type=str, choices=['local', 'remote'], default='local', help='Storage type (default: local)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    args = parser.parse_args()
    
    return ScraperArgs(
        sport=args.sport,
        league=args.league,
        season=args.season,
        date=args.date,
        storage=args.storage,
        headless=args.headless
    ) 