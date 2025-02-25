import logging
from typing import Optional, Dict

logger = logging.getLogger("SetupProxy")

def setup_proxy_config(
    proxy: Optional[Dict[str, str]] = None
) -> Optional[Dict[str, str]]:
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