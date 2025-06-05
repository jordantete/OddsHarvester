import argparse, re
from datetime import datetime
from typing import List, Optional
from src.utils.command_enum import CommandEnum
from src.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from src.utils.utils import get_supported_markets
from src.utils.sport_market_constants import Sport
from src.storage.storage_type import StorageType
from src.storage.storage_format import StorageFormat

class CLIArgumentValidator:
    def validate_args(self, args: argparse.Namespace):
        """Validates parsed CLI arguments."""
        self._validate_command(command=args.command)

        if isinstance(args.markets, str):
            args.markets = [market.strip() for market in args.markets.split(",")]

        errors = []
        
        if hasattr(args, 'match_links'):
            errors.extend(self._validate_match_links(match_links=args.match_links, sport=args.sport))

        if hasattr(args, 'sport'):
            errors.extend(self._validate_sport(sport=args.sport))

        if hasattr(args, 'markets'):
            errors.extend(self._validate_markets(sport=args.sport, markets=args.markets))

        if hasattr(args, 'league'):
            errors.extend(self._validate_league(sport=args.sport, league=args.league))
        
        if hasattr(args, "season"):
            errors.extend(self._validate_season(command=args.command, season=args.season))
        
        if hasattr(args, 'date'):
            errors.extend(self._validate_date(command=args.command, date=args.date, match_links=args.match_links))
        
        if hasattr(args, 'file_path') or hasattr(args, 'format'):
            errors.extend(self._validate_file_args(args=args))
            
        if hasattr(args, 'max_pages'):
            errors.extend(self._validate_max_pages(command=args.command, max_pages=args.max_pages))
        
        if hasattr(args, 'proxies'):
            errors.extend(self._validate_proxies(args.proxies))
        
        if hasattr(args, 'target_bookmaker'):
            if args.target_bookmaker and not isinstance(args.target_bookmaker, str):
                errors.append("Target bookmaker must be a string if specified.")

        if hasattr(args, 'scrape_odds_history'):
            if not isinstance(args.scrape_odds_history, bool):
                errors.append("'--scrape-odds-history' must be a boolean flag.")
        
        errors.extend(self._validate_browser_settings(
            user_agent=args.browser_user_agent,
            locale_timezone=args.browser_locale_timezone,
            timezone_id=args.browser_timezone_id
        ))
        errors.extend(self._validate_storage(storage=args.storage))

        if errors:
            raise ValueError("\n".join(errors))
    
    def _validate_command(self, command: Optional[str]):
        """Validates the command argument."""
        if command not in CommandEnum.__members__.values():
            raise ValueError(f"Invalid command '{command}'. Supported commands are: {', '.join(e.value for e in CommandEnum)}.")
    
    def _validate_match_links(
        self, 
        match_links: Optional[List[str]],
        sport: Optional[str]
    ) -> List[str]:
        """Validates the format of match links."""
        errors = []
        url_pattern = re.compile(r"https?://www\.oddsportal\.com/.+")

        if match_links:
            if not sport:
                errors.append("The '--sport' argument is required when using '--match_links'.")
    
            for link in match_links:
                if not url_pattern.match(link):
                    errors.append(f"Invalid match link format: {link}")

        return errors
    
    def _validate_sport(self, sport: Optional[str]) -> List[str]:
        """Validates the sport argument."""
        errors = []
        supported_sports = ', '.join(s.value for s in Sport)

        if not sport:
            error_msg = f"Invalid sport: None. Expected one of {[s.value for s in Sport]}."
            errors.append(error_msg)
            raise ValueError(error_msg)

        try:
            Sport(str(sport).lower())
        except (ValueError, AttributeError):
            if isinstance(sport, str):
                error_msg = f"Invalid sport: '{sport}'. Supported sports are: {supported_sports}."
            else:
                error_msg = f"Invalid sport: {sport}. Expected one of {[s.value for s in Sport]}."
            errors.append(error_msg)
            raise ValueError(error_msg)

        return errors

    def _validate_markets(self, sport: Sport, markets: List[str]) -> List[str]:
        """Validates markets against the selected sport."""
        errors = []
        
        if isinstance(sport, str):
            try:
                sport = Sport(sport.lower())
            except ValueError:
                return [f"Invalid sport: '{sport}'. Supported sports are: {', '.join(s.value for s in Sport)}."]

        supported_markets = get_supported_markets(sport)

        for market in markets:
            if market not in supported_markets:
                errors.append(f"Invalid market: {market}. Supported markets for {sport.value}: {', '.join(supported_markets)}.")

        return errors

    def _validate_league(self, sport: str, league: Optional[str]) -> List[str]:
        """Validates the league argument based on the sport."""
        errors = []

        if not league:
            return errors

        try:
            sport_enum = Sport(sport.lower()) if isinstance(sport, str) else sport
        except ValueError:
            return [f"Invalid sport: '{sport}'. Supported sports are: {', '.join(s.value for s in Sport)}."]

        if sport_enum not in SPORTS_LEAGUES_URLS_MAPPING:
            errors.append(f"Sport '{sport}' is not supported for league validation.")
            return errors

        supported_leagues = SPORTS_LEAGUES_URLS_MAPPING[sport_enum]
        if league not in supported_leagues:
            errors.append(
                f"Invalid league: '{league}' for sport '{sport_enum.value}'."
            )

        return errors

    # def _validate_season(self, command: str, season: Optional[str]) -> List[str]:
    #     """Validates the season argument (only for scrape_historic command)."""
    #     errors = []

    #     if command != "scrape_historic":
    #         return errors  # Season validation is only for the historic command

    #     if not season:
    #         errors.append("The season argument is required for the 'scrape_historic' command.")
    #         return errors

    #     # Match format YYYY-YYYY (e.g., 2023-2024)
    #     season_pattern = re.compile(r"^\d{4}-\d{4}$")
    #     if not season_pattern.match(season):
    #         errors.append(f"Invalid season format: '{season}'. Expected format: YYYY-YYYY (e.g., 2023-2024).")
    #         return errors

    #     # Validate that the second year is exactly one year after the first year
    #     start_year, end_year = map(int, season.split("-"))
    #     if end_year != start_year + 1:
    #         errors.append(f"Invalid season range: '{season}'. The second year must be exactly one year after the first year.")

    #     return errors

    def _validate_season(self, command: str, season: Optional[str]) -> List[str]:
        """Validates the season argument (only for scrape_historic command)."""
        errors = []

        if command != "scrape_historic":
            return errors  # Season validation is only for the historic command

        if not season:
            errors.append("The season argument is required for the 'scrape_historic' command.")
            return errors

        single_year_pattern = re.compile(r"^\d{4}$")
        range_pattern = re.compile(r"^\d{4}-\d{4}$")

        if single_year_pattern.match(season):
            # Valid single year (e.g., 2024), no further checks needed
            return errors

        if range_pattern.match(season):
            # Validate that the second year is exactly one after the first
            start_year, end_year = map(int, season.split("-"))
            if end_year != start_year + 1:
                errors.append(f"Invalid season range: '{season}'. The second year must be exactly one year after the first year.")
        else:
            errors.append(f"Invalid season format: '{season}'. Expected format: YYYY or YYYY-YYYY (e.g., 2024 or 2024-2025).")

        return errors

    def _validate_date(
        self, 
        command: str, 
        date: Optional[str],
        match_links: Optional[List[str]]
    ) -> List[str]:
        """Validates the date argument for the `scrape_upcoming` command."""
        errors = []

        # Date not required when match_links is provided
        if match_links:
            return errors

        # Date should only be required for scrape_upcoming
        if command != "scrape_upcoming":
            if date:
                errors.append(f"Date should not be provided for the '{command}' command.")
            return errors

        if not date:
            return [f"Missing required argument: 'date' is mandatory for '{command}' command."]

        # Ensure date format is YYYYMMDD
        try:
            parsed_date = datetime.strptime(date, "%Y%m%d")
        except ValueError:
            return [f"Invalid date format: '{date}'. Expected format is YYYYMMDD (e.g., 20250227)."]

        # Ensure the date is today or in the future
        if parsed_date.date() < datetime.now().date():
            errors.append(f"Date '{date}' must be today or in the future.")

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

    def _validate_max_pages(
        self,
        command: str, 
        max_pages: Optional[int]
    ) -> List[str]:
        """Validates the max_pages argument (only for scrape_historic)."""
        errors = []
        
        if command != "scrape_historic":
            return errors  # max_pages is only valid for scrape_historic
        
        if max_pages is not None:
            if not isinstance(max_pages, int) or max_pages <= 0:
                errors.append(f"Invalid max-pages value: '{max_pages}'. It must be a positive integer.")

        return errors

    def _validate_proxies(
        self, 
        proxies: Optional[List[str]]
    ) -> List[str]:
        """Validates proxy format (supports http, https, socks5 with optional auth)."""
        errors = []
        if not proxies:
            return errors
    
        PROXY_PATTERN = re.compile(r"^(?P<scheme>https?|socks5|socks4)://(?P<host>[\w\.-]+):(?P<port>\d+)(?:\s+(?P<user>\S+)\s+(?P<pass>\S+))?$")

        for proxy in proxies:
            if not PROXY_PATTERN.match(proxy):
                errors.append(
                    f"Invalid proxy format: '{proxy}'. Expected format: "
                    f"'http[s]://host:port [user pass]' or 'socks5://host:port [user pass]'."
                )

        return errors

    def _validate_browser_settings(
        self, 
        user_agent: Optional[str], 
        locale_timezone: Optional[str], 
        timezone_id: Optional[str]
    ) -> List[str]:
        """Validates the browser-related CLI arguments."""
        errors = []

        if user_agent and not isinstance(user_agent, str):
            errors.append("Invalid browser user agent format.")

        if locale_timezone and not isinstance(locale_timezone, str):
            errors.append("Invalid browser locale timezone format.")

        if timezone_id and not isinstance(timezone_id, str):
            errors.append("Invalid browser timezone ID format.")

        return errors