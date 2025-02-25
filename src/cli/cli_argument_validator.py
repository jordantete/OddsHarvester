import argparse, re
from datetime import datetime
from typing import List, Optional
from utils.command_enum import CommandEnum
from utils.constants import DATE_FORMAT_REGEX
from utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from utils.utils import get_supported_markets
from utils.sport_market_constants import Sport
from storage.storage_type import StorageType
from storage.storage_format import StorageFormat


class CLIArgumentValidator:
    def validate_args(self, args: argparse.Namespace):
        """Validates parsed CLI arguments."""
        self._validate_command(command=args.command)

        if isinstance(args.markets, str):
            args.markets = [market.strip() for market in args.markets.split(",")]

        errors = []

        if hasattr(args, 'sport'):
            errors.extend(self._validate_sport(sport=args.sport))

        if hasattr(args, 'markets'):
            errors.extend(self._validate_markets(sport=args.sport, markets=args.markets))

        if hasattr(args, 'league'):
            errors.extend(self._validate_league(sport=args.sport, league=args.league))
        
        if hasattr(args, 'date'):
            errors.extend(self._validate_date(command=args.command, date=args.date))
        
        if hasattr(args, 'file_path') or hasattr(args, 'format'):
            errors.extend(self._validate_file_args(args=args))

        errors.extend(self._validate_storage(storage=args.storage))

        if errors:
            raise ValueError("\n".join(errors))
    
    def _validate_command(self, command: Optional[str]):
        """Validates the command argument."""
        if command not in CommandEnum.__members__.values():
            raise ValueError(f"Invalid command '{command}'. Supported commands are: {', '.join(e.value for e in CommandEnum)}.")
    
    def _validate_sport(self, sport: Optional[str]) -> List[str]:
        """Validates the sport argument."""
        if sport and sport not in [s.value for s in Sport]:
            return [f"Invalid sport: '{sport}'. Supported sports are: {', '.join(s.value for s in Sport)}."]
        return []

    def _validate_markets(self, sport: Sport, markets: List[str]) -> List[str]:
        """Validates markets against the selected sport."""
        errors = []
        supported_markets = get_supported_markets(sport)
        
        for market in markets:
            if market not in supported_markets:
                errors.append(f"Invalid market: {market}. Supported markets for {sport.value}: {', '.join(supported_markets)}.")

        return errors

    def _validate_league(self, sport: Sport, league: Optional[str]) -> List[str]:
        """Validates the league argument based on the sport."""
        errors = []
        
        if not league:
            return errors
        
        if sport not in SPORTS_LEAGUES_URLS_MAPPING:
            return [f"Unsupported sport: '{sport.value}'. Supported sports are: {', '.join(s.value for s in SPORTS_LEAGUES_URLS_MAPPING.keys())}."]
        
        sport_league_mapping = SPORTS_LEAGUES_URLS_MAPPING[sport]
        
        if league not in sport_league_mapping:
            errors.append(
                f"Invalid league: '{league}' for sport '{sport.value}'. "
                f"Supported leagues: {', '.join(sport_league_mapping.keys())}."
            )
        return errors

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