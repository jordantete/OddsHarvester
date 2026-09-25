from unittest.mock import AsyncMock, MagicMock

import pytest

from oddsharvester.core.market_extraction.odds_history_extractor import (
    LEAF_BOOKMAKER_ROW_CSS,
    OddsHistoryExtractor,
)


def _row(name=None, title=None, cells=0):
    """Bookmaker row mock: `name` is the visible label, `title` the logo link title."""
    name_el = None
    if name is not None:
        name_el = AsyncMock()
        name_el.text_content = AsyncMock(return_value=name)
    title_el = None
    if title is not None:
        title_el = AsyncMock()
        title_el.get_attribute = AsyncMock(return_value=title)

    async def query_selector(selector):
        return title_el if selector == "a[title]" else name_el

    row = AsyncMock()
    row.query_selector = AsyncMock(side_effect=query_selector)
    row.query_selector_all = AsyncMock(return_value=[AsyncMock() for _ in range(cells)])
    return row


def _modal_headers(htmls):
    """One modal header per hover; None stands for a header whose parent is not an element."""
    headers = []
    for html in htmls:
        wrapper = MagicMock()
        if html is None:
            wrapper.as_element = MagicMock(return_value=None)
        else:
            element = AsyncMock()
            element.inner_html = AsyncMock(return_value=html)
            wrapper.as_element = MagicMock(return_value=element)
        header = AsyncMock()
        header.evaluate_handle = AsyncMock(return_value=wrapper)
        headers.append(header)
    return headers


class TestOddsHistoryExtractor:
    @pytest.fixture
    def extractor(self):
        return OddsHistoryExtractor()

    @pytest.fixture
    def page(self):
        page = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        return page

    def test_leaf_row_selector_excludes_rows_that_wrap_a_table(self):
        assert LEAF_BOOKMAKER_ROW_CSS == 'tr:has(a[href*="/bookmakers/"]):not(:has(tr))'

    @pytest.mark.asyncio
    async def test_hovers_each_outcome_cell_of_the_matching_row(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=3)])
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers(["<a/>", "<b/>", "<c/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == ["<a/>", "<b/>", "<c/>"]
        page.query_selector_all.assert_awaited_once_with(LEAF_BOOKMAKER_ROW_CSS)

    @pytest.mark.asyncio
    async def test_matches_the_exact_name_not_a_prefix(self, extractor, page):
        exchange, plain = _row("Betfair Exchange", cells=2), _row("Betfair", cells=2)
        page.query_selector_all = AsyncMock(return_value=[exchange, plain])
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers(["<a/>", "<b/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Betfair", 2)

        assert result == ["<a/>", "<b/>"]
        exchange.query_selector_all.assert_not_awaited()
        plain.query_selector_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_matches_a_logo_only_row_by_its_normalised_title(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row(title="Go to Betfair Exchange website!", cells=1)])
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers(["<a/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Betfair Exchange", 1)

        assert result == ["<a/>"]

    @pytest.mark.asyncio
    async def test_name_match_ignores_whitespace_differences(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Betfair\n  Exchange", cells=1)])
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers(["<a/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "BetfairExchange", 1)

        assert result == ["<a/>"]

    @pytest.mark.asyncio
    async def test_hovers_at_most_cell_count_cells(self, extractor, page):
        row = _row("Bookmaker1", cells=4)
        page.query_selector_all = AsyncMock(return_value=[row])
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers(["<a/>", "<b/>", "<c/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == ["<a/>", "<b/>", "<c/>"]
        cells = row.query_selector_all.return_value
        cells[3].hover.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fewer_cells_than_outcomes_pads_with_none(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=2)])
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers(["<a/>", "<b/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == ["<a/>", "<b/>", None]

    @pytest.mark.asyncio
    async def test_failed_cell_keeps_its_slot(self, extractor, page):
        first, _, third = _modal_headers(["<a/>", "<unused/>", "<c/>"])
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=3)])
        page.wait_for_selector = AsyncMock(side_effect=[first, TimeoutError("no modal"), third])

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == ["<a/>", None, "<c/>"]

    @pytest.mark.asyncio
    async def test_modal_without_element_gives_none(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=1)])
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers([None]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 1)

        assert result == [None]

    @pytest.mark.asyncio
    async def test_no_matching_row_gives_one_none_per_outcome(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Other", cells=3)])

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == [None, None, None]

    @pytest.mark.asyncio
    async def test_row_listing_failure_gives_one_none_per_outcome(self, extractor, page):
        page.query_selector_all = AsyncMock(side_effect=Exception("detached"))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 2)

        assert result == [None, None]

    @pytest.mark.asyncio
    async def test_unreadable_row_name_is_skipped(self, extractor, page):
        broken = AsyncMock()
        broken.query_selector = AsyncMock(side_effect=Exception("stale"))
        page.query_selector_all = AsyncMock(return_value=[broken, _row("Bookmaker1", cells=1)])
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers(["<a/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 1)

        assert result == ["<a/>"]

    def test_logger_initialization(self, extractor):
        assert extractor.logger.name == "OddsHistoryExtractor"
