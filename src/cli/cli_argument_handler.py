import logging

from src.cli.cli_argument_parser import CLIArgumentParser
from src.cli.cli_argument_validator import CLIArgumentValidator


class CLIArgumentHandler:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parser = CLIArgumentParser().get_parser()
        self.validator = CLIArgumentValidator()

    def parse_and_validate_args(self) -> dict:
        """Parses and validates command-line arguments, returning a structured dictionary."""
        args = self.parser.parse_args()

        if not args.command:
            self.logger.error("No CLI args Command provided")
            self.parser.print_help()
            exit(1)

        try:
            self.validator.validate_args(args)
        except ValueError as e:
            self.logger.error(f"CLI args validation failed: {e}")
            self.parser.print_help()
            exit(1)

        return {
            "command": args.command,
            "match_links": getattr(args, "match_links", None),
            "sport": getattr(args, "sport", None),
            "date": getattr(args, "date", None),
            "leagues": getattr(args, "leagues", None),
            "season": getattr(args, "season", None),
            "storage_type": args.storage,
            "storage_format": getattr(args, "format", None),
            "file_path": getattr(args, "file_path", None),
            "max_pages": getattr(args, "max_pages", None),
            "proxies": getattr(args, "proxies", None),
            "headless": args.headless,
            "markets": args.markets,
            "browser_user_agent": getattr(args, "browser_user_agent", None),
            "browser_locale_timezone": getattr(args, "browser_locale_timezone", None),
            "browser_timezone_id": getattr(args, "browser_timezone_id", None),
            "target_bookmaker": getattr(args, "target_bookmaker", None),
            "scrape_odds_history": getattr(args, "scrape_odds_history", False),
        }
