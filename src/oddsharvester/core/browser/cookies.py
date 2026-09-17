"""See module docstring in core/browser/__init__.py."""

import logging

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import COOKIE_BANNER_TIMEOUT_MS


class CookieDismisser:
    """Dismiss the cookie consent banner if present on the page."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._dismissed_contexts: set = set()

    async def dismiss(
        self,
        page: Page,
        selector: str | None = None,
        timeout: int = COOKIE_BANNER_TIMEOUT_MS,
    ) -> bool:
        """Dismiss the cookie banner if it appears.

        Returns True if a banner was found and dismissed, or was already dismissed for
        this page's context; False otherwise (banner absent or click failed).
        """
        if selector is None:
            selector = OddsPortalSelectors.COOKIE_BANNER

        # Consent is stored per browser context, so once accepted the banner cannot
        # render again and looking for it costs a full timeout on every later page.
        context = page.context
        if context in self._dismissed_contexts:
            return True

        try:
            self.logger.info("Checking for cookie banner...")
            await page.wait_for_selector(selector, timeout=timeout)
            self.logger.info("Cookie banner found. Dismissing it.")
            await page.click(selector)
            self._dismissed_contexts.add(context)
            return True

        except PlaywrightTimeoutError:
            self.logger.info("No cookie banner detected.")
            return False

        except Exception as e:
            self.logger.error(f"Error while dismissing cookie banner: {e}")
            return False
