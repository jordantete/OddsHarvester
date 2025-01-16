import os
from utils.constants import FOOTBALL_LEAGUES_URLS_MAPPING

def build_response(status_code: int, message: str) -> dict:
    """Helper method to build a consistent response."""
    return {'statusCode': status_code, 'body': message}

def get_football_league_url(league: str) -> str:
    if league not in FOOTBALL_LEAGUES_URLS_MAPPING:
        raise ValueError(f"Invalid football league '{league}'. Supported leagues are: {', '.join(FOOTBALL_LEAGUES_URLS_MAPPING.keys())}.")
    return FOOTBALL_LEAGUES_URLS_MAPPING[league]

def is_running_in_docker() -> bool:
    """Detect if the app is running inside a Docker container."""
    return os.path.exists('/.dockerenv')