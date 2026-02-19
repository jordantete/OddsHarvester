import logging

from playwright.async_api import Page

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import (
    ODDS_HISTORY_HOVER_WAIT_MS,
    ODDS_HISTORY_PRE_WAIT_MS,
    ODDS_MOVEMENT_SELECTOR_TIMEOUT_MS,
)


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
        await page.wait_for_timeout(ODDS_HISTORY_PRE_WAIT_MS)

        modals_data = []

        try:
            # Find all bookmaker rows
            rows = await page.query_selector_all(OddsPortalSelectors.BOOKMAKER_ROW_CSS)

            for row in rows:
                try:
                    logo_img = await row.query_selector(OddsPortalSelectors.BOOKMAKER_LOGO_CSS)

                    if logo_img:
                        title = await logo_img.get_attribute("title")

                        if title and bookmaker_name.lower() in title.lower():
                            self.logger.info(f"Found matching bookmaker row: {title}")
                            odds_blocks = await row.query_selector_all(OddsPortalSelectors.ODDS_BLOCK_CSS)

                            for odds in odds_blocks:
                                await odds.hover()
                                await page.wait_for_timeout(ODDS_HISTORY_HOVER_WAIT_MS)

                                odds_movement_element = await page.wait_for_selector(
                                    OddsPortalSelectors.ODDS_MOVEMENT_HEADER, timeout=ODDS_MOVEMENT_SELECTOR_TIMEOUT_MS
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
