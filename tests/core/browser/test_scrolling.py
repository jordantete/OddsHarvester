import logging
from unittest.mock import AsyncMock, MagicMock

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import pytest

from oddsharvester.core.browser.scrolling import _LINE_ROW_JS, PageScroller
from oddsharvester.core.browser.waits import SIGNAL_POLL_MS
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import SCROLL_PAUSE_TIME_MS, SCROLL_UNTIL_CLICK_TIMEOUT_S

# Asian Handicap line spans of Arsenal - Leeds on www.oddsportal.com (2026-09-29), in DOM order.
# Each line row holds five spans: both labels, the full label, the short label (hidden on
# desktop), the bookmaker count and the payout.
ARSENAL_LEEDS_AH_ROWS = [
    ["Asian Handicap -4.5AH -4.5", "Asian Handicap -4.5", "AH -4.5", "0", "-"],
    ["Asian Handicap -4.25AH -4.25", "Asian Handicap -4.25", "AH -4.25", "0", "-"],
    ["Asian Handicap -4AH -4", "Asian Handicap -4", "AH -4", "0", "-"],
    ["Asian Handicap -3.75AH -3.75", "Asian Handicap -3.75", "AH -3.75", "0", "-"],
    ["Asian Handicap -3.5AH -3.5", "Asian Handicap -3.5", "AH -3.5", "0", "-"],
    ["Asian Handicap -3.25AH -3.25", "Asian Handicap -3.25", "AH -3.25", "0", "-"],
    ["Asian Handicap -3AH -3", "Asian Handicap -3", "AH -3", "0", "-"],
    ["Asian Handicap -2.75AH -2.75", "Asian Handicap -2.75", "AH -2.75", "0", "-"],
    ["Asian Handicap -2.5AH -2.5", "Asian Handicap -2.5", "AH -2.5", "0", "-"],
    ["Asian Handicap -2.25AH -2.25", "Asian Handicap -2.25", "AH -2.25", "0", "-"],
    ["Asian Handicap -2AH -2", "Asian Handicap -2", "AH -2", "0", "-"],
    ["Asian Handicap -1.75AH -1.75", "Asian Handicap -1.75", "AH -1.75", "0", "-"],
    ["Asian Handicap -1.5AH -1.5", "Asian Handicap -1.5", "AH -1.5", "0", "-"],
    ["Asian Handicap -1.25AH -1.25", "Asian Handicap -1.25", "AH -1.25", "0", "-"],
    ["Asian Handicap -1AH -1", "Asian Handicap -1", "AH -1", "0", "-"],
    ["Asian Handicap -0.75AH -0.75", "Asian Handicap -0.75", "AH -0.75", "0", "-"],
    ["Asian Handicap -0.5AH -0.5", "Asian Handicap -0.5", "AH -0.5", "0", "-"],
    ["Asian Handicap -0.25AH -0.25", "Asian Handicap -0.25", "AH -0.25", "0", "-"],
    ["Asian Handicap 0AH 0", "Asian Handicap 0", "AH 0", "0", "-"],
    ["Asian Handicap +0.25AH +0.25", "Asian Handicap +0.25", "AH +0.25", "0", "-"],
    ["Asian Handicap +0.5AH +0.5", "Asian Handicap +0.5", "AH +0.5", "0", "-"],
    ["Asian Handicap +0.75AH +0.75", "Asian Handicap +0.75", "AH +0.75", "0", "-"],
]

