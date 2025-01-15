import time, logging
from playwright.async_api import Page, TimeoutError

class BrowserHelper:
    def __init__(self, page: Page):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.page = page
    
    async def scroll_until_loaded(self, timeout=60, scroll_pause_time=10, max_scrolls=15):
        """Scrolls down the page in a loop until no new content is loaded or a timeout is reached."""
        self.logger.info("Will scroll to the bottom of the page.")
        end_time = time.time() + timeout
        last_height = await self.page.evaluate("document.body.scrollHeight")
        self.logger.info(f"__scroll_until_loaded last_height: {last_height}")

        scroll_attempts = 0
        while True:
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(scroll_pause_time * 1000)  # Convert seconds to milliseconds
            new_height = await self.page.evaluate("document.body.scrollHeight")
            self.logger.info(f"__scroll_until_loaded new_height: {new_height}")

            if new_height == last_height:
                scroll_attempts += 1
                if scroll_attempts > 2:
                    self.logger.info("No more new content detected.")
                    break
            else:
                scroll_attempts = 0

            last_height = new_height

            if time.time() > end_time or scroll_attempts > max_scrolls:
                self.logger.info("Reached the end of the scrolling time or maximum scroll attempts.")
                break

    async def __click_by_inner_text(self, selector: str, text: str) -> bool:
        """ This method attempts to click an element based on its text content."""
        try:
            cleaned_text = ''.join(text.split())
            elements = await self.page.query_selector_all(f'xpath=//{selector}[contains(text(), "{cleaned_text}")]')

            if not elements:
                self.logger.info(f"Element with text '{text}' not found.")
                return False

            for element in elements:
                if ''.join(await element.text_content().split()) == cleaned_text:
                    await element.click()
                    return True

        except Exception as e:
            self.logger.error(f"Error clicking element with text '{text}': {e}")
            return False
        
        self.logger.info(f"Element with text '{text}' not found.")
        return False

    async def click_by_text(self, selector: str, text: str) -> bool:
        try:
            elements = await self.page.query_selector_all(selector)
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

    async def wait_and_query(self, selector: str, timeout: int = 5000):
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return await self.page.query_selector_all(selector)
        
        except TimeoutError:
            self.logger.error(f"Timeout waiting for selector: {selector}")
            return []