import re

from src.utils.constants import ODDSPORTAL_BASE_URL
from src.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from src.utils.sport_market_constants import Sport


class URLBuilder:
    """
    A utility class for constructing URLs used in scraping data from OddsPortal.
    """

    @staticmethod
    def get_historic_matches_url(sport: str, league: str, season: str | None = None) -> str:
        """
        Constructs the URL for historical matches of a specific sport league and season.

        Args:
            sport (str): The sport for which the URL is required (e.g., "football", "tennis", "baseball").
            league (str): The league for which the URL is required (e.g., "premier-league", "mlb").
            season (Optional[str]): The season for which the URL is required. Accepts either:
                - a single year (e.g., "2024")
                - a range in 'YYYY-YYYY' format (e.g., "2023-2024")
                - None or empty string for the current season

        Returns:
            str: The constructed URL for the league and season.

        Raises:
            ValueError: If the season is provided but does not follow the expected format(s).
        """
        base_url = URLBuilder.get_league_url(sport, league).rstrip("/")

        # Treat missing season as current
        if not season:
            return f"{base_url}/results/"

        if isinstance(season, str) and season.lower() == "current":
            raise ValueError(f"Invalid season format: {season}. Expected format: 'YYYY' or 'YYYY-YYYY'")

        if re.match(r"^\d{4}$", season):
            return f"{base_url}-{season}/results/"

        if re.match(r"^\d{4}-\d{4}$", season):
            start_year, end_year = map(int, season.split("-"))
            if end_year != start_year + 1:
                raise ValueError(
                    f"Invalid season range: {season}. The second year must be exactly one year after the first."
                )

            # Special handling for baseball leagues
            if sport.lower() == "baseball":
                return f"{base_url}-{start_year}/results/"

            return f"{base_url}-{season}/results/"

        raise ValueError(f"Invalid season format: {season}. Expected format: 'YYYY' or 'YYYY-YYYY'")

    @staticmethod
    def get_upcoming_matches_url(sport: str, date: str, league: str | None = None) -> str:
        """
        Constructs the URL for upcoming matches for a specific sport and date.
        If a league is provided, includes the league in the URL.

        Args:
            sport (str): The sport for which the URL is required (e.g., "football", "tennis").
            date (str): The date for which the matches are required in 'YYYY-MM-DD' format (e.g., "2025-01-15").
            league (Optional[str]): The league for which matches are required (e.g., "premier-league").

        Returns:
            str: The constructed URL for upcoming matches.
        """
        if league:
            return URLBuilder.get_league_url(sport, league)
        return f"{ODDSPORTAL_BASE_URL}/matches/{sport}/{date}/"

    @staticmethod
    def get_league_url(sport: str, league: str) -> str:
        """
        Retrieves the URL associated with a specific league for a given sport.

        Args:
            sport (str): The sport name (e.g., "football", "tennis").
            league (str): The league name (e.g., "premier-league", "atp-tour").

        Returns:
            str: The URL associated with the league.

        Raises:
            ValueError: If the league is not found for the specified sport.
        """
        sport_enum = Sport(sport)

        if sport_enum not in SPORTS_LEAGUES_URLS_MAPPING:
            raise ValueError(f"Unsupported sport '{sport}'. Available: {', '.join(SPORTS_LEAGUES_URLS_MAPPING.keys())}")

        leagues = SPORTS_LEAGUES_URLS_MAPPING[sport_enum]

        if league not in leagues:
            raise ValueError(f"Invalid league '{league}' for sport '{sport}'. Available: {', '.join(leagues.keys())}")

        return leagues[league]
