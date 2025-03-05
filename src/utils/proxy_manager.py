import logging
from typing import List, Dict, Optional

class ProxyManager:
    """Manages proxy selection, usage, and rotation for Playwright."""

    def __init__(
        self, 
        cli_proxies: Optional[List[str]] = None
    ):
        """
        Initialize ProxyManager with a list of proxies.

        Args:
            cli_proxies (Optional[List[str]]): List of proxy strings from CLI.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.proxies = self._parse_proxies(cli_proxies)
        self.current_proxy_index = 0  # Track current proxy in use

    def _parse_proxies(
        self, 
        cli_proxies: Optional[List[str]]
    ) -> List[Dict[str, str]]:
        """
        Parses proxy details from CLI arguments.

        Args:
            cli_proxies (Optional[List[str]]): List of proxy strings from CLI.

        Returns:
            List[Dict[str, str]]: List of structured proxy configurations.
        """
        parsed_proxies = []

        if not cli_proxies:
            self.logger.info("No proxies provided, running without proxy.")
            return parsed_proxies

        for proxy_entry in cli_proxies:
            try:
                parts = proxy_entry.split()
                if len(parts) == 1 and proxy_entry.startswith("http"):
                    server, username, password = parts[0], None, None
                elif len(parts) == 3 and parts[0].startswith("http"):
                    server, username, password = parts
                else:
                    raise ValueError(f"Invalid proxy format: {proxy_entry}")

                proxy_config = {"server": server}
                if username and password:
                    proxy_config["username"] = username
                    proxy_config["password"] = password

                parsed_proxies.append(proxy_config)

            except Exception as e:
                self.logger.error(f"Failed to parse proxy: {proxy_entry}, error: {e}")

        if parsed_proxies:
            self.logger.info(f"Loaded {len(parsed_proxies)} proxies for rotation.")

        return parsed_proxies

    def get_current_proxy(self) -> Optional[Dict[str, str]]:
        """
        Returns the current proxy config.

        Returns:
            Optional[Dict[str, str]]: Current proxy config or None if no proxies available.
        """
        if not self.proxies:
            self.logger.info("No proxies available, using direct connection.")
            return None

        return self.proxies[self.current_proxy_index]

    def rotate_proxy(self):
        """
        Rotates to the next available proxy.
        If all proxies fail, logs an error and switches to direct connection.
        """
        if not self.proxies:
            self.logger.warning("No proxies available to rotate. Running without proxy.")
            return

        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        self.logger.info(f"Rotated to new proxy: {self.get_current_proxy()}")