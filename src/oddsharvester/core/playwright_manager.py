import logging
import random

from playwright.async_api import async_playwright

from oddsharvester.utils.constants import PLAYWRIGHT_BROWSER_ARGS, PLAYWRIGHT_BROWSER_ARGS_DOCKER
from oddsharvester.utils.utils import is_running_in_docker

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

    async def initialize(
        self,
        headless: bool,
        user_agent: str | None = None,
        locale: str | None = None,
        timezone_id: str | None = None,
        proxy: dict[str, str] | None = None,
    ):
        """
        Initialize and start Playwright with a browser and page.

        Args:
            is_webdriver_headless (bool): Whether to start the browser in headless mode.
            proxy (Optional[Dict[str, str]]): Proxy configuration with keys 'server', 'username', and 'password'.
        """
        try:
            self.logger.info("Starting Playwright...")
            self.playwright = await async_playwright().start()

            browser_args = PLAYWRIGHT_BROWSER_ARGS_DOCKER if is_running_in_docker() else PLAYWRIGHT_BROWSER_ARGS
            self.browser = await self.playwright.chromium.launch(headless=headless, args=browser_args, proxy=proxy)

            # Use provided user_agent or random default
            effective_user_agent = user_agent or random.choice(DEFAULT_USER_AGENTS)  # noqa: S311

            self.context = await self.browser.new_context(
                locale=locale,
                timezone_id=timezone_id,
                user_agent=effective_user_agent,
                viewport={"width": random.randint(1366, 1920), "height": random.randint(768, 1080)},  # noqa: S311
            )

            # Add anti-detection script
            await self.context.add_init_script(STEALTH_SCRIPT)

            self.page = await self.context.new_page()
            self.logger.info("Playwright initialized successfully.")

        except Exception as e:
            self.logger.error(f"Failed to initialize Playwright: {e!s}")
            raise

    async def cleanup(self):
        """Properly closes Playwright instances."""
        self.logger.info("Cleaning up Playwright resources...")
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.logger.info("Playwright resources cleanup complete.")
