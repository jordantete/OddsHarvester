from unittest.mock import AsyncMock, MagicMock

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import pytest

from oddsharvester.core.browser.waits import SIGNAL_POLL_MS
from oddsharvester.core.market_extraction.odds_history_extractor import (
    LEAF_BOOKMAKER_ROW_CSS,
    SETTLED_TOOLTIP_JS,
    OddsHistoryExtractor,
    is_history_response,
)
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import ODDS_HISTORY_HOVER_WAIT_MS


def _row(name=None, title=None, cells=0, href=None):
    """Bookmaker row mock: `name` is the visible label, `title` the logo link title, `href` the logo link."""
    name_el = None
    if name is not None:
        name_el = AsyncMock()
        name_el.text_content = AsyncMock(return_value=name)
    title_el = None
    if title is not None:
        title_el = AsyncMock()
        title_el.get_attribute = AsyncMock(return_value=title)
    link_el = None
    if href is not None:
        link_el = AsyncMock()
        link_el.get_attribute = AsyncMock(return_value=href)

    async def query_selector(selector):
        if selector == "a[title]":
            return title_el
        if selector == OddsPortalSelectors.BOOKMAKER_LINK_CSS:
            return link_el
        return name_el

    row = AsyncMock()
    row.query_selector = AsyncMock(side_effect=query_selector)
    row.query_selector_all = AsyncMock(return_value=[AsyncMock() for _ in range(cells)])
    return row


class _HistoryResponse:
    """Stands for page.expect_response: the block ends once the response came, or raises at the cap."""

    def __init__(self, arrives: bool = True):
        self.arrives = arrives

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is None and not self.arrives:
            raise PlaywrightTimeoutError(f"Timeout {ODDS_HISTORY_HOVER_WAIT_MS}ms exceeded.")
        return False