# Gea - Machac, ATP Beijing (2026-09-29): a sets row and a games row both read '+1.5'.
GEA_MACHAC_AH_ROWS = [
    ["Asian Handicap -1.5AH -1.5", "Asian Handicap -1.5", "AH -1.5", "0", "-"],
    ["Asian Handicap -0.5AH -0.5", "Asian Handicap -0.5", "AH -0.5", "0", "-"],
    ["Asian Handicap +0.5AH +0.5", "Asian Handicap +0.5", "AH +0.5", "0", "-"],
    ["Asian Handicap +1AH +1", "Asian Handicap +1", "AH +1", "0", "-"],
    ["Asian Handicap +1.5AH +1.5", "Asian Handicap +1.5", "AH +1.5", "0", "-"],
    ["Asian Handicap +1.5AH +1.5", "Asian Handicap +1.5", "AH +1.5", "0", "-"],
    ["Asian Handicap +2AH +2", "Asian Handicap +2", "AH +2", "0", "-"],
    ["Asian Handicap +2.5AH +2.5", "Asian Handicap +2.5", "AH +2.5", "0", "-"],
    ["Asian Handicap +3AH +3", "Asian Handicap +3", "AH +3", "0", "-"],
    ["Asian Handicap +3.5AH +3.5", "Asian Handicap +3.5", "AH +3.5", "0", "-"],
]


def _line_page(rows):
    """A page rendering `rows` of submarket spans, and one clickable <tr> mock per row."""
    trs = [MagicMock(click=AsyncMock()) for _ in rows]
    spans = []
    for rank, row in enumerate(rows):
        for position, text in enumerate(row):
            span = MagicMock()
            span.text_content = AsyncMock(return_value=text)
            box = None if position == 2 else {"x": 0, "y": 40 * rank, "width": 120, "height": 20}
            span.bounding_box = AsyncMock(return_value=box)
            span.evaluate = AsyncMock(return_value=rank)
            span.evaluate_handle = AsyncMock(return_value=trs[rank])
            spans.append(span)
    page = MagicMock()
    page.query_selector_all = AsyncMock(return_value=spans)
    page.evaluate = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.wait_for_function = AsyncMock(return_value=MagicMock())
    return page, trs


def _rank_of(rows, line):
    return next(rank for rank, row in enumerate(rows) if row[1].split()[-1] == line)


async def _click_line(page, line, timeout=1):
    return await PageScroller().click_line_row(
        page,
        OddsPortalSelectors.SUB_MARKET_SELECTOR,
        line,
        OddsPortalSelectors.SUB_MARKET_CLICK_ANCESTOR,
        timeout=timeout,
    )


def _line_args(line, want):
    return {
        "selector": OddsPortalSelectors.SUB_MARKET_SELECTOR,
        "tokens": line.split(),
        "bareNumber": line.strip().isdigit(),
        "ancestor": OddsPortalSelectors.SUB_MARKET_CLICK_ANCESTOR,
        "bookmakerRow": OddsPortalSelectors.BOOKMAKER_ROW_WITH_NAME_CSS,
        "want": want,
    }


