from unittest.mock import AsyncMock, MagicMock

import pytest

from oddsharvester.core.browser.pagination import PaginationWalker, WalkVerdict
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors


@pytest.fixture
def walker():
    return PaginationWalker()


class TestIsFullPage:
    """A full page of links is the signal that more pages exist."""

    @pytest.mark.parametrize(("link_count", "expected"), [(0, False), (49, False), (50, True), (51, True)])
    def test_boundary(self, walker, link_count, expected):
        assert walker.is_full_page(link_count) is expected


class TestDecideInsideFloor:
    """Below the frontier the widget has promised a later page exists, so this one must be full.

    Regression guard: a short page inside the floor must be reported, not silently
    collected, and it must never end the walk either.
    """

    def test_short_page_fails(self, walker):
        """A page that is not the last one has lost rows if it is not full (issue #78)."""
        verdict = walker.decide(requested_page=1, link_count=2, frontier=3, observed_max=None, scroll_ok=True)
        assert verdict is WalkVerdict.PAGE_FAILED

    def test_short_page_with_failed_scroll_fails(self, walker):
        """scroll_ok is not the discriminator: a stalled lazy-load still reports success."""
        verdict = walker.decide(requested_page=1, link_count=2, frontier=3, observed_max=None, scroll_ok=False)
        assert verdict is WalkVerdict.PAGE_FAILED

    def test_full_page_continues(self, walker):
        verdict = walker.decide(requested_page=1, link_count=50, frontier=8, observed_max=8, scroll_ok=True)
        assert verdict is WalkVerdict.CONTINUE

    def test_empty_page_fails(self, walker):
        verdict = walker.decide(requested_page=5, link_count=0, frontier=8, observed_max=8, scroll_ok=True)
        assert verdict is WalkVerdict.PAGE_FAILED

    def test_empty_page_below_frontier_with_scroll_ok_still_fails(self, walker):
        """scroll_ok must not leak into the empty-page branches: below the frontier an empty
        page is anomalous no matter how the scroll went."""
        verdict = walker.decide(requested_page=2, link_count=0, frontier=5, observed_max=None, scroll_ok=True)
        assert verdict is WalkVerdict.PAGE_FAILED


class TestDecidePastFloor:
    """At or beyond the frontier the walk is exploring, so fullness governs."""

    def test_full_page_continues(self, walker):
        verdict = walker.decide(requested_page=1, link_count=50, frontier=1, observed_max=None, scroll_ok=True)
        assert verdict is WalkVerdict.CONTINUE

    def test_full_page_continues_even_with_failed_scroll(self, walker):
        """A full page still implies more pages exist regardless of scroll completeness."""
        verdict = walker.decide(requested_page=1, link_count=50, frontier=1, observed_max=None, scroll_ok=False)
        assert verdict is WalkVerdict.CONTINUE

    def test_short_page_stops_complete(self, walker):
        verdict = walker.decide(requested_page=8, link_count=30, frontier=8, observed_max=8, scroll_ok=True)
        assert verdict is WalkVerdict.STOP_COMPLETE

    def test_short_page_with_failed_scroll_fails(self, walker):
        """Issue 79: a short page from a truncated scroll must not be read as a genuine last page."""
        verdict = walker.decide(requested_page=8, link_count=30, frontier=8, observed_max=8, scroll_ok=False)
        assert verdict is WalkVerdict.PAGE_FAILED

    def test_empty_page_past_widget_max_stops_complete(self, walker):
        """Page 9 of an 8-page season renders zero rows but still shows a widget saying 8."""
        verdict = walker.decide(requested_page=9, link_count=0, frontier=8, observed_max=8, scroll_ok=True)
        assert verdict is WalkVerdict.STOP_COMPLETE

    def test_empty_page_within_widget_max_fails(self, walker):
        verdict = walker.decide(requested_page=8, link_count=0, frontier=8, observed_max=8, scroll_ok=True)
        assert verdict is WalkVerdict.PAGE_FAILED

    def test_empty_page_within_frontier_despite_lower_observed_max_fails(self, walker):
        """A mid-walk partial widget read must not shrink the protected range: frontier
        stays at the planned 8 even though this read only saw up to 3."""
        verdict = walker.decide(requested_page=8, link_count=0, frontier=8, observed_max=3, scroll_ok=True)
        assert verdict is WalkVerdict.PAGE_FAILED

    def test_empty_first_page_without_widget_stops_complete(self, walker):
        """Gotcha 15: a dead league/season pair answers 200 with an empty first page."""
        verdict = walker.decide(requested_page=1, link_count=0, frontier=1, observed_max=None, scroll_ok=True)
        assert verdict is WalkVerdict.STOP_COMPLETE

    def test_empty_later_page_without_widget_fails(self, walker):
        verdict = walker.decide(requested_page=2, link_count=0, frontier=2, observed_max=None, scroll_ok=True)
        assert verdict is WalkVerdict.PAGE_FAILED


def _link(text):
    link = MagicMock()
    # text_content, not inner_text: the widget's parent can be display:none
    # until the listing is scrolled to the bottom (2026-08 redesign).
    link.text_content = AsyncMock(return_value=text)
    return link


def _page_with(texts):
    page = MagicMock()

    async def query(selector):
        assert selector == OddsPortalSelectors.PAGINATION_ITEM
        return [_link(t) for t in texts]

    page.query_selector_all = AsyncMock(side_effect=query)
    return page


class TestReadWidget:
    """The widget renders digit buttons/spans plus localized Prev/Next items."""

    @pytest.mark.asyncio
    async def test_keeps_digits_and_drops_navigation_labels(self, walker):
        page = _page_with(["1", "2", "3", "4", "5", "6", "7", "8", "Next"])
        assert await walker.read_widget(page=page) == [1, 2, 3, 4, 5, 6, 7, 8]

    @pytest.mark.asyncio
    async def test_drops_prev_label(self, walker):
        page = _page_with(["Prev", "1", "2", "3", "4", "5", "6", "7", "8"])
        assert await walker.read_widget(page=page) == [1, 2, 3, 4, 5, 6, 7, 8]

    @pytest.mark.asyncio
    async def test_absent_widget_returns_empty(self, walker):
        page = _page_with([])
        assert await walker.read_widget(page=page) == []

    @pytest.mark.asyncio
    async def test_ellipsis_range_keeps_endpoints(self, walker):
        """Gotcha 2a: long ranges collapse to endpoints, gap filling happens downstream."""
        page = _page_with(["1", "2", "3", "27", "Next"])
        assert await walker.read_widget(page=page) == [1, 2, 3, 27]

    @pytest.mark.asyncio
    async def test_query_failure_returns_empty(self, walker):
        page = MagicMock()
        page.query_selector_all = AsyncMock(side_effect=RuntimeError("detached"))
        assert await walker.read_widget(page=page) == []
