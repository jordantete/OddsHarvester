import logging

from playwright.async_api import Page


class OddsHistoryExtractor:
    """Handles extraction of odds history data by hovering over bookmaker odds."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def extract_odds_history_for_bookmaker(self, page: Page, bookmaker_name: str) -> list[str]:
        """
        Hover on odds for a specific bookmaker to trigger and capture the odds history modal.

        Args:
            page (Page): Playwright page instance.
            bookmaker_name (str): Name of the bookmaker to match.

        Returns:
            List[str]: List of raw HTML content from modals triggered by hovering over matched odds blocks.
        """
        self.logger.info(f"Extracting odds history for bookmaker: {bookmaker_name}")
        await page.wait_for_timeout(2000)

        modals_data = []

        try:
            # Find all bookmaker rows
            rows = await page.query_selector_all("div.border-black-borders.flex.h-9")

            for row in rows:
                try:
                    logo_img = await row.query_selector("img.bookmaker-logo")

                    if logo_img:
                        title = await logo_img.get_attribute("title")

                        if title and bookmaker_name.lower() in title.lower():
                            self.logger.info(f"Found matching bookmaker row: {title}")
                            odds_blocks = await row.query_selector_all("div.flex-center.flex-col.font-bold")

                            for odds in odds_blocks:
                                await odds.hover()
                                await page.wait_for_timeout(2000)

                                odds_movement_element = await page.wait_for_selector(
                                    "h3:text('Odds movement')", timeout=3000
                                )
                                modal_wrapper = await odds_movement_element.evaluate_handle(
                                    "node => node.parentElement"
                                )
                                modal_element = modal_wrapper.as_element()

                                if modal_element:
                                    html = await modal_element.inner_html()
                                    modals_data.append(html)
                                else:
                                    self.logger.warning(
                                        "Unable to retrieve odds' evolution modal: modal_element is None"
                                    )

                except Exception as e:
                    self.logger.warning(f"Failed to process a bookmaker row: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to extract odds history for bookmaker {bookmaker_name}: {e}")

        return modals_data
