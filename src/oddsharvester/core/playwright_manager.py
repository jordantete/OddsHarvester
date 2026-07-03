import logging
import os
from pathlib import Path
import random

from playwright.async_api import async_playwright

from oddsharvester.core.exceptions import AllProxiesExhaustedError
from oddsharvester.utils.constants import PLAYWRIGHT_BROWSER_ARGS, PLAYWRIGHT_BROWSER_ARGS_DOCKER
from oddsharvester.utils.utils import is_running_in_docker

HAR_REPLAY_ENV_VAR = "ODDSHARVESTER_HAR_REPLAY"
HAR_RECORD_ENV_VAR = "ODDSHARVESTER_HAR_RECORD"
HAR_REPLAY_URL_PATTERN = "**oddsportal.com/**"

# Anti-detection script to hide automation signatures
STEALTH_SCRIPT = """
Object.defineProperty(navigator, "webdriver", {get: () => undefined});
window.chrome = {runtime: {}};
Object.defineProperty(navigator, "plugins", {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, "languages", {get: () => ["en-US", "en"]});
"""

# Default user agents that look like real browsers
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]


class PlaywrightManager:
    """
    Manages Playwright browser lifecycle and configuration.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.timezone_id: str | None = None
        self.contexts: dict = {}
        self._default_key: str | None = None
        self._proxy_manager = None

    async def initialize(
        self,
        headless: bool,
        user_agent: str | None = None,
        locale: str | None = None,
        timezone_id: str | None = None,
        proxy_manager=None,
    ):
        """
        Initialize and start Playwright with a browser and page.

        Args:
            is_webdriver_headless (bool): Whether to start the browser in headless mode.
            proxy_manager: Optional ProxyManager providing the launch proxy and, in multi-proxy
                mode, one context per proxy.
        """
        try:
            self.logger.info("Starting Playwright...")
            self.timezone_id = timezone_id
            self._proxy_manager = proxy_manager
            self.playwright = await async_playwright().start()

            browser_args = PLAYWRIGHT_BROWSER_ARGS_DOCKER if is_running_in_docker() else PLAYWRIGHT_BROWSER_ARGS
            launch_proxy = proxy_manager.launch_proxy() if proxy_manager else None
            self.browser = await self.playwright.chromium.launch(
                headless=headless, args=browser_args, proxy=launch_proxy
            )

            effective_user_agent = user_agent or random.choice(DEFAULT_USER_AGENTS)  # noqa: S311

            # (key, per-context proxy override) for each context to create.
            # Per-context proxy is used ONLY in multi-proxy mode; otherwise the
            # single context inherits the launch proxy (unchanged behavior).
            if proxy_manager and proxy_manager.is_multi_proxy():
                context_specs = [(e.key, e.config) for e in proxy_manager.entries]
            elif proxy_manager:
                context_specs = [(proxy_manager.entries[0].key, None)]
            else:
                context_specs = [("direct", None)]

            self._default_key = context_specs[0][0]
            for index, (key, ctx_proxy) in enumerate(context_specs):
                self.contexts[key] = await self._create_context(
                    proxy=ctx_proxy,
                    user_agent=effective_user_agent,
                    locale=locale,
                    timezone_id=timezone_id,
                    enable_har=(index == 0),
                )

            self.context = self.contexts[self._default_key]
            self.page = await self.context.new_page()

            # When no explicit timezone is requested, the browser context falls
            # back to the host system timezone. Capture the effective timezone
            # so date-header parsing and DOM match-date conversion use the same
            # zone the browser actually rendered in (see docs/agentic-gotchas.md
            # §10) — otherwise parsing silently assumed UTC while the browser
            # rendered in the system tz, causing date-filter misses near
            # midnight and on cross-timezone leagues.
            if self.timezone_id is None:
                try:
                    self.timezone_id = await self.page.evaluate(
                        "() => Intl.DateTimeFormat().resolvedOptions().timeZone"
                    )
                except Exception as e:
                    self.logger.warning(f"Could not resolve browser timezone, assuming UTC: {e}")
                    self.timezone_id = "UTC"

            self.logger.info("Playwright initialized successfully.")

        except Exception as e:
            self.logger.error(f"Failed to initialize Playwright: {e!s}")
            raise

    async def _create_context(self, proxy, user_agent, locale, timezone_id, enable_har):
        """Create one browser context. HAR record/replay is applied to the default context only."""
        context_kwargs = {
            "locale": locale,
            "timezone_id": timezone_id,
            "user_agent": user_agent,
            "viewport": {"width": random.randint(1366, 1920), "height": random.randint(768, 1080)},  # noqa: S311
        }
        if proxy is not None:
            context_kwargs["proxy"] = proxy
        if enable_har:
            har_record_path = os.environ.get(HAR_RECORD_ENV_VAR)
            if har_record_path:
                self.logger.info(f"HAR recording mode active: {har_record_path}")
                context_kwargs["record_har_path"] = Path(har_record_path)
                context_kwargs["record_har_mode"] = "full"
                context_kwargs["record_har_url_filter"] = HAR_REPLAY_URL_PATTERN

        context = await self.browser.new_context(**context_kwargs)
        await context.add_init_script(STEALTH_SCRIPT)

        if enable_har:
            har_replay_path = os.environ.get(HAR_REPLAY_ENV_VAR)
            if har_replay_path:
                self.logger.info(f"HAR replay mode active: {har_replay_path}")
                await context.route_from_har(
                    Path(har_replay_path),
                    url=HAR_REPLAY_URL_PATTERN,
                    not_found="abort",
                )
        return context

    def non_default_context_keys(self) -> list[str]:
        """Keys of proxy contexts other than the default one (empty for single/no-proxy)."""
        return [key for key in self.contexts if key != self._default_key]

    async def new_page_on_key(self, key: str):
        """Open a new page in the context bound to a specific proxy key."""
        return await self.contexts[key].new_page()

    async def new_rotated_page(self):
        """Open a page on the next round-robin proxy. Returns (page, proxy_key).

        Raises AllProxiesExhaustedError if every proxy is blacklisted.
        """
        if self._proxy_manager is None:
            return await self.context.new_page(), self._default_key
        entry = self._proxy_manager.next_proxy()
        if entry is None:
            raise AllProxiesExhaustedError("All proxies are blacklisted; cannot open a new page.")
        page = await self.contexts[entry.key].new_page()
        return page, entry.key

    def report_page_result(self, key: str, is_proxy_failure: bool) -> None:
        """Forward a per-page outcome to the proxy pool (no-op without a proxy manager)."""
        if self._proxy_manager is not None:
            self._proxy_manager.report_result(key, is_proxy_failure)

    def blacklist_proxy(self, key: str) -> None:
        """Force a proxy out of rotation (no-op without a proxy manager)."""
        if self._proxy_manager is not None:
            self._proxy_manager.blacklist_proxy(key)

    async def cleanup(self):
        """Properly closes Playwright instances."""
        self.logger.info("Cleaning up Playwright resources...")
        if self.page:
            await self.page.close()
        for context in self.contexts.values():
            await context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.logger.info("Playwright resources cleanup complete.")
