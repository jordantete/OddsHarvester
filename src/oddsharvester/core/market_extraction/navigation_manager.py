import logging

from playwright.async_api import Page

from oddsharvester.core.browser.market_navigation import MarketTabNavigator
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import DEFAULT_MARKET_TIMEOUT_MS, MARKET_SWITCH_WAIT_TIME_MS, SCROLL_PAUSE_TIME_MS


class NavigationManager:
    """Handles browser navigation for market extraction."""

    def __init__(self, tab_navigator: MarketTabNavigator, scroller: PageScroller):
        """Initialize NavigationManager."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.tab_navigator = tab_navigator
        self.scroller = scroller

    async def navigate_to_market_tab(self, page: Page, market_tab_name: str) -> bool:
        """Navigate to a specific market tab."""
        return await self.tab_navigator.navigate_to_tab(
            page=page, market_tab_name=market_tab_name, timeout=DEFAULT_MARKET_TIMEOUT_MS
        )

    async def wait_for_market_switch(self, page: Page, market_name: str, max_attempts: int = 3) -> bool:
        """
        Wait for the market switch to complete and verify the correct market is active.

        Args:
            page (Page): The Playwright page instance.
            market_name (str): The name of the market that should be active.
            max_attempts (int): Maximum number of verification attempts.

        Returns:
            bool: True if the market switch is confirmed, False otherwise.
        """
        self.logger.info(f"Waiting for market switch to complete for: {market_name}")

        # Localized-mirror confirmation via URL-fragment code (gotchas §7).
        target_code = OddsPortalSelectors.MARKET_TAB_CODES.get(market_name)

        for attempt in range(max_attempts):
            try:
                # Wait for the market switch animation to complete
                await page.wait_for_timeout(MARKET_SWITCH_WAIT_TIME_MS)

                if target_code and OddsPortalSelectors.market_code_from_url(page.url) == target_code:
                    self.logger.info(f"Market switch confirmed via URL code: {market_name} is active")
                    return True

                active_tab = await page.query_selector("li.active, li[class*='active'], .active")
                if active_tab:
                    tab_text = await active_tab.text_content()
                    if tab_text and market_name.lower() in tab_text.lower():
                        self.logger.info(f"Market switch confirmed: {market_name} is active")
                        return True

            except Exception as e:
                self.logger.warning(f"Market switch verification attempt {attempt + 1} failed: {e}")

        self.logger.warning(f"Market switch verification failed after {max_attempts} attempts")
        return False

    async def select_specific_market(self, page: Page, specific_market: str, main_market: str | None = None) -> bool:
        """Select a specific submarket within the main market.

        On localized mirrors the submarket label prefix is translated, so match
        on the language-independent tail (gotchas §7).
        """
        text = OddsPortalSelectors.submarket_match_text(specific_market, main_market)
        return await self.scroller.scroll_until_visible_and_click_parent(
            page=page,
            selector=OddsPortalSelectors.SUB_MARKET_SELECTOR,
            text=text,
        )

    async def close_specific_market(self, page: Page, specific_market: str, main_market: str | None = None) -> bool:
        """Close a specific submarket after scraping."""
        self.logger.info(f"Closing sub-market: {specific_market}")
        text = OddsPortalSelectors.submarket_match_text(specific_market, main_market)
        return await self.scroller.scroll_until_visible_and_click_parent(
            page=page,
            selector=OddsPortalSelectors.SUB_MARKET_SELECTOR,
            text=text,
        )

    async def wait_for_page_load(self, page: Page) -> None:
        """Wait for page content to load."""
        await page.wait_for_timeout(SCROLL_PAUSE_TIME_MS)