class TestPageScroller:
    @pytest.fixture
    def scroller(self):
        return PageScroller()

    async def test_scroll_until_loaded_success_with_selector(self, scroller, mock_page):
        """Test successful scrolling with content selector."""
        # Mock page evaluation and element counting
        mock_page.evaluate.return_value = 1000  # Same height for all calls
        mock_page.query_selector_all.return_value = [AsyncMock()] * 5  # 5 elements
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(
            mock_page, timeout=1, scroll_pause_time=0.1, max_scroll_attempts=2, content_check_selector=".test-element"
        )
        assert result is True

    async def test_scroll_until_loaded_success_height_based(self, scroller, mock_page):
        """Test successful scrolling with height-based detection."""
        # Mock page evaluation with changing height then stable
        mock_page.evaluate.return_value = 1200  # Stable height
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(mock_page, timeout=1, scroll_pause_time=0.1, max_scroll_attempts=2)
        assert result is True

    async def test_scroll_until_loaded_timeout(self, scroller, mock_page):
        """Test scrolling that times out."""
        # Mock page evaluation with changing height (never stabilizes)
        mock_page.evaluate.return_value = 1000  # Stable height but short timeout

        # Mock a longer wait time to ensure timeout is reached
        async def slow_wait(*args, **kwargs):
            import asyncio

            await asyncio.sleep(0.1)  # Simulate slow operation

        mock_page.wait_for_timeout = slow_wait

        result = await scroller.scroll_until_loaded(
            mock_page,
            timeout=0.01,  # Short timeout
            scroll_pause_time=0.1,
        )
        assert result is False

    async def test_scroll_until_loaded_with_changing_content(self, scroller, mock_page):
        """Test scrolling with content that keeps changing."""
        # Mock page evaluation and changing element count
        mock_page.evaluate.return_value = 1000  # Same height
        mock_page.query_selector_all.return_value = [AsyncMock()] * 7  # 7 elements (stable)
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(
            mock_page, timeout=1, scroll_pause_time=0.1, max_scroll_attempts=2, content_check_selector=".test-element"
        )
        assert result is True

    async def test_scroll_until_loaded_zero_timeout(self, scroller, mock_page):
        """Test scrolling with zero timeout."""
        mock_page.evaluate.return_value = 1000
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(mock_page, timeout=0)
        assert result is False

    async def test_scroll_until_loaded_negative_timeout(self, scroller, mock_page):
        """Test scrolling with negative timeout."""
        mock_page.evaluate.return_value = 1000
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(mock_page, timeout=-1)
        assert result is False

    async def test_logging_during_scrolling(self, scroller, mock_page, caplog):
        """Test logging during scrolling operations."""
        with caplog.at_level(logging.INFO):
            mock_page.evaluate.return_value = 1000
            mock_page.wait_for_timeout = AsyncMock()

            await scroller.scroll_until_loaded(mock_page, timeout=0.1)

            assert "Will scroll to the bottom of the page" in caplog.text
            # The test might complete before timeout, so check for either completion or timeout
            assert any(msg in caplog.text for msg in ["Page height stabilized", "Reached scrolling timeout"])

    async def test_full_scrolling_flow(self, scroller, mock_page):
        """Test the complete scrolling flow."""
        # Mock successful scrolling
        mock_page.evaluate.return_value = 1000  # Stable height
        mock_page.wait_for_timeout = AsyncMock()

        result = await scroller.scroll_until_loaded(mock_page, timeout=1, scroll_pause_time=0.1, max_scroll_attempts=2)
        assert result is True


def test_listing_scroll_pace_matches_what_the_listings_always_used():
    """E1: the three listings passed 2 s / 3 attempts in-line; the constants now carry those values."""
    from oddsharvester.utils.constants import MAX_SCROLL_ATTEMPTS, SCROLL_PAUSE_S

    assert (SCROLL_PAUSE_S, MAX_SCROLL_ATTEMPTS) == (2, 3)


@pytest.mark.parametrize("line", ["-1", "-1.75", "-2", "-4", "-4.5", "0", "+0.75"])
async def test_exact_tail_clicks_the_row_of_that_line(line):
    """A3: lines render in ascending order, so a substring match on '-1' opened '-1.75'."""
    page, trs = _line_page(ARSENAL_LEEDS_AH_ROWS)

    assert await _click_line(page, line) is True

    target = _rank_of(ARSENAL_LEEDS_AH_ROWS, line)
    assert [tr.click.await_count for tr in trs] == [int(rank == target) for rank in range(len(trs))]


@pytest.mark.parametrize("line", ["-1", "-2", "0"])
async def test_exact_tail_clicks_nothing_when_the_line_is_missing(line):
    """'-1' must not open '-1.75', nor '0' a row whose bookmaker count reads '0'."""
    rows = [row for row in ARSENAL_LEEDS_AH_ROWS if row[1] != f"Asian Handicap {line}"]
    page, trs = _line_page(rows)

    assert await _click_line(page, line, timeout=0.1) is False

    assert not any(tr.click.await_count for tr in trs)


async def test_exact_tail_finds_the_line_on_a_localized_mirror():
    rows = [[text.replace("Asian Handicap", "Hándicap asiático") for text in row] for row in ARSENAL_LEEDS_AH_ROWS]
    page, trs = _line_page(rows)

    assert await _click_line(page, "-1") is True

    assert trs[_rank_of(ARSENAL_LEEDS_AH_ROWS, "-1")].click.await_count == 1


