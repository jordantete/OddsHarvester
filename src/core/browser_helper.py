import logging
import time

from playwright.async_api import Page

from src.core.odds_portal_selectors import OddsPortalSelectors


class BrowserHelper:
    """
    A helper class for managing common browser interactions using Playwright.

    This class provides high-level methods for:
    - Cookie banner management
    - Market navigation (including hidden markets)
    - Scrolling operations
    - Element interaction utilities
    """

    def __init__(self):
        """
        Initialize the BrowserHelper class.
        """
        self.logger = logging.getLogger(self.__class__.__name__)

    # =============================================================================
    # COOKIE BANNER MANAGEMENT
    # =============================================================================

    async def dismiss_cookie_banner(self, page: Page, selector: str | None = None, timeout: int = 10000):
        """
        Dismiss the cookie banner if it appears on the page.

        Args:
            page (Page): The Playwright page instance to interact with.
            selector (str): The CSS selector for the cookie banner's accept button.
            timeout (int): Maximum time to wait for the banner (default: 10000ms).

        Returns:
            bool: True if the banner was dismissed, False otherwise.
        """
        if selector is None:
            selector = OddsPortalSelectors.COOKIE_BANNER

        try:
            self.logger.info("Checking for cookie banner...")
            await page.wait_for_selector(selector, timeout=timeout)
            self.logger.info("Cookie banner found. Dismissing it.")
            await page.click(selector)
            return True

        except TimeoutError:
            self.logger.info("No cookie banner detected.")
            return False

        except Exception as e:
            self.logger.error(f"Error while dismissing cookie banner: {e}")
            return False

    # =============================================================================
    # MARKET NAVIGATION
    # =============================================================================

    async def navigate_to_market_tab(self, page: Page, market_tab_name: str, timeout=10000):
        """
        Navigate to a specific market tab by its name.
        Now supports hidden markets under the "More" dropdown.

        Args:
            page: The Playwright page instance.
            market_tab_name: The name of the market tab to navigate to (e.g., 'Over/Under', 'Draw No Bet').
            timeout: Timeout in milliseconds.

        Returns:
            bool: True if the market tab was successfully selected, False otherwise.
        """
        self.logger.info(f"Attempting to navigate to market tab: {market_tab_name}")

        # First attempt: Try to find the market directly in visible tabs
        market_found = False
        for selector in OddsPortalSelectors.MARKET_TAB_SELECTORS:
            if await self._wait_and_click(page=page, selector=selector, text=market_tab_name, timeout=timeout):
                market_found = True
                break

        if market_found:
            # Verify that the tab is actually active
            if await self._verify_tab_is_active(page, market_tab_name):
                self.logger.info(f"Successfully navigated to {market_tab_name} tab (directly visible).")
                return True
            else:
                self.logger.warning(f"Tab {market_tab_name} was clicked but is not active.")

        # Second attempt: Try to find the market in the "More" dropdown
        self.logger.info(f"Market '{market_tab_name}' not found in visible tabs. Checking 'More' dropdown...")
        if await self._click_more_if_market_hidden(page, market_tab_name, timeout):
            # Verify that the tab is actually active
            if await self._verify_tab_is_active(page, market_tab_name):
                self.logger.info(f"Successfully navigated to {market_tab_name} tab (via 'More' dropdown).")
                return True
            else:
                self.logger.warning(f"Tab {market_tab_name} was clicked but is not active.")

        self.logger.error(
            f"Failed to find or click the {market_tab_name} tab (searched visible tabs and 'More' dropdown)."
        )
        return False

    # =============================================================================
    # SCROLLING OPERATIONS
    # =============================================================================

    async def scroll_until_loaded(
        self,
        page: Page,
        timeout=30,
        scroll_pause_time=3,
        max_scroll_attempts=5,
        content_check_selector: str | None = None,
    ):
        """
        Scrolls down the page until no new content is loaded or a timeout is reached.

        This method is useful for pages that load content dynamically as the user scrolls.
        It attempts to scroll the page to the bottom multiple times, waiting for a specified
        interval between scrolls. Scrolling stops when no new content is detected, a timeout
        occurs, or the maximum number of scroll attempts is reached.

        Args:
            page (Page): The Playwright page instance to interact with.
            timeout (int): The maximum time (in seconds) to attempt scrolling (default: 30).
            scroll_pause_time (int): The time (in seconds) to pause between scrolls (default: 3).
            max_scroll_attempts (int): The maximum number of attempts to detect new content (default: 5).
            content_check_selector (str): Optional CSS selector to check for new content after scrolling.

        Returns:
            bool: True if scrolling completed successfully, False otherwise.
        """
        self.logger.info("Will scroll to the bottom of the page to load all content.")
        end_time = time.time() + timeout
        last_height = await page.evaluate("document.body.scrollHeight")
        last_element_count = 0
        stable_count_attempts = 0

        # Get initial element count if selector is provided
        if content_check_selector:
            initial_elements = await page.query_selector_all(content_check_selector)
            last_element_count = len(initial_elements)
            self.logger.info(f"Initial element count: {last_element_count}")

        self.logger.info(f"Initial page height: {last_height}")

        while time.time() < end_time:
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(scroll_pause_time * 1000)

            new_height = await page.evaluate("document.body.scrollHeight")
            new_element_count = 0

            # Count elements if selector is provided
            if content_check_selector:
                elements = await page.query_selector_all(content_check_selector)
                new_element_count = len(elements)
                self.logger.info(f"Current element count: {new_element_count} (height: {new_height})")

                # Check if element count is stable
                if new_element_count == last_element_count and new_height == last_height:
                    stable_count_attempts += 1
                    self.logger.debug(f"Content stable. Attempt {stable_count_attempts}/{max_scroll_attempts}.")

                    if stable_count_attempts >= max_scroll_attempts:
                        self.logger.info(f"Content stabilized at {new_element_count} elements. Scrolling complete.")
                        return True
                else:
                    stable_count_attempts = 0  # Reset if content changed
                    last_element_count = new_element_count
            else:
                # Fallback to height-based detection
                if new_height == last_height:
                    stable_count_attempts += 1
                    self.logger.debug(f"Height stable. Attempt {stable_count_attempts}/{max_scroll_attempts}.")

                    if stable_count_attempts >= max_scroll_attempts:
                        self.logger.info("Page height stabilized. Scrolling complete.")
                        return True
                else:
                    stable_count_attempts = 0

            last_height = new_height

        self.logger.info("Reached scrolling timeout. Stopping scroll.")
        return False

    async def scroll_until_visible_and_click_parent(
        self, page, selector, text: str | None = None, timeout=20, scroll_pause_time=3
    ):
        """
        Scrolls the page until an element matching the selector and text is visible, then clicks its parent element.

        Args:
            page (Page): The Playwright page instance.
            selector (str): The CSS selector of the element.
            text (str): Optional. The text content to match.
            timeout (int): Timeout in seconds (default: 20).
            scroll_pause_time (int): Pause time in seconds between scrolls (default: 3).

        Returns:
            bool: True if the parent element was clicked successfully, False otherwise.
        """
        end_time = time.time() + timeout

        while time.time() < end_time:
            elements = await page.query_selector_all(selector)

            for element in elements:
                if text:
                    element_text = await element.text_content()

                    if element_text and text in element_text:
                        bounding_box = await element.bounding_box()

                        if bounding_box:
                            self.logger.info(f"Element with text '{text}' is visible. Clicking its parent.")
                            parent_element = await element.evaluate_handle("element => element.parentElement")
                            await parent_element.click()
                            return True
                else:
                    bounding_box = await element.bounding_box()
                    if bounding_box:
                        self.logger.info("Element is visible. Clicking its parent.")
                        parent_element = await element.evaluate_handle("element => element.parentElement")
                        await parent_element.click()
                        return True

            await page.evaluate("window.scrollBy(0, 500);")
            await page.wait_for_timeout(scroll_pause_time * 1000)

        self.logger.warning(
            f"Failed to find and click parent of element matching selector '{selector}' with text '{text}' within timeout."
        )
        return False

    # =============================================================================
    # PRIVATE HELPER METHODS
    # =============================================================================

    async def _wait_and_click(self, page: Page, selector: str, text: str | None = None, timeout: float = 5000):
        """
        Waits for a selector and optionally clicks an element based on its text.

        Args:
            page (Page): The Playwright page instance to interact with.
            selector (str): The CSS selector to wait for.
            text (str): Optional. The text of the element to click.
            timeout (float): The waiting time for the element to click.

        Returns:
            bool: True if the element is clicked successfully, False otherwise.
        """
        try:
            await page.wait_for_selector(selector=selector, timeout=timeout)

            if text:
                return await self._click_by_text(page=page, selector=selector, text=text)
            else:
                # Click the first element matching the selector
                element = await page.query_selector(selector)
                await element.click()
                return True

        except Exception as e:
            self.logger.error(f"Error waiting for or clicking selector '{selector}': {e}")
            return False

    async def _click_by_text(self, page: Page, selector: str, text: str) -> bool:
        """
        Attempts to click an element based on its text content.

        This method searches for all elements matching a specific selector, retrieves their
        text content, and checks if the provided text is a substring of the element's text.
        If a match is found, the method clicks the element.

        Args:
            page (Page): The Playwright page instance to interact with.
            selector (str): The CSS selector for the elements to search (e.g., '.btn', 'div').
            text (str): The text content to match as a substring.

        Returns:
            bool: True if an element with the matching text was successfully clicked, False otherwise.

        Raises:
            Exception: Logs the error and returns False if an issue occurs during execution.
        """
        try:
            elements = await page.query_selector_all(selector)

            for element in elements:
                element_text = await element.text_content()

                if element_text and text in element_text:
                    await element.click()
                    return True

            self.logger.info(f"Element with text '{text}' not found.")
            return False

        except Exception as e:
            self.logger.error(f"Error clicking element with text '{text}': {e}")
            return False

    async def _click_more_if_market_hidden(self, page: Page, market_tab_name: str, timeout: int = 10000):
        """
        Attempts to find and click a market tab hidden in the "More" dropdown.

        Args:
            page (Page): The Playwright page instance.
            market_tab_name (str): The name of the market tab to find.
            timeout (int): Timeout in milliseconds.

        Returns:
            bool: True if the market was found and clicked in the "More" dropdown, False otherwise.
        """
        try:
            more_clicked = False
            for selector in OddsPortalSelectors.MORE_BUTTON_SELECTORS:
                try:
                    more_element = await page.query_selector(selector)
                    if more_element:
                        text = await more_element.text_content()
                        if text and ("more" in text.lower() or "..." in text):
                            self.logger.info(f"Clicking 'More' button: '{text.strip()}'")
                            await more_element.click()
                            more_clicked = True
                            break
                except Exception as e:
                    self.logger.debug(f"Exception while searching for 'More' button with selector '{selector}': {e}")
                    continue

            if not more_clicked:
                self.logger.warning("Could not find or click 'More' button")
                return False

            await page.wait_for_timeout(1000)

            dropdown_selectors = OddsPortalSelectors.get_dropdown_selectors_for_market(market_tab_name)
            for selector in dropdown_selectors:
                try:
                    dropdown_element = await page.query_selector(selector)
                    if dropdown_element:
                        text = await dropdown_element.text_content()
                        if text and market_tab_name.lower() in text.lower():
                            self.logger.info(f"Found '{market_tab_name}' in dropdown. Clicking...")
                            await dropdown_element.click()
                            return True
                except Exception as e:
                    self.logger.debug(
                        f"Exception while searching for market '{market_tab_name}' in dropdown with selector '{selector}': {e}"
                    )
                    continue

            self.logger.info("Debugging dropdown content:")
            dropdown_items = await page.query_selector_all(OddsPortalSelectors.DROPDOWN_DEBUG_ELEMENTS)
            for item in dropdown_items[:10]:  # Limit to first 10 items
                try:
                    text = await item.text_content()
                    if text and text.strip():
                        self.logger.info(f"  Dropdown item: '{text.strip()}'")
                except Exception as e:
                    self.logger.debug(f"Exception while logging dropdown item: {e}")
                    continue

            return False

        except Exception as e:
            self.logger.error(f"Error in _click_more_if_market_hidden: {e}")
            return False

    async def _verify_tab_is_active(self, page: Page, market_tab_name: str) -> bool:
        """
        Verify that a market tab is actually active after clicking.

        Args:
            page (Page): The Playwright page instance.
            market_tab_name (str): The name of the market tab to verify.

        Returns:
            bool: True if the tab is active, False otherwise.
        """
        try:
            # Wait a bit for the tab switch to complete
            await page.wait_for_timeout(500)

            # Check for active tab indicators
            active_selectors = ["li.active", "li[class*='active']", ".active", "[class*='active']"]

            for selector in active_selectors:
                try:
                    active_element = await page.query_selector(selector)
                    if active_element:
                        text = await active_element.text_content()
                        if text and market_tab_name.lower() in text.lower():
                            self.logger.info(f"Tab '{market_tab_name}' is confirmed active")
                            return True
                except Exception as e:
                    self.logger.debug(f"Exception checking active selector '{selector}': {e}")
                    continue

            # Alternative: check if the market name appears in the current URL or page content
            page_content = await page.content()
            if market_tab_name and market_tab_name.lower() in page_content.lower():
                self.logger.info(f"Market '{market_tab_name}' found in page content")
                return True

            self.logger.warning(f"Tab '{market_tab_name}' is not confirmed as active")
            return False

        except Exception as e:
            self.logger.error(f"Error verifying tab is active: {e}")
            return False
