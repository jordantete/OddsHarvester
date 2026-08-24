"""See module docstring in core/browser/__init__.py."""

import logging
import time

from playwright.async_api import Page

from oddsharvester.utils.constants import (
    MAX_SCROLL_ATTEMPTS,
    SCROLL_PAUSE_S,
    SCROLL_TIMEOUT_S,
    SCROLL_UNTIL_CLICK_PAUSE_S,
    SCROLL_UNTIL_CLICK_TIMEOUT_S,
)

_SCROLL_STEP_PX = 500


class PageScroller:
    """Incremental page scrolling and scroll-to-element-and-click."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def scroll_until_loaded(
        self,
        page: Page,
        timeout: int = SCROLL_TIMEOUT_S,
        scroll_pause_time: int = SCROLL_PAUSE_S,
        max_scroll_attempts: int = MAX_SCROLL_ATTEMPTS,
        content_check_selector: str | None = None,
    ) -> bool:
        """Scroll the page until no new content loads or timeout is reached.

        Returns True if the page stabilized (height or element count), False on timeout.
        """
        self.logger.info("Will scroll to the bottom of the page to load all content.")
        end_time = time.time() + timeout
        last_height = await page.evaluate("document.body.scrollHeight")
        last_element_count = 0
        stable_count_attempts = 0

        if content_check_selector:
            initial_elements = await page.query_selector_all(content_check_selector)
            last_element_count = len(initial_elements)
            self.logger.info(f"Initial element count: {last_element_count}")

        self.logger.info(f"Initial page height: {last_height}")

        current_scroll_pos = 0

        while time.time() < end_time:
            page_height = await page.evaluate("document.body.scrollHeight")
            if current_scroll_pos < page_height:
                current_scroll_pos = min(current_scroll_pos + _SCROLL_STEP_PX, page_height)
                await page.evaluate(f"window.scrollTo(0, {current_scroll_pos})")
            else:
                await page.evaluate(f"window.scrollTo(0, {page_height})")
            await page.wait_for_timeout(scroll_pause_time * 1000)

            new_height = await page.evaluate("document.body.scrollHeight")

            if content_check_selector:
                elements = await page.query_selector_all(content_check_selector)
                new_element_count = len(elements)
                self.logger.info(f"Current element count: {new_element_count} (height: {new_height})")

                if new_element_count == last_element_count and new_height == last_height:
                    stable_count_attempts += 1
                    self.logger.debug(f"Content stable. Attempt {stable_count_attempts}/{max_scroll_attempts}.")
                    if stable_count_attempts >= max_scroll_attempts:
                        self.logger.info(f"Content stabilized at {new_element_count} elements. Scrolling complete.")
                        return True
                else:
                    stable_count_attempts = 0
                    last_element_count = new_element_count
            else:
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
        self,
        page: Page,
        selector: str,
        text: str | None = None,
        timeout: int = SCROLL_UNTIL_CLICK_TIMEOUT_S,
        scroll_pause_time: int = SCROLL_UNTIL_CLICK_PAUSE_S,
        click_ancestor: str | None = None,
    ) -> bool:
        """Scroll until an element matching selector (and optional text) is visible, then click its parent.

        When `click_ancestor` is given, the closest ancestor matching that
        selector is clicked instead of the direct parent (e.g. the enclosing
        <tr> of a submarket label span).
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
                            parent_element = await element.evaluate_handle(
                                "(element, ancestor) => ancestor ? element.closest(ancestor) : element.parentElement",
                                click_ancestor,
                            )
                            await parent_element.click()
                            return True
                else:
                    bounding_box = await element.bounding_box()
                    if bounding_box:
                        self.logger.info("Element is visible. Clicking its parent.")
                        parent_element = await element.evaluate_handle(
                            "(element, ancestor) => ancestor ? element.closest(ancestor) : element.parentElement",
                            click_ancestor,
                        )
                        await parent_element.click()
                        return True

            await page.evaluate("window.scrollBy(0, 500);")
            await page.wait_for_timeout(scroll_pause_time * 1000)

        self.logger.warning(
            f"Failed to find and click parent of element matching selector '{selector}' with text '{text}' "
            f"within timeout."
        )
        return False