async def test_exact_tail_refuses_a_line_two_rows_share(caplog):
    page, trs = _line_page(GEA_MACHAC_AH_ROWS)

    with caplog.at_level(logging.WARNING):
        assert await _click_line(page, "+1.5") is False

    assert not any(tr.click.await_count for tr in trs)
    assert "Line '+1.5' matches 2 different rows; refusing to pick one." in caplog.text


async def test_exact_tail_clicks_a_line_no_other_row_shares():
    page, trs = _line_page(GEA_MACHAC_AH_ROWS)

    assert await _click_line(page, "+1") is True

    assert [tr.click.await_count for tr in trs] == [0, 0, 0, 1, 0, 0, 0, 0, 0, 0]


async def test_a_line_row_is_looked_for_once_the_table_shows_it_without_scrolling():
    """R13: one wait for the row, at most SCROLL_UNTIL_CLICK_TIMEOUT_S, then one read; nothing scrolls."""
    page, _ = _line_page(ARSENAL_LEEDS_AH_ROWS)

    assert await PageScroller().click_line_row(
        page, OddsPortalSelectors.SUB_MARKET_SELECTOR, "-1", OddsPortalSelectors.SUB_MARKET_CLICK_ANCESTOR
    )

    page.wait_for_function.assert_awaited_once_with(
        _LINE_ROW_JS,
        arg=_line_args("-1", "present"),
        timeout=SCROLL_UNTIL_CLICK_TIMEOUT_S * 1000,
        polling=SIGNAL_POLL_MS,
    )
    page.query_selector_all.assert_awaited_once()
    page.evaluate.assert_not_awaited()
    page.wait_for_timeout.assert_not_awaited()


async def test_a_line_the_table_never_shows_clicks_nothing_and_warns(caplog):
    page, trs = _line_page(ARSENAL_LEEDS_AH_ROWS)
    page.wait_for_function = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 1000ms exceeded."))

    with caplog.at_level(logging.WARNING):
        assert await _click_line(page, "+9.5") is False

    assert "No row of line '+9.5' within 1000 ms; carrying on with the page as it is." in caplog.text
    page.query_selector_all.assert_not_awaited()
    assert not any(tr.click.await_count for tr in trs)


@pytest.mark.parametrize(("shown", "want"), [(True, "open"), (False, "closed")])
async def test_a_toggled_line_waits_for_its_bookmaker_rows(shown, want):
    """R8 for a line market: its bookmaker rows under it once opened, gone once closed, at most 2 s."""
    page = MagicMock(wait_for_function=AsyncMock(return_value=MagicMock()))

    assert (
        await PageScroller().wait_for_line_bookmakers(
            page,
            OddsPortalSelectors.SUB_MARKET_SELECTOR,
            "+2.5",
            OddsPortalSelectors.SUB_MARKET_CLICK_ANCESTOR,
            shown=shown,
        )
        is True
    )

    page.wait_for_function.assert_awaited_once_with(
        _LINE_ROW_JS, arg=_line_args("+2.5", want), timeout=SCROLL_PAUSE_TIME_MS, polling=SIGNAL_POLL_MS
    )


async def test_a_line_with_no_bookmaker_rows_warns_at_the_cap(caplog):
    page = MagicMock(wait_for_function=AsyncMock(side_effect=PlaywrightTimeoutError("Timeout 2000ms exceeded.")))

    with caplog.at_level(logging.WARNING):
        assert (
            await PageScroller().wait_for_line_bookmakers(
                page,
                OddsPortalSelectors.SUB_MARKET_SELECTOR,
                "+2.25",
                OddsPortalSelectors.SUB_MARKET_CLICK_ANCESTOR,
                shown=True,
            )
            is False
        )

    assert "No bookmaker rows under line '+2.25' within 2000 ms" in caplog.text
