from datetime import datetime
from utils.constants import FOOTBALL_LEAGUES_URLS_MAPPING

def build_response(status_code: int, message: str) -> dict:
    """Helper method to build a consistent response."""
    return {'statusCode': status_code, 'body': message}

def get_current_date_time_string():
    now = datetime.now()
    date_time_string = now.strftime('%Y-%m-%d %H:%M:%S')
    return date_time_string

def get_football_league_url(league: str) -> str:
    if league not in FOOTBALL_LEAGUES_URLS_MAPPING:
        raise ValueError(f"Invalid football league '{league}'. Supported leagues are: {', '.join(FOOTBALL_LEAGUES_URLS_MAPPING.keys())}.")
    return FOOTBALL_LEAGUES_URLS_MAPPING[league]