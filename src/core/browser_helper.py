import logging
import time

from playwright.async_api import Page


class BrowserHelper:
    """
    A helper class for managing common browser interactions using Playwright.
    """

    def __init__(self):
        """
        Initialize the BrowserHelper class.
        """
        self.logger = logging.getLogger(self.__class__.__name__)

    async def dismiss_cookie_banner(
        self, page: Page, selector: str = "#onetrust-accept-btn-handler", timeout: int = 10000
    ):
        """
        Dismiss the cookie banner if it appears on the page.

        Args:
            page (Page): The Playwright page instance to interact with.
            selector (str): The CSS selector for the cookie banner's accept button.
            timeout (int): Maximum time to wait for the banner (default: 5000ms).

        Returns:
            bool: True if the banner was dismissed, False otherwise.
        """
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

    async def navigate_to_market_tab(self, page: Page, market_tab_name: str, timeout=10000):
        """
        Navigate to a specific market tab by its name.

        Args:
            page: The Playwright page instance.
            market_tab_name: The name of the market tab to navigate to (e.g., 'Over/Under').
            timeout: Timeout in milliseconds.

        Returns:
            bool: True if the market tab was successfully selected, False otherwise.
        """
        markets_tab_selector = "ul.visible-links.bg-black-main.odds-tabs > li"
        self.logger.info(f"Attempting to navigate to market tab: {market_tab_name}")

        if not await self._wait_and_click(
            page=page, selector=markets_tab_selector, text=market_tab_name, timeout=timeout
        ):
            self.logger.error(f"Failed to find or click the {market_tab_name} tab.")
            return False

        self.logger.info(f"Successfully navigated to {market_tab_name} tab.")
        return True

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
        self.logger.info("Will scroll to the bottom of the page.")
        end_time = time.time() + timeout
        last_height = await page.evaluate("document.body.scrollHeight")
        self.logger.info(f"__scroll_until_loaded last_height: {last_height}")
        scroll_attempts = 0

        while time.time() < end_time:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(scroll_pause_time * 1000)

            new_height = await page.evaluate("document.body.scrollHeight")
            self.logger.info(f"__scroll_until_loaded new_height: {new_height}")

            # Check if content is loaded using optional selector
            if content_check_selector:
                elements = await page.query_selector_all(content_check_selector)
                if elements:
                    self.logger.info(f"Content detected with selector '{content_check_selector}'. Stopping scroll.")
                    return True

            # Check if scroll height has stopped changing
            if new_height == last_height:
                scroll_attempts += 1
                self.logger.debug(f"No new content detected. Scroll attempt {scroll_attempts}/{max_scroll_attempts}.")

                if scroll_attempts >= max_scroll_attempts:
                    self.logger.info("Maximum scroll attempts reached. Stopping scroll.")
                    return False
            else:
                scroll_attempts = 0  # Reset attempts if content is detected

            last_height = new_height

        self.logger.info("Reached scrolling timeout without detecting new content.")
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

    async def click_by_inner_text(self, page: Page, selector: str, text: str) -> bool:
        """
        Attempts to click an element based on its inner text content.

        This method searches for elements matching a specific selector and checks if their
        inner text matches the provided text. It performs a "cleaned text" comparison to
        handle potential whitespace or formatting differences.

        Args:
            page (Page): The Playwright page instance to interact with.
            selector (str): The selector for the elements to search (e.g., 'div', 'span').
            text (str): The text content to match.

        Returns:
            bool: True if the element was successfully clicked, False otherwise.

        Raises:
            Exception: Logs the error and returns False if an issue occurs during execution.
        """
        try:
            cleaned_text = "".join(text.split())
            elements = await page.query_selector_all(f'xpath=//{selector}[contains(text(), "{cleaned_text}")]')

            if not elements:
                self.logger.info(f"Element with text '{text}' not found.")
                return False

            for element in elements:
                if "".join(await element.text_content().split()) == cleaned_text:
                    await element.click()
                    return True

        except Exception as e:
            self.logger.error(f"Error clicking element with text '{text}': {e}")
            return False

        self.logger.info(f"Element with text '{text}' not found.")
        return False

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
