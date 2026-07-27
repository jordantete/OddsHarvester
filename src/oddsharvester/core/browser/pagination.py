"""See module docstring in core/browser/__init__.py."""

from enum import Enum, auto
import logging

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
    ) -> WalkVerdict:
        """Verdict for a page that was just collected.

        Below the frontier the widget promised the page exists, so only an empty
        page is anomalous. At or beyond it the walk is exploring, so a page that
        is not full ends the season. See gotchas 15 and 17.
        """
        if requested_page < frontier:
            return WalkVerdict.PAGE_FAILED if link_count == 0 else WalkVerdict.CONTINUE

        if link_count == 0:
            if observed_max is not None:
                return WalkVerdict.STOP_COMPLETE if requested_page > observed_max else WalkVerdict.PAGE_FAILED
            return WalkVerdict.STOP_COMPLETE if requested_page == 1 else WalkVerdict.PAGE_FAILED

        return WalkVerdict.CONTINUE if self.is_full_page(link_count) else WalkVerdict.STOP_COMPLETE
