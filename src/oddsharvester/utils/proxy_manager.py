import logging


class ProxyManager:
    """Manages proxy selection, usage, and rotation for Playwright."""

    def __init__(self, cli_proxies: list[str] | None = None):
        """
        Initialize ProxyManager with a list of proxies.

        Args:
            cli_proxies (Optional[List[str]]): List of proxy strings from CLI.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.proxies = self._parse_proxies(cli_proxies)
        self.current_proxy_index = 0  # Track current proxy in use

    def _parse_proxies(self, cli_proxies: list[str] | None) -> list[dict[str, str]]:
        """
        Parses proxy details from CLI arguments.

        Args:
            cli_proxies (Optional[List[str]]): List of proxy strings from CLI.

        Returns:
            List[Dict[str, str]]: List of structured proxy configurations.
        """
        parsed_proxies = []
        valid_schemes = ("http", "https", "socks4", "socks5")

        if not cli_proxies:
            self.logger.info("No proxies provided, running without proxy.")
            return parsed_proxies

        for proxy_entry in cli_proxies:
            try:
                parts = proxy_entry.strip().split()
                server = parts[0]

                if not any(server.startswith(scheme + "://") for scheme in valid_schemes):
                    raise ValueError(f"Invalid proxy scheme in: {server}")

                proxy_config = {"server": server}

                if len(parts) == 3:
                    proxy_config["username"] = parts[1]
                    proxy_config["password"] = parts[2]
                elif len(parts) != 1:
                    raise ValueError(f"Invalid proxy format: {proxy_entry}")

                parsed_proxies.append(proxy_config)

            except Exception as e:
                self.logger.error(f"Failed to parse proxy: {proxy_entry}, error: {e}")

        if parsed_proxies:
            self.logger.info(f"Loaded {len(parsed_proxies)} proxies for rotation.")

        return parsed_proxies

    def get_current_proxy(self) -> dict[str, str] | None:
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
