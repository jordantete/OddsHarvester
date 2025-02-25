from cli.cli_argument_parser import CLIArgumentParser
from cli.cli_argument_validator import CLIArgumentValidator

class CLIArgumentHandler:
    def __init__(self):
        self.parser = CLIArgumentParser().get_parser()
        self.validator = CLIArgumentValidator()

    def parse_and_validate_args(self) -> dict:
        """Parses and validates command-line arguments, returning a structured dictionary."""
        args = self.parser.parse_args()

        if not args.command:
            self.parser.print_help()
            exit(1)

        self.validator.validate_args(args)

        return {
            "command": args.command,
            "sport": getattr(args, "sport", None),
            "date": getattr(args, "date", None),
            "league": getattr(args, "league", None),
            "season": getattr(args, "season", None),
            "storage_type": args.storage,
            "storage_format": getattr(args, "format", None),
            "file_path": getattr(args, "file_path", None),
            "headless": args.headless,
            "markets": args.markets
        }