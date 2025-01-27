import argparse, re
from datetime import datetime
from typing import List, Optional
from utils.constants import SUPPORTED_SPORTS, SUPPORTED_MARKETS, FOOTBALL_LEAGUES_URLS_MAPPING, DATE_FORMAT_REGEX
from utils.utils import parse_over_under_market
from utils.command_enum import CommandEnum
from storage.storage_type import StorageType
from storage.storage_format import StorageFormat

class CLIArgumentHandler:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="OddsHarvester CLI for scraping betting odds data.",
            epilog=self._generate_help_message(),
            formatter_class=argparse.RawTextHelpFormatter
        )
        self._initialize_subparsers()

    def _initialize_subparsers(self):
        subparsers = self.parser.add_subparsers(
            title="Commands", 
            dest="command",
            help="Specify whether you want to scrape upcoming matches or historical odds."
        )

        upcoming_parser = subparsers.add_parser("scrape_upcoming", help="Scrape odds for upcoming matches.")
        self._add_upcoming_arguments(upcoming_parser)

        historic_parser = subparsers.add_parser("scrape_historic", help="Scrape historical odds for a specific league and/or season.")
        self._add_historic_arguments(historic_parser)

    def _add_upcoming_arguments(self, parser):
        parser.add_argument("--sport", type=str, required=True, help="The sport to scrape (e.g., football).")
        parser.add_argument("--date", type=str, required=True, help="Date for upcoming matches (YYYYMMDD).")
        parser.add_argument("--league", type=str, help="Specific league to target for upcoming matches (e.g., premier-league).")
        parser.add_argument(
            "--markets",
            type=lambda s: s.split(','),
            default=["1x2"],
            help=f"Comma-separated list of markets to scrape (default: 1x2). Supported: {', '.join(SUPPORTED_MARKETS)}."
        )
        parser.add_argument(
            "--storage",
            type=str,
            choices=[f.value for f in StorageType],
            default="local",
            help="Storage type for scraped data (default: local)."
        )
        parser.add_argument(
            "--file_path",
            type=str,
            help="File path for saving data when using local storage (default: scraped_data.csv)."
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=[f.value for f in StorageFormat],
            help="Storage format for saving data when using local storage."
        )
        parser.add_argument("--headless", action="store_true", help="Run the scraper in headless mode.")
        parser.add_argument(
            "--save_logs",
            action="store_true",
            help="Save logs to a local file for debugging (default: False)."
        )

    def _add_historic_arguments(self, parser):
        parser.add_argument("--league", type=str, required=True, help="The league to scrape (e.g., premier-league).")
        parser.add_argument("--season", type=str, required=True, help="Season to scrape (format: YYYY-YYYY).")
        parser.add_argument(
            "--markets",
            type=lambda s: s.split(','),
            default=["1x2"],
            help=f"Comma-separated list of markets to scrape (default: 1x2). Supported: {', '.join(SUPPORTED_MARKETS)}."
        )
        parser.add_argument(
            "--storage",
            type=str,
            choices=[f.value for f in StorageType],
            default="local",
            help="Storage type for scraped data (default: local)."
        )
        parser.add_argument(
            "--file_path",
            type=str,
            help="File path for saving data when using local storage (default: scraped_data.csv)."
        )
        parser.add_argument(
            "--format",
            type=str,
            choices=[f.value for f in StorageFormat],
            help="Storage format for saving data when using local storage."
        )
        parser.add_argument("--headless", action="store_true", help="Run the scraper in headless mode.")
        parser.add_argument(
            "--save_logs",
            action="store_true",
            help="Save logs to a local file for debugging (default: False)."
        )

    def _generate_help_message(self):
        return (
            "Commands and arguments:\n\n"
            "  scrape_upcoming:\n"
            "    --sport         The sport to scrape (e.g., football).\n"
            "    --date          Date for upcoming matches (YYYYMMDD).\n"
            "    --league        Specific league to target for upcoming matches.\n"
            "    --markets       Comma-separated list of betting markets to scrape (default: 1x2).\n"
            "    --storage       Storage type for scraped data (local or remote; default: local).\n"
            "    --file_path     File path to save data locally (default: scraped_data.csv).\n"
            "    --format        Format for saving local data (json).\n"
            "    --headless      Run the scraper in headless mode (default: False).\n"
            "    --save_logs     Save logs to a local file for debugging (default: False).\n\n"
            "  scrape_historic:\n"
            "    --league        The league to scrape (e.g., premier-league).\n"
            "    --season        Season to scrape (format: YYYY-YYYY).\n"
            "    --markets       Comma-separated list of betting markets to scrape (default: 1x2).\n"
            "    --storage       Storage type for scraped data (local or remote; default: local).\n"
            "    --file_path     File path to save data locally (default: scraped_data.csv).\n"
            "    --format        Format for saving local data (json).\n"
            "    --headless      Run the scraper in headless mode (default: False).\n"
            "    --save_logs     Save logs to a local file for debugging (default: False).\n\n"
            "Examples:\n"
            "  Scrape upcoming matches:\n"
            "    python main.py scrape_upcoming --sport football --date 20250101 --markets 1x2,btts --storage local --file_path output.json\n\n"
            "  Scrape historical odds:\n"
            "    python main.py scrape_historic --league premier-league --season 2022-2023 --markets 1x2 --storage remote --headless\n"
        )

    def parse_and_validate_args(self) -> argparse.Namespace:
        """Parses and validates command-line arguments."""
        args = self.parser.parse_args()
        
        if not args.command:
            self.parser.print_help()
            exit(1)

        self._validate_command(args.command)

        if isinstance(args.markets, str):
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
        
        if hasattr(args, 'file_path') or hasattr(args, 'format'):
            errors.extend(self._validate_file_args(args))

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

    def _validate_file_args(
        self, 
        args: argparse.Namespace
    ) -> List[str]:
        """Validates the file_path and file_format arguments."""
        errors = []

        extracted_format = None
        if args.file_path:
            if '.' in args.file_path:
                extracted_format = args.file_path.split('.')[-1].lower()
            else:
                errors.append(f"File path '{args.file_path}' must include a valid file extension (e.g., '.csv' or '.json').")

        if args.format:
            if args.format not in [f.value for f in StorageFormat]:
                errors.append(f"Invalid file format: '{args.format}'. Supported formats are: {', '.join(f.value for f in StorageFormat)}.")
            elif extracted_format and args.format != extracted_format:
                errors.append(f"Mismatch between file format '{args.format}' and file path extension '{extracted_format}'.")

        elif extracted_format:
            if extracted_format not in [f.value for f in StorageFormat]:
                errors.append(f"Invalid file extension in file path: '{extracted_format}'. Supported formats are: {', '.join(f.value for f in StorageFormat)}.")
            args.format = extracted_format

        if args.file_path and args.format and not args.file_path.endswith(f".{args.format}"):
            errors.append(f"File path '{args.file_path}' must end with '.{args.format}'.")

        return errors