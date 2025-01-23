import os, logging
from typing import Optional, Dict
from src.core.over_under_market import OverUnderMarket
from utils.constants import FOOTBALL_LEAGUES_URLS_MAPPING

logger = logging.getLogger(__name__)

def build_response(status_code: int, message: str) -> dict:
    """Helper method to build a consistent response."""
    return {'statusCode': status_code, 'body': message}

def get_football_league_url(league: str) -> str:
    """Retrieves the URL associated with a specific football league."""
    if league not in FOOTBALL_LEAGUES_URLS_MAPPING:
        raise ValueError(f"Invalid football league '{league}'. Supported leagues are: {', '.join(FOOTBALL_LEAGUES_URLS_MAPPING.keys())}.")
    return FOOTBALL_LEAGUES_URLS_MAPPING[league]

def is_running_in_docker() -> bool:
    """Detect if the app is running inside a Docker container."""
    return os.path.exists('/.dockerenv')

def ensure_directory_exists(file_path: str):
    """Ensures the directory for the given file path exists. If it doesn't exist, creates it."""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def parse_over_under_market(arg: str) -> OverUnderMarket:
    """Parse the console argument into the corresponding OverUnderMarket enum."""
    try:
        # Extract the numerical part from the argument (e.g., '1.5' from 'over_under_1_5')
        market_value = arg.replace("over_under_", "").replace("_", ".")
        return OverUnderMarket(market_value)
    
    except ValueError:
        raise ValueError(f"Invalid Over/Under market argument: {arg}. Supported values are: {', '.join(f'over_under_{e.value.replace(".", "_")}' for e in OverUnderMarket)}")
    
def setup_proxy_config(proxy: Optional[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
    """
    Prepare the proxy configuration for Playwright.

    Args:
        proxy (Optional[Dict[str, str]]): Proxy configuration with the following keys:
            - server (str): Proxy server address, including protocol and port (e.g., 'http://proxy-server:8080').
            - username (Optional[str]): Proxy username (optional).
            - password (Optional[str]): Proxy password (optional).

    Returns:
        Optional[Dict[str, str]]: A dictionary containing the formatted proxy configuration if provided or None if no proxy is configured.
    """
    try:
        if not proxy or "server" not in proxy:
            logger.info("No proxy configuration provided. Proceeding without proxy.")
            return None

        proxy_config = {"server": proxy.get("server")}

        if proxy.get("username") and proxy.get("password"):
            proxy_config["username"] = proxy["username"]
            proxy_config["password"] = proxy["password"]

        logger.info(f"Using proxy server: {proxy_config['server']}")
        return proxy_config

    except Exception as e:
        logger.error(f"Failed to set up proxy configuration: {str(e)}")
        return None