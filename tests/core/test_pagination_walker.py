import pytest

from oddsharvester.core.browser.pagination import PaginationWalker, WalkVerdict


@pytest.fixture
def walker():
    return PaginationWalker()


class TestIsFullPage:
    """A full page of links is the signal that more pages exist."""

    @pytest.mark.parametrize(("link_count", "expected"), [(0, False), (49, False), (50, True), (51, True)])
    def test_boundary(self, walker, link_count, expected):
        assert walker.is_full_page(link_count) is expected


class TestDecideInsideFloor:
    """Below the frontier the widget has promised the page exists, so fullness never stops the walk.

    Regression guard: a short page inside the floor must not end collection, or the
    gotcha 17 protection (empty pages inside the plan are failures) silently disappears.
    """

    def test_short_page_continues(self, walker):
        verdict = walker.decide(requested_page=1, link_count=2, frontier=3, observed_max=None)
        assert verdict is WalkVerdict.CONTINUE

    def test_full_page_continues(self, walker):
        verdict = walker.decide(requested_page=1, link_count=50, frontier=8, observed_max=8)
        assert verdict is WalkVerdict.CONTINUE

    def test_empty_page_fails(self, walker):
        verdict = walker.decide(requested_page=5, link_count=0, frontier=8, observed_max=8)
        assert verdict is WalkVerdict.PAGE_FAILED


class TestDecidePastFloor:
    """At or beyond the frontier the walk is exploring, so fullness governs."""

    def test_full_page_continues(self, walker):
        verdict = walker.decide(requested_page=1, link_count=50, frontier=1, observed_max=None)
        assert verdict is WalkVerdict.CONTINUE

    def test_short_page_stops_complete(self, walker):
        verdict = walker.decide(requested_page=8, link_count=30, frontier=8, observed_max=8)
        assert verdict is WalkVerdict.STOP_COMPLETE

    def test_empty_page_past_widget_max_stops_complete(self, walker):
        """Page 9 of an 8-page season renders zero rows but still shows a widget saying 8."""
        verdict = walker.decide(requested_page=9, link_count=0, frontier=8, observed_max=8)
        assert verdict is WalkVerdict.STOP_COMPLETE

    def test_empty_page_within_widget_max_fails(self, walker):
        verdict = walker.decide(requested_page=8, link_count=0, frontier=8, observed_max=8)
        assert verdict is WalkVerdict.PAGE_FAILED

    def test_empty_first_page_without_widget_stops_complete(self, walker):
        """Gotcha 15: a dead league/season pair answers 200 with an empty first page."""
        verdict = walker.decide(requested_page=1, link_count=0, frontier=1, observed_max=None)
        assert verdict is WalkVerdict.STOP_COMPLETE

    def test_empty_later_page_without_widget_fails(self, walker):
        verdict = walker.decide(requested_page=2, link_count=0, frontier=2, observed_max=None)
        assert verdict is WalkVerdict.PAGE_FAILED
