from typing import Optional
from src.utils.utils import get_football_league_url
from src.utils.constants import ODDSPORTAL_BASE_URL

class URLBuilder:
    """
    A utility class for constructing URLs used in scraping data from OddsPortal.
    """

    @staticmethod
    def get_base_url(
        league: str, 
        season: Optional[str] = None
    ) -> str:
        """
        Constructs the base URL for a specific football league and optionally a season.

        Args:
            league (str): The league for which the URL is required (e.g., "premier-league").
            season (Optional[str]): The season for which the URL is required in 'YYYY-YYYY' format (e.g., "2023-2024").
            If not provided, the URL for the current season is returned.

        Returns:
            str: The constructed URL for the league and season.

        Raises:
            ValueError: If the season is provided but does not follow the expected 'YYYY-YYYY' format.
        """
        base_url = get_football_league_url(league)

        if not season:
            return base_url

        try:
            season_components = season.split("-")
            return f"{base_url}-{season_components[0]}-{season_components[1]}/results/"
        
        except IndexError:
            raise ValueError(f"Invalid season format: {season}. Expected format: 'YYYY-YYYY'")

    @staticmethod
    def get_upcoming_url(
        sport: str, 
        date: str
    ) -> str:
        """
        Constructs the URL for upcoming matches for a specific sport and date.

        Args:
            sport (str): The sport for which the URL is required (e.g., "football").
            date (str): The date for which the matches are required in 'YYYY-MM-DD' format (e.g., "2025-01-15").

        Returns:
            str: The constructed URL for upcoming matches.
        """
        return f"{ODDSPORTAL_BASE_URL}/matches/{sport}/{date}/"