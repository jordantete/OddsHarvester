from dataclasses import dataclass
import logging
from urllib.parse import urlparse, urlunparse

# A proxy is dropped from rotation after this many CONSECUTIVE proxy-attributable
# failures (navigation / rate-limit). The counter resets on any non-proxy outcome.
PROXY_CONSECUTIVE_FAILURE_THRESHOLD = 3

_VALID_SCHEMES = ("http://", "https://", "socks4://", "socks5://")
_DIRECT_KEY = "direct"
_PER_CONTEXT_SENTINEL = {"server": "per-context"}


@dataclass
class ProxyEntry:
    """A single proxy in the rotation pool."""

    key: str
    config: dict[str, str] | None
    consecutive_failures: int = 0
    blacklisted: bool = False


class ProxyManager:
    """Manages one or more proxies for Playwright, with round-robin rotation and failover.

    With 0 or 1 proxy the pool behaves like the legacy single-proxy manager (no
    rotation, no failover). With 2+ proxies it hands out proxies round-robin and
    blacklists any that fail repeatedly.
    """

    def __init__(
        self,
        proxy_urls: list[str] | None = None,
        proxy_user: str | None = None,
        proxy_pass: str | None = None,
        proxy_url: str | None = None,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)

        urls = self._normalize_urls(proxy_urls, proxy_url)
        legacy_single = len(urls) == 1

        self.entries: list[ProxyEntry] = []
        for url in urls:
            entry = self._build_entry(
                url,
                proxy_user=proxy_user if legacy_single else None,
                proxy_pass=proxy_pass if legacy_single else None,
            )
            if entry is not None:
                self.entries.append(entry)

        if (proxy_user or proxy_pass) and not legacy_single and len(self.entries) > 1:
            self.logger.warning(
                "--proxy-user/--proxy-pass are ignored with multiple proxies; "
                "embed credentials in each proxy URL instead."
            )

        if not self.entries:
            self.logger.info("No proxy provided, running without proxy.")
            self.entries = [ProxyEntry(key=_DIRECT_KEY, config=None)]

        self._real = [e for e in self.entries if e.config is not None]
        self._failover_enabled = len(self._real) >= 2
        self._cursor = 0
        self._exhausted_logged = False

    @staticmethod
    def _normalize_urls(proxy_urls: list[str] | None, proxy_url: str | None) -> list[str]:
        if proxy_urls:
            return [u for u in proxy_urls if u]
        if proxy_url:
            return [proxy_url]
        return []

    @staticmethod
    def _sanitize_url_for_logging(url: str) -> str:
        """Strip embedded credentials from a URL for safe logging."""
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            safe = parsed._replace(netloc=f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname)
            return urlunparse(safe)
        return url

    def _build_entry(
        self,
        url: str,
        proxy_user: str | None = None,
        proxy_pass: str | None = None,
    ) -> ProxyEntry | None:
        if not any(url.startswith(scheme) for scheme in _VALID_SCHEMES):
            self.logger.error("Invalid proxy scheme provided.")
            return None

        parsed = urlparse(url)
        server = self._sanitize_url_for_logging(url)  # scheme://host:port, no creds
        config: dict[str, str] = {"server": server}

        if parsed.username and parsed.password:
            config["username"] = parsed.username
            config["password"] = parsed.password
            self.logger.info(f"Configured proxy with authentication: {server}")
        elif proxy_user and proxy_pass:
            config["username"] = proxy_user
            config["password"] = proxy_pass
            self.logger.info(f"Configured proxy with authentication: {server}")
        elif proxy_user or proxy_pass:
            self.logger.warning("Both proxy_user and proxy_pass must be provided for authentication. Ignoring auth.")
            self.logger.info(f"Configured proxy without authentication: {server}")
        else:
            self.logger.info(f"Configured proxy without authentication: {server}")

        return ProxyEntry(key=server, config=config)

    def is_multi_proxy(self) -> bool:
        return len(self._real) >= 2

    def launch_proxy(self) -> dict[str, str] | None:
        """Proxy dict for browser.launch(). The sentinel enables per-context override (>=2 proxies)."""
        if self.is_multi_proxy():
            return dict(_PER_CONTEXT_SENTINEL)
        return self.entries[0].config

    def next_proxy(self) -> ProxyEntry | None:
        """Return the next non-blacklisted proxy (round-robin), or None if all are blacklisted."""
        n = len(self.entries)
        for i in range(n):
            idx = (self._cursor + i) % n
            entry = self.entries[idx]
            if not entry.blacklisted:
                self._cursor = (idx + 1) % n
                return entry
        if not self._exhausted_logged:
            self.logger.error("All proxies are blacklisted; remaining matches will fail.")
            self._exhausted_logged = True
        return None

    def report_result(self, key: str, is_proxy_failure: bool) -> None:
        """Record the outcome of a request that used the proxy identified by `key`.

        Only active with >=2 proxies. A proxy-attributable failure increments a
        consecutive-failure counter; any other outcome resets it. Reaching the
        threshold blacklists the proxy.
        """
        if not self._failover_enabled:
            return
        entry = next((e for e in self.entries if e.key == key), None)
        if entry is None or entry.blacklisted:
            return
        if is_proxy_failure:
            entry.consecutive_failures += 1
            if entry.consecutive_failures >= PROXY_CONSECUTIVE_FAILURE_THRESHOLD:
                entry.blacklisted = True
                self.logger.warning(
                    f"Proxy blacklisted after {entry.consecutive_failures} consecutive failures: {entry.key}"
                )
        else:
            entry.consecutive_failures = 0

    # Legacy accessors (single-proxy compatibility) ---------------------------------

    def get_proxy(self) -> dict[str, str] | None:
        """Legacy: return the first entry's config (single/no-proxy compatibility)."""
        return self.entries[0].config

    def get_current_proxy(self) -> dict[str, str] | None:
        """Legacy method - use get_proxy() instead."""
        return self.get_proxy()

    def rotate_proxy(self):
        """Legacy no-op; rotation now happens per request via next_proxy()."""
        self.logger.debug("Proxy rotation handled per-request via next_proxy().")
