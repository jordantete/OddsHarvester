import re
from typing import Optional
from utils.utils import get_football_league_url
from utils.constants import ODDSPORTAL_BASE_URL

class URLBuilder:
    """
    A utility class for constructing URLs used in scraping data from OddsPortal.
    """

    @staticmethod
    def get_historic_matches_url(
        league: str, 
        season: Optional[str] = None
    ) -> str:
        """
        Constructs the URL for historical matches of a specific football league and season.

        Args:
            league (str): The league for which the URL is required (e.g., "premier-league").
            season (Optional[str]): The season for which the URL is required in 'YYYY-YYYY' format 
                (e.g., "2023-2024"). If not provided, the URL for the current season is returned.

        Returns:
            str: The constructed URL for the league and season.

        Raises:
            ValueError: If the season is provided but does not follow the expected 'YYYY-YYYY' format.
        """
        base_url = get_football_league_url(league)

        if not season:
            return base_url

        if not re.match(r"^\d{4}-\d{4}$", season):
            raise ValueError(f"Invalid season format: {season}. Expected format: 'YYYY-YYYY'.")

        return f"{base_url}-{season}/results/"

    @staticmethod
    def get_upcoming_matches_url(
        sport: str, 
        date: str,
        league: Optional[str] = None
    ) -> str:
        """
        Constructs the URL for upcoming matches for a specific sport and date.
        If a league is provided, includes the league in the URL.

        Args:
            sport (str): The sport for which the URL is required (e.g., "football").
            date (str): The date for which the matches are required in 'YYYY-MM-DD' format (e.g., "2025-01-15").
            league (Optional[str]): The league for which matches are required (e.g., "premier-league").

        Returns:
            str: The constructed URL for upcoming matches.
        """
        return get_football_league_url(league) if league else f"{ODDSPORTAL_BASE_URL}/matches/{sport}/{date}/"
