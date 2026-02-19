import logging
from urllib.parse import urlparse, urlunparse


class ProxyManager:
    """Manages proxy configuration for Playwright."""

    def __init__(
        self,
        proxy_url: str | None = None,
        proxy_user: str | None = None,
        proxy_pass: str | None = None,
    ):
        """
        Initialize ProxyManager with proxy configuration.

        Args:
            proxy_url: Proxy server URL (e.g., http://proxy.example.com:8080).
            proxy_user: Proxy username (optional).
            proxy_pass: Proxy password (optional).
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.proxy = self._build_proxy_config(proxy_url, proxy_user, proxy_pass)

    @staticmethod
    def _sanitize_url_for_logging(url: str) -> str:
        """Strip embedded credentials from a URL for safe logging."""
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            safe = parsed._replace(netloc=f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname)
            return urlunparse(safe)
        return url

    def _build_proxy_config(
        self,
        proxy_url: str | None,
        proxy_user: str | None,
        proxy_pass: str | None,
    ) -> dict[str, str] | None:
        """
        Build proxy configuration dict for Playwright.

        Args:
            proxy_url: Proxy server URL.
            proxy_user: Proxy username.
            proxy_pass: Proxy password.

        Returns:
            Proxy configuration dict or None if no proxy configured.
        """
        if not proxy_url:
            self.logger.info("No proxy provided, running without proxy.")
            return None

        valid_schemes = ("http://", "https://", "socks4://", "socks5://")
        if not any(proxy_url.startswith(scheme) for scheme in valid_schemes):
            self.logger.error("Invalid proxy scheme provided.")
            return None

        safe_url = self._sanitize_url_for_logging(proxy_url)
        proxy_config = {"server": proxy_url}

        if proxy_user and proxy_pass:
            proxy_config["username"] = proxy_user
            proxy_config["password"] = proxy_pass
            self.logger.info(f"Configured proxy with authentication: {safe_url}")
        elif proxy_user or proxy_pass:
            self.logger.warning("Both proxy_user and proxy_pass must be provided for authentication. Ignoring auth.")
            self.logger.info(f"Configured proxy without authentication: {safe_url}")
        else:
            self.logger.info(f"Configured proxy without authentication: {safe_url}")

        return proxy_config

    def get_proxy(self) -> dict[str, str] | None:
        """
        Returns the proxy configuration.

        Returns:
            Proxy config dict or None if no proxy configured.
        """
        if not self.proxy:
            self.logger.info("No proxy available, using direct connection.")
            return None

        return self.proxy

    # Legacy method for backwards compatibility
    def get_current_proxy(self) -> dict[str, str] | None:
        """Legacy method - use get_proxy() instead."""
        return self.get_proxy()

    def rotate_proxy(self):
        """Legacy method - no-op with single proxy configuration."""
        self.logger.debug("Proxy rotation not supported with single proxy configuration.")
