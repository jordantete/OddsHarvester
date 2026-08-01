"""See module docstring in core/browser/__init__.py."""

from enum import Enum, auto
import logging

from playwright.async_api import Page

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import RESULTS_PAGE_SIZE


class WalkVerdict(Enum):
    """What the collection loop should do after fetching a listing page."""

    CONTINUE = auto()
    STOP_COMPLETE = auto()
    PAGE_FAILED = auto()


class PaginationWalker:
    """Decides how far a listing walk goes when the pagination widget cannot be trusted."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def read_widget(self, page: Page) -> list[int]:
        """Page numbers rendered by the pagination widget, empty when absent or unreadable."""
        try:
            links = await page.query_selector_all(OddsPortalSelectors.PAGINATION_LINK)
        except Exception as e:
            self.logger.warning(f"Could not query the pagination widget: {e}")
            return []

        pages: set[int] = set()
        for link in links:
            try:
                text = (await link.inner_text()).strip()
            except Exception as e:
                self.logger.warning(f"Could not read a pagination link: {e}")
                continue
            if text.isdigit():
                pages.add(int(text))
        return sorted(pages)

    @staticmethod
    def is_full_page(link_count: int) -> bool:
        """A full page implies more pages exist."""
        return link_count >= RESULTS_PAGE_SIZE

    def decide(
        self,
        requested_page: int,
        link_count: int,
        frontier: int,
        observed_max: int | None,
        scroll_ok: bool,
    ) -> WalkVerdict:
        """Verdict for a page that was just collected.

        Below the frontier the widget promised a later page exists, so this one is
        not the last and must come back full: anything short of a full page lost
        rows, whether it rendered none or five (issue #78). At or beyond the
        frontier the walk is exploring, so a page that is not full ends the season,
        unless its scroll did not complete: a short page from a truncated scroll
        must not be read as a genuine last page, or the season ends looking
        complete with zero failures reported (issue #79). `scroll_ok` only affects
        that short-page case; below the frontier fullness alone decides, since a
        stalled lazy-load stabilizes at a partial count and still reports success.
        See gotchas 15 and 17.
        """
        if requested_page < frontier:
            return WalkVerdict.CONTINUE if self.is_full_page(link_count) else WalkVerdict.PAGE_FAILED

        if link_count == 0:
            if observed_max is not None:
                return WalkVerdict.STOP_COMPLETE if requested_page > frontier else WalkVerdict.PAGE_FAILED
            return WalkVerdict.STOP_COMPLETE if requested_page == 1 else WalkVerdict.PAGE_FAILED

        if self.is_full_page(link_count):
            return WalkVerdict.CONTINUE

        return WalkVerdict.STOP_COMPLETE if scroll_ok else WalkVerdict.PAGE_FAILED
