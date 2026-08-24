"""See module docstring in core/browser/__init__.py."""

import logging

from playwright.async_api import Page

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import (
    MARKET_TAB_TIMEOUT_MS,
    TAB_SWITCH_WAIT_MS,
)

# In-page hash switch: the SPA routes the match view off location.hash
# ('#<id>:<market>;<scope>') and re-renders on hashchange (2026-08 redesign).
HASH_SWITCH_JS = """
(args) => {
    window.location.hash = '#' + args.fragment + ':' + args.code + ';' + args.scope;
    window.dispatchEvent(new HashChangeEvent('hashchange', { newURL: window.location.href }));
}
"""


class MarketTabNavigator:
    """Switch the match view to a market tab, hash-first with a tab-click fallback."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def navigate_to_tab(self, page: Page, market_tab_name: str, timeout: int = MARKET_TAB_TIMEOUT_MS) -> bool:
        """Navigate to a market tab by its English name.

        Primary path rewrites the URL hash to the market's language-independent
        code (works on localized mirrors, gotchas §7). Fallback clicks the
        sports-nav tab matching the name (markets missing from MARKET_TAB_CODES,
        or a hash route the SPA refuses).
        """
        self.logger.info(f"Attempting to navigate to market tab: {market_tab_name}")

        # In-play views route their own market codes (e.g. 'O/U', not
        # 'over-under'); the pre-match hash path would flip or break the view.
        inplay = "/inplay-odds/" in page.url
        code = OddsPortalSelectors.MARKET_TAB_CODES.get(market_tab_name)
        if not inplay and code and await self._navigate_by_hash(page, code, timeout):
            self.logger.info(f"Successfully navigated to {market_tab_name} tab (hash code '{code}').")
            return True

        if await self._click_tab_by_text(page, market_tab_name):
            self.logger.info(f"Successfully navigated to {market_tab_name} tab (tab click).")
            return True

        self.logger.error(f"Failed to reach the {market_tab_name} tab (hash and tab-click paths).")
        return False

    async def _navigate_by_hash(self, page: Page, code: str, timeout: int) -> bool:
        fragment = OddsPortalSelectors.event_id_from_url(page.url)
        if not fragment:
            return False
        # Preserve the current period scope so a market switch keeps the period.
        scope = OddsPortalSelectors.period_scope_from_url(page.url) or 2
        try:
            await page.evaluate(HASH_SWITCH_JS, {"fragment": fragment, "code": code, "scope": scope})
            await page.wait_for_timeout(TAB_SWITCH_WAIT_MS)
            if OddsPortalSelectors.market_code_from_url(page.url) != code:
                return False
            await page.wait_for_selector(OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR, timeout=timeout)
            return True
        except Exception as e:
            self.logger.warning(f"Hash navigation to market code '{code}' failed: {e}")
            return False

    async def _click_tab_by_text(self, page: Page, market_tab_name: str) -> bool:
        try:
            elements = await page.query_selector_all(OddsPortalSelectors.MARKET_TAB_ANY)
            for element in elements:
                text = (await element.text_content() or "").strip()
                if text and market_tab_name.lower() in text.lower():
                    await element.click()
                    await page.wait_for_timeout(TAB_SWITCH_WAIT_MS)
                    return await self._verify_tab_is_active(page, market_tab_name)
            self.logger.info(f"No sports-nav tab matched '{market_tab_name}'.")
            return False
        except Exception as e:
            self.logger.error(f"Error clicking market tab '{market_tab_name}': {e}")
            return False

    async def _verify_tab_is_active(self, page: Page, market_tab_name: str) -> bool:
        try:
            active = await page.query_selector(OddsPortalSelectors.MARKET_TAB_ACTIVE)
            if active:
                text = (await active.text_content() or "").strip()
                if text and market_tab_name.lower() in text.lower():
                    self.logger.info(f"Tab '{market_tab_name}' is confirmed active")
                    return True
            self.logger.warning(f"Tab '{market_tab_name}' is not confirmed as active")
            return False
        except Exception as e:
            self.logger.error(f"Error verifying active market tab: {e}")
            return False
