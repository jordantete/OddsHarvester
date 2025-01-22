import argparse, re
from datetime import datetime
from typing import List, Optional
from utils.constants import SUPPORTED_SPORTS, SUPPORTED_MARKETS, FOOTBALL_LEAGUES_URLS_MAPPING, DATE_FORMAT_REGEX
from utils.utils import parse_over_under_market
from utils.command_enum import CommandEnum
from storage.storage_type import StorageType

class CLIArgumentHandler:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="OddsHarvester CLI for scraping betting odds data.",
            epilog="Examples:\n"
                "  Scrape upcoming matches:\n"
                "    python main.py scrape-upcoming --sport football --date 20250101 --markets 1x2, btts\n"
                "  Scrape historical odds:\n"
                "    python main.py scrape-historic --league premier-league --season 2022-2023\n",
            formatter_class=argparse.RawTextHelpFormatter
        )
        self._initialize_subparsers()

    def _initialize_subparsers(self):
        subparsers = self.parser.add_subparsers(
            title="Commands", dest="command",
            help="Specify whether you want to scrape upcoming matches or historical odds."
        )

        # Upcoming matches
        upcoming_parser = subparsers.add_parser("scrape-upcoming", help="Scrape odds for upcoming matches.")
        upcoming_parser.add_argument("--sport", type=str, required=True, help="The sport to scrape (e.g., football).")
        upcoming_parser.add_argument("--date", type=str, required=True, help="Date for upcoming matches (YYYY-MM-DD).")
        upcoming_parser.add_argument("--league", type=str, help="Specific league to target for upcoming matches (e.g., premier-league).")
        upcoming_parser.add_argument(
            "--markets",
            type=str,
            default="1x2",
            help=f"Comma-separated list of markets to scrape (default: 1x2). Supported: {', '.join(SUPPORTED_MARKETS)}."
        )
        upcoming_parser.add_argument(
            "--storage", type=str, choices=["local", "remote"], default="local",
            help="Storage type for scraped data (default: local)."
        )
        upcoming_parser.add_argument("--headless", action="store_true", help="Run the scraper in headless mode.")

        # Historical odds
        historic_parser = subparsers.add_parser("scrape-historic", help="Scrape historical odds for a specific league and season.")
        historic_parser.add_argument("--league", type=str, required=True, help="The league to scrape (e.g., premier-league).")
        historic_parser.add_argument("--season", type=str, required=True, help="Season to scrape (format: YYYY-YYYY).")
        historic_parser.add_argument(
            "--markets",
            type=str,
            default="1x2",
            help=f"Comma-separated list of markets to scrape (default: 1x2). Supported: {', '.join(SUPPORTED_MARKETS)}."
        )
        historic_parser.add_argument(
            "--storage", type=str, choices=["local", "remote"], default="local",
            help="Storage type for scraped data (default: local)."
        )
        historic_parser.add_argument("--headless", action="store_true", help="Run the scraper in headless mode.")

    def parse_and_validate_args(self) -> argparse.Namespace:
        """Parses and validates command-line arguments."""
        args = self.parser.parse_args()
        self._validate_command(args.command)

        if args.markets:
            args.markets = [market.strip() for market in args.markets.split(",")]

        self._validate_args(args)
        return args
    
    def _validate_command(self, command: Optional[str]):
        """Validates the command argument."""
        if command not in CommandEnum.__members__.values():
            raise ValueError(f"Invalid command '{command}'. Supported commands are: {', '.join(e.value for e in CommandEnum)}.")

    def _validate_args(self, args: argparse.Namespace):
        """Validates parsed CLI arguments."""
        errors = []
        errors.extend(self._validate_markets(args.markets))

        if hasattr(args, 'sport'):
            errors.extend(self._validate_sport(args.sport))

        if hasattr(args, 'league'):
            errors.extend(self._validate_league(args.league))
        
        if hasattr(args, 'date'):
            errors.extend(self._validate_date(args.command, args.date))

        errors.extend(self._validate_storage(args.storage))

        if errors:
            raise ValueError("\n".join(errors))

    def _validate_markets(self, markets: List[str]) -> List[str]:
        """Validates the markets argument."""
        errors = []
        for market in markets:
            if market.startswith("over_under_"):
                try:
                    parse_over_under_market(market)
                except ValueError as e:
                    errors.append(f"Invalid Over/Under market '{market}': {str(e)}.")
            elif market not in SUPPORTED_MARKETS:
                errors.append(f"Invalid market: {market}. Supported markets are: {', '.join(SUPPORTED_MARKETS)}.")
        return errors

    def _validate_sport(self, sport: Optional[str]) -> List[str]:
        """Validates the sport argument."""
        if sport and sport not in SUPPORTED_SPORTS:
            return [f"Invalid sport: '{sport}'. Supported sports are: {', '.join(SUPPORTED_SPORTS)}."]
        return []

    def _validate_league(self, league: Optional[str]) -> List[str]:
        """Validates the league argument."""
        if league and league not in FOOTBALL_LEAGUES_URLS_MAPPING:
            return [f"Invalid league: '{league}'. Supported leagues are: {', '.join(FOOTBALL_LEAGUES_URLS_MAPPING.keys())}."]
        return []

    def _validate_date(self, command: str, date: Optional[str]) -> List[str]:
        """Validates the date argument for scrape-upcoming."""
        errors = []
        if command == "scrape-upcoming" and date:
            if not re.match(DATE_FORMAT_REGEX, date):
                errors.append(f"Invalid date format: '{date}'. Date must be in the format YYYY-MM-DD.")
            else:
                try:
                    date_obj = datetime.strptime(date, "%Y%m%d").date()
                    if date_obj < datetime.now().date():
                        errors.append(f"Date '{date}' must be today or in the future.")
                except ValueError:
                    errors.append(f"Invalid date: '{date}'. Could not parse the date.")
        return errors

    def _validate_storage(self, storage: str) -> List[str]:
        """Validates the storage argument."""
        try:
            StorageType(storage)
        except ValueError:
            return [f"Invalid storage type: '{storage}'. Supported storage types are: {', '.join([e.value for e in StorageType])}"]
        return []