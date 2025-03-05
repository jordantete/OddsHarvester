import argparse
from .cli_help_message_generator import CLIHelpMessageGenerator
from src.utils.sport_market_constants import Sport
from src.storage.storage_type import StorageType
from src.storage.storage_format import StorageFormat

class CLIArgumentParser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="OddsHarvester CLI for scraping betting odds data.",
            epilog=CLIHelpMessageGenerator().generate(),
            formatter_class=argparse.RawTextHelpFormatter
        )
        self._initialize_subparsers()

    def _initialize_subparsers(self):
        subparsers = self.parser.add_subparsers(
            title="Commands", 
            dest="command",
            help="Specify whether you want to scrape upcoming matches or historical odds."
        )

        self._add_upcoming_parser(subparsers)
        self._add_historic_parser(subparsers)

    def _add_upcoming_parser(self, subparsers):
        parser = subparsers.add_parser("scrape_upcoming", help="Scrape odds for upcoming matches.")
        self._add_common_arguments(parser)
        parser.add_argument("--date", type=str, required=True, help="Date for upcoming matches (YYYYMMDD).")

    def _add_historic_parser(self, subparsers):
        parser = subparsers.add_parser("scrape_historic", help="Scrape historical odds for a specific league and/or season.")
        self._add_common_arguments(parser)
        parser.add_argument("--season", type=str, required=True, help="Season to scrape (format: YYYY-YYYY).")
        parser.add_argument("--max_pages", type=int, help="Maximum number of pages to scrape (optional).")

    def _add_common_arguments(self, parser):
        parser.add_argument(
            "--sport",
            type=str,
            choices=[s.value for s in Sport],
            default=Sport.FOOTBALL.value,
            help="The sport to scrape (default: football)."
        )
        parser.add_argument("--league", type=str, help="Specific league (e.g., premier-league).")
        parser.add_argument(
            "--markets",
            type=lambda s: s.split(','),
            help="Comma-separated list of markets to scrape."
        )
        parser.add_argument(
            "--storage",
            type=str,
            choices=[f.value for f in StorageType],
            default="local",
            help="Storage type (default: local)."
        )
        parser.add_argument("--file_path", type=str, help="File path for saving data.")
        parser.add_argument(
            "--format",
            type=str,
            choices=[f.value for f in StorageFormat],
            help="Storage format."
        )
        parser.add_argument(
            "--proxies",
            nargs="+",
            help="List of proxies in 'server user pass' format (format: 'http://proxy.com:8080 user pass'). Multiple proxies supported for rotation.",
        )
        parser.add_argument("--headless", action="store_true", help="Run in headless mode.")
        parser.add_argument("--save_logs", action="store_true", help="Save logs for debugging.")

    def get_parser(self) -> argparse.ArgumentParser:
        return self.parser