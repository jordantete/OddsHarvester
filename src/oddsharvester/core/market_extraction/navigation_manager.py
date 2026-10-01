import logging

from playwright.async_api import Page

from oddsharvester.core.browser.market_navigation import MarketTabNavigator
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import DEFAULT_MARKET_TIMEOUT_MS, SCROLL_PAUSE_TIME_MS


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

    async def select_specific_market(self, page: Page, specific_market: str, main_market: str | None = None) -> bool:
        """Select a specific submarket within the main market.

        On localized mirrors the submarket label prefix is translated, so match
        on the language-independent tail (gotchas §7). The tail must be the end
        of the row's label, and a tail two rows share selects nothing.
        """
        text = OddsPortalSelectors.submarket_match_text(specific_market, main_market)
        return await self.scroller.scroll_until_visible_and_click_parent(
            page=page,
            selector=OddsPortalSelectors.SUB_MARKET_SELECTOR,
            text=text,
            click_ancestor=OddsPortalSelectors.SUB_MARKET_CLICK_ANCESTOR,
            exact_tail=True,
        )

    async def close_specific_market(self, page: Page, specific_market: str, main_market: str | None = None) -> bool:
        """Close a specific submarket after scraping; its header click toggles it."""
        self.logger.info(f"Closing sub-market: {specific_market}")
        return await self.select_specific_market(page, specific_market, main_market=main_market)

    async def wait_for_page_load(self, page: Page) -> None:
        """Wait for page content to load."""
        await page.wait_for_timeout(SCROLL_PAUSE_TIME_MS)
