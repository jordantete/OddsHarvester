import logging
import time

from playwright.async_api import ElementHandle, Page, Response
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from oddsharvester.core.browser.waits import wait_for_signal
from oddsharvester.core.market_extraction.bookmaker_name import bookmaker_match_key, resolve_bookmaker_name
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import (
    ODDS_HISTORY_HOVER_WAIT_MS,
    ODDS_MOVEMENT_SELECTOR_TIMEOUT_MS,
)

# An expanded submarket row wraps a nested bookmaker table: only leaf rows are bookmaker rows (same rule as OddsParser).
LEAF_BOOKMAKER_ROW_CSS = f"{OddsPortalSelectors.BOOKMAKER_ROW_WITH_NAME_CSS}:not(:has(tr))"

# The tooltip renders its header over a spinner first, then its history once the request answered.
SETTLED_TOOLTIP_JS = """
(header) => {
    const tooltip = document.querySelector(header)?.parentElement;
    return tooltip && !tooltip.querySelector(".animate-spin") ? tooltip.innerHTML : null;
}
"""


def is_history_response(response: Response) -> bool:
    """The odds-movement request a hover fires: /proxy/match-event-history/<event>-<bookmaker>/."""
    return "/match-event-history/" in response.url


class OddsHistoryExtractor:
    """Handles extraction of odds history data by hovering over bookmaker odds."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def extract_odds_history_for_bookmaker(
        self, page: Page, bookmaker_name: str, cell_count: int
    ) -> list[str | None]:
        """
        Hover each outcome cell of a bookmaker's row and capture the odds-history modal it opens.

        Args:
            page (Page): Playwright page instance.
            bookmaker_name (str): Name as resolved by OddsParser; matched exactly, ignoring case and whitespace.
            cell_count (int): Number of outcome cells to hover.

        Returns:
            list[str | None]: One item per outcome, in order: the modal HTML, or None when it could not be read.
        """
        self.logger.info(f"Extracting odds history for bookmaker: {bookmaker_name}")
        modals: list[str | None] = [None] * cell_count
        row = await self._find_row(page, bookmaker_name)
        if row is None:
            self.logger.warning(f"No odds row found for bookmaker {bookmaker_name}; its history stays empty.")
            return modals

        try:
            cells = (await row.query_selector_all(OddsPortalSelectors.ODD_CELL_CSS))[:cell_count]
        except Exception as e:
            self.logger.warning(f"Failed to read odds cells for bookmaker {bookmaker_name}: {e}")
            return modals

        for index, cell in enumerate(cells):
            modals[index] = await self._hover_modal(page, cell, bookmaker_name, index)
        return modals

    async def _find_row(self, page: Page, bookmaker_name: str) -> ElementHandle | None:
        target = bookmaker_match_key(bookmaker_name)
        try:
            rows = await page.query_selector_all(LEAF_BOOKMAKER_ROW_CSS)
        except Exception as e:
            self.logger.warning(f"Failed to list bookmaker rows: {e}")
            return None

        matches = []
        for row in rows:
            try:
                name = await self._row_bookmaker_name(row)
            except Exception as e:
                self.logger.warning(f"Failed to read a bookmaker row name: {e}")
                continue
            if name and bookmaker_match_key(name) == target:
                matches.append(row)

        if len(matches) > 1:
            self.logger.warning(f"{len(matches)} rows are named {bookmaker_name}; using the first one.")
        return matches[0] if matches else None

    async def _hover_modal(self, page: Page, cell: ElementHandle, bookmaker_name: str, index: int) -> str | None:
        try:
            settled = await self._hover_until_settled(page, cell)
            if settled is not None:
                return settled
            header = await page.wait_for_selector(
                OddsPortalSelectors.ODDS_MOVEMENT_HEADER, timeout=ODDS_MOVEMENT_SELECTOR_TIMEOUT_MS
            )
            wrapper = await header.evaluate_handle("node => node.parentElement")
            modal = wrapper.as_element()
            if modal is None:
                self.logger.warning(f"Odds-history modal missing for {bookmaker_name}, outcome {index}.")
                return None
            return await modal.inner_html()
        except Exception as e:
            self.logger.warning(f"Failed to read odds history for {bookmaker_name}, outcome {index}: {e}")
            return None

    async def _hover_until_settled(self, page: Page, cell: ElementHandle) -> str | None:
        """Hover the cell; the tooltip HTML once its history request answered and its spinner went, else None.

        The response and the tooltip share one cap, ODDS_HISTORY_HOVER_WAIT_MS.
        """
        started = time.monotonic()
        try:
            async with page.expect_response(is_history_response, timeout=ODDS_HISTORY_HOVER_WAIT_MS):
                await cell.hover()
        except PlaywrightTimeoutError:
            self.logger.warning(
                f"No odds-history response within {ODDS_HISTORY_HOVER_WAIT_MS} ms of the hover; "
                "carrying on with the page as it is."
            )
            return None
        left_ms = ODDS_HISTORY_HOVER_WAIT_MS - int((time.monotonic() - started) * 1000)
        handle = await wait_for_signal(
            page,
            SETTLED_TOOLTIP_JS,
            max(left_ms, 1),
            "settled odds-history tooltip",
            arg=OddsPortalSelectors.ODDS_MOVEMENT_HEADER,
        )
        return None if handle is None else await handle.json_value()

    @staticmethod
    async def _row_bookmaker_name(row: ElementHandle) -> str | None:
        """Bookmaker name of an odds row, resolved the way OddsParser does."""
        name_el = await row.query_selector(f"{OddsPortalSelectors.BOOKMAKER_LINK_CSS} p")
        titled = await row.query_selector("a[title]")
        link = await row.query_selector(OddsPortalSelectors.BOOKMAKER_LINK_CSS)
        return resolve_bookmaker_name(
            (await name_el.text_content()) if name_el else None,
            (await titled.get_attribute("title")) if titled else None,
            (await link.get_attribute("href")) if link else None,
        )
