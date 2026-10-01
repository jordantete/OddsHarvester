"""See module docstring in core/browser/__init__.py."""

import logging
import time

from playwright.async_api import ElementHandle, Page

from oddsharvester.core.browser.waits import wait_for_signal
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import (
    MAX_SCROLL_ATTEMPTS,
    SCROLL_PAUSE_S,
    SCROLL_PAUSE_TIME_MS,
    SCROLL_TIMEOUT_S,
    SCROLL_UNTIL_CLICK_TIMEOUT_S,
)

_SCROLL_STEP_PX = 500

_CLICK_TARGET_JS = "(element, ancestor) => ancestor ? element.closest(ancestor) : element.parentElement"
# Two spans of one row share this rank, two rows never do.
_CLICK_TARGET_RANK_JS = """
(element, ancestor) => {
    const target = ancestor ? element.closest(ancestor) : element.parentElement;
    return target ? Array.from(document.querySelectorAll(ancestor || "*")).indexOf(target) : -1;
}
"""

# The rows (closest args.ancestor) of the args.selector elements whose label ends with the line's tokens, read as
# OddsPortalSelectors.line_label_matches reads them. args.want: "present" for at least one row; "open" or "closed"
# for one row whose next row holds, or does not hold, bookmaker rows.
_LINE_ROW_JS = """
(args) => {
    const rows = [];
    for (const element of document.querySelectorAll(args.selector)) {
        const label = (element.textContent || "").split(/\\s+/).filter(Boolean);
        if (!args.tokens.length || label.length < args.tokens.length) continue;
        if (label.slice(label.length - args.tokens.length).join(" ") !== args.tokens.join(" ")) continue;
        if (label.length === args.tokens.length && args.bareNumber) continue;
        const row = element.closest(args.ancestor);
        if (row && !rows.includes(row)) rows.push(row);
    }
    if (args.want === "present") return rows.length > 0;
    if (rows.length !== 1) return false;
    const next = rows[0].nextElementSibling;
    const open = !!next && next.querySelector(args.bookmakerRow) !== null;
    return args.want === "open" ? open : !open;
}
"""


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

    async def click_line_row(
        self,
        page: Page,
        selector: str,
        line: str,
        click_ancestor: str,
        timeout: int = SCROLL_UNTIL_CLICK_TIMEOUT_S,
    ) -> bool:
        """Click the one row whose label ends with `line`, once the table shows it, waiting at most `timeout` s.

        The label is that of a `selector` element and the row its closest `click_ancestor`; `line` ('-1', '+2.5')
        must be the end of the label (`OddsPortalSelectors.line_label_matches`), and the call fails when two
        different rows hold it.
        """
        args = self._line_args(selector, line, click_ancestor, "present")
        if not await wait_for_signal(page, _LINE_ROW_JS, timeout * 1000, f"row of line '{line}'", arg=args):
            return False
        clicked = await self._click_row_of_line(await page.query_selector_all(selector), line, click_ancestor)
        if clicked is None:
            self.logger.warning(f"Line '{line}' has no visible row to click.")
            return False
        return clicked

    async def wait_for_line_bookmakers(
        self,
        page: Page,
        selector: str,
        line: str,
        click_ancestor: str,
        shown: bool,
        cap_ms: int = SCROLL_PAUSE_TIME_MS,
    ) -> bool:
        """Wait, at most `cap_ms`, until the row of `line` shows its bookmaker rows (`shown`), or shows none."""
        want = "open" if shown else "closed"
        signal = f"bookmaker rows {'under' if shown else 'gone from'} line '{line}'"
        args = self._line_args(selector, line, click_ancestor, want)
        return await wait_for_signal(page, _LINE_ROW_JS, cap_ms, signal, arg=args) is not None

    @staticmethod
    def _line_args(selector: str, line: str, click_ancestor: str, want: str) -> dict:
        return {
            "selector": selector,
            "tokens": line.split(),
            "bareNumber": line.strip().isdigit(),
            "ancestor": click_ancestor,
            "bookmakerRow": OddsPortalSelectors.BOOKMAKER_ROW_WITH_NAME_CSS,
            "want": want,
        }

    async def _click_row_of_line(
        self, elements: list[ElementHandle], line: str, click_ancestor: str | None
    ) -> bool | None:
        """Click the one row whose visible label ends with `line`.

        Returns True once clicked, False when several rows match (the line cannot
        be told apart), None when no row matches yet.
        """
        rows: dict[int, ElementHandle] = {}
        for element in elements:
            label = await element.text_content()
            if not label or not OddsPortalSelectors.line_label_matches(label, line):
                continue
            if not await element.bounding_box():
                continue
            rows.setdefault(await element.evaluate(_CLICK_TARGET_RANK_JS, click_ancestor), element)

        if len(rows) > 1:
            self.logger.warning(f"Line '{line}' matches {len(rows)} different rows; refusing to pick one.")
            return False
        if not rows:
            return None

        element = next(iter(rows.values()))
        self.logger.info(f"Line '{line}' is visible. Clicking its row.")
        target = await element.evaluate_handle(_CLICK_TARGET_JS, click_ancestor)
        await target.click()
        return True