def _tooltips(htmls):
    """One settled tooltip per hover: the handle of its HTML, or the cap reached for None."""
    results = []
    for html in htmls:
        if html is None:
            results.append(PlaywrightTimeoutError("Timeout exceeded."))
        else:
            handle = MagicMock()
            handle.json_value = AsyncMock(return_value=html)
            results.append(handle)
    return results


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
        page.expect_response = MagicMock(side_effect=lambda *args, **kwargs: _HistoryResponse())
        return page

    def test_leaf_row_selector_excludes_rows_that_wrap_a_table(self):
        assert LEAF_BOOKMAKER_ROW_CSS == 'tr:has(a[href*="/bookmakers/"]):not(:has(tr))'

    async def test_hovers_each_outcome_cell_of_the_matching_row(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=3)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<a/>", "<b/>", "<c/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == ["<a/>", "<b/>", "<c/>"]
        page.query_selector_all.assert_awaited_once_with(LEAF_BOOKMAKER_ROW_CSS)
        page.wait_for_timeout.assert_not_awaited()
        page.wait_for_selector.assert_not_awaited()

    async def test_a_hover_is_read_once_its_response_came_and_its_spinner_went(self, extractor, page):
        """R16: the history response, then the tooltip without its spinner, both within ODDS_HISTORY_HOVER_WAIT_MS."""
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=1)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<final/>"]))

        assert await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 1) == ["<final/>"]

        page.expect_response.assert_called_once_with(is_history_response, timeout=ODDS_HISTORY_HOVER_WAIT_MS)
        expression = page.wait_for_function.await_args.args[0]
        kwargs = page.wait_for_function.await_args.kwargs
        assert expression == SETTLED_TOOLTIP_JS
        assert kwargs["arg"] == OddsPortalSelectors.ODDS_MOVEMENT_HEADER
        assert 0 < kwargs["timeout"] <= ODDS_HISTORY_HOVER_WAIT_MS
        assert kwargs["polling"] == SIGNAL_POLL_MS

    async def test_a_hover_whose_response_never_comes_reads_the_tooltip_as_it_is(self, extractor, page, caplog):
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=1)])
        page.expect_response = MagicMock(return_value=_HistoryResponse(arrives=False))
        page.wait_for_function = AsyncMock()
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers(["<loading/>"]))

        with caplog.at_level("WARNING"):
            assert await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 1) == ["<loading/>"]

        assert "No odds-history response within 2000 ms of the hover" in caplog.text
        page.wait_for_function.assert_not_awaited()

    async def test_a_tooltip_still_loading_at_the_cap_is_read_as_it_is(self, extractor, page, caplog):
        """The response came, but the tooltip still shows its spinner: the header is read as before."""
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=1)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips([None]))
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers(["<loading/>"]))

        with caplog.at_level("WARNING"):
            assert await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 1) == ["<loading/>"]

        assert "No settled odds-history tooltip within" in caplog.text

    def test_only_the_history_request_answers_a_hover(self):
        history = MagicMock(url="https://www.oddsportal.com/proxy/match-event-history/1-lMp9YMye-1-2-0-141/?geo=BG")
        match_event = MagicMock(url="https://www.oddsportal.com/match-event/1-1-lMp9YMye-1-2-yj8e9.dat")

        assert is_history_response(history) is True
        assert is_history_response(match_event) is False

    async def test_matches_the_exact_name_not_a_prefix(self, extractor, page):
        exchange, plain = _row("Betfair Exchange", cells=2), _row("Betfair", cells=2)
        page.query_selector_all = AsyncMock(return_value=[exchange, plain])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<a/>", "<b/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Betfair", 2)

        assert result == ["<a/>", "<b/>"]
        exchange.query_selector_all.assert_not_awaited()
        plain.query_selector_all.assert_awaited_once()

    async def test_matches_a_logo_only_row_by_its_normalised_title(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row(title="Go to Betfair Exchange website!", cells=1)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<a/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Betfair Exchange", 1)

        assert result == ["<a/>"]

    async def test_matches_a_logo_only_row_by_its_link_slug(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row(href="/proxy/bookmakers/unibet-fr/link/", cells=1)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<a/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Unibet.fr", 1)

        assert result == ["<a/>"]

    async def test_name_match_ignores_whitespace_differences(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Betfair\n  Exchange", cells=1)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<a/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "BetfairExchange", 1)

        assert result == ["<a/>"]

    async def test_hovers_at_most_cell_count_cells(self, extractor, page):
        row = _row("Bookmaker1", cells=4)
        page.query_selector_all = AsyncMock(return_value=[row])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<a/>", "<b/>", "<c/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == ["<a/>", "<b/>", "<c/>"]
        cells = row.query_selector_all.return_value
        cells[3].hover.assert_not_awaited()

    async def test_fewer_cells_than_outcomes_pads_with_none(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=2)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<a/>", "<b/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == ["<a/>", "<b/>", None]

    async def test_failed_cell_keeps_its_slot(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=3)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<a/>", None, "<c/>"]))
        page.wait_for_selector = AsyncMock(side_effect=TimeoutError("no modal"))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == ["<a/>", None, "<c/>"]

    async def test_modal_without_element_gives_none(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Bookmaker1", cells=1)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips([None]))
        page.wait_for_selector = AsyncMock(side_effect=_modal_headers([None]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 1)

        assert result == [None]

    async def test_no_matching_row_gives_one_none_per_outcome(self, extractor, page):
        page.query_selector_all = AsyncMock(return_value=[_row("Other", cells=3)])

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 3)

        assert result == [None, None, None]

    async def test_row_listing_failure_gives_one_none_per_outcome(self, extractor, page):
        page.query_selector_all = AsyncMock(side_effect=Exception("detached"))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 2)

        assert result == [None, None]

    async def test_unreadable_row_name_is_skipped(self, extractor, page):
        broken = AsyncMock()
        broken.query_selector = AsyncMock(side_effect=Exception("stale"))
        page.query_selector_all = AsyncMock(return_value=[broken, _row("Bookmaker1", cells=1)])
        page.wait_for_function = AsyncMock(side_effect=_tooltips(["<a/>"]))

        result = await extractor.extract_odds_history_for_bookmaker(page, "Bookmaker1", 1)

        assert result == ["<a/>"]

    def test_logger_initialization(self, extractor):
        assert extractor.logger.name == "OddsHistoryExtractor"
