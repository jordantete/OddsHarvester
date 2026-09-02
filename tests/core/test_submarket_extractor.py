from unittest.mock import AsyncMock

from bs4 import BeautifulSoup
import pytest
from tests.dom_builders import line_row, odds_table

from oddsharvester.core.market_extraction.submarket_extractor import SubmarketExtractor

# =============================================================================
# HTML FIXTURES — the collapsed submarket line rows of a match view
# =============================================================================

# Over/Under line: the full label sits in the max-sm:hidden span (Strategy 1)
OVER_UNDER_HTML = odds_table(line_row("Over/Under +2.5", ["1.85", "1.95"], short_label="O/U +2.5"))

# Line whose label is a plain paragraph (Strategy 2)
OVER_UNDER_FALLBACK_P_HTML = odds_table(
    '<tr class="h-9 cursor-pointer"><td><img alt="arrow"/><p>Over/Under +1.5</p></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>1.40</p></div></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>2.80</p></div></td></tr>'
)

# European Handicap line with three outcomes
HANDICAP_FLEX_HTML = odds_table(line_row("European Handicap -1", ["2.50", "3.10", "2.80"], short_label="EH -1"))

# Handicap line whose label is a plain paragraph
HANDICAP_FLEX_FALLBACK_HTML = odds_table(
    '<tr class="h-9 cursor-pointer"><td><img alt="arrow"/><p>Asian Handicap -0.5</p></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>1.90</p></div></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>1.90</p></div></td></tr>'
)

# Label carried by a bold paragraph
FONT_BOLD_HTML = odds_table(
    '<tr class="h-9 cursor-pointer"><td><img alt="arrow"/><p class="font-bold text-sm">Draw No Bet</p></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>1.60</p></div></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>2.20</p></div></td></tr>'
)

# Correct Score label ("1:0")
CORRECT_SCORE_HTML = odds_table(
    '<tr class="h-9 cursor-pointer"><td><img alt="arrow"/><p>1:0</p></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>6.50</p></div></td></tr>'
)

# Row with no identifiable submarket name
NO_NAME_ROW_HTML = odds_table(
    '<tr class="h-9 cursor-pointer"><td><img alt="arrow"/><p>2.50</p><p>45%</p></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>1.80</p></div></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>2.00</p></div></td></tr>'
)

# Multiple submarkets page (for is_preview_compatible and extract_visible_submarkets_passive)
MULTI_SUBMARKET_PAGE_HTML = odds_table(
    line_row("Over/Under +1.5", ["1.30", "3.40"])
    + line_row("Over/Under +2.5", ["1.85", "1.95"])
    + line_row("Over/Under +3.5", ["2.60", "1.50"])
)

# Single submarket (incompatible with preview mode)
SINGLE_SUBMARKET_PAGE_HTML = odds_table(line_row("Over/Under +2.5", ["1.85", "1.95"]))

# Submarkets without sufficient odds (incompatible with preview)
NO_ODDS_PAGE_HTML = odds_table(line_row("Market A", ["1.85"]) + line_row("Market B", ["2.10"]))

# Empty page
EMPTY_PAGE_HTML = "<html><body></body></html>"

# Page with extra odds beyond labels
EXTRA_ODDS_HTML = odds_table(line_row("1X2", ["2.50", "3.10", "2.80"]))

# Correct Score page
CORRECT_SCORE_PAGE_HTML = odds_table(
    '<tr class="h-9 cursor-pointer"><td><img alt="arrow"/><p>1:0</p></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>6.50</p></div></td></tr>'
    + '<tr class="h-9 cursor-pointer"><td><img alt="arrow"/><p>2:1</p></td>'
    + '<td class="w-[var(--event-table-odd-col)]"><div class="font-bold"><p>8.00</p></div></td></tr>'
)


class TestSubmarketExtractor:
    """Unit tests for the SubmarketExtractor class."""

    @pytest.fixture
    def submarket_extractor(self):
        """Create an instance of SubmarketExtractor."""
        return SubmarketExtractor()

    @pytest.fixture
    def page_mock(self):
        """Create a mock for the Playwright page."""
        mock = AsyncMock()
        mock.wait_for_timeout = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_is_preview_compatible_market_no_submarkets(self, submarket_extractor, page_mock):
        """Test detection when no submarkets are found."""
        # Arrange
        main_market = "Over/Under"
        page_mock.query_selector_all = AsyncMock(return_value=[])

        # Act
        result = await submarket_extractor.is_preview_compatible_market(page_mock, main_market)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_is_preview_compatible_market_exception_handling(self, submarket_extractor, page_mock):
        """Test exception handling during preview compatibility check."""
        # Arrange
        main_market = "Over/Under"
        page_mock.query_selector_all = AsyncMock(side_effect=Exception("Test exception"))

        # Act
        result = await submarket_extractor.is_preview_compatible_market(page_mock, main_market)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_extract_visible_submarkets_passive_no_submarkets(self, submarket_extractor, page_mock):
        """Test extraction when no submarkets are visible."""
        # Arrange
        main_market = "Over/Under"
        period = "FullTime"
        odds_labels = ["odds_over", "odds_under"]

        page_mock.query_selector_all = AsyncMock(return_value=[])

        # Act
        result = await submarket_extractor.extract_visible_submarkets_passive(
            page_mock, main_market, period, odds_labels
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_visible_submarkets_passive_no_bookmakers(self, submarket_extractor, page_mock):
        """Test extraction when no bookmakers are found."""
        # Arrange
        main_market = "Over/Under"
        period = "FullTime"
        odds_labels = ["odds_over", "odds_under"]

        # Mock submarket elements
        submarket_element = AsyncMock()
        submarket_element.text_content = AsyncMock(return_value="Over/Under 2.5")
        page_mock.query_selector_all = AsyncMock(side_effect=[[submarket_element], []])

        # Act
        result = await submarket_extractor.extract_visible_submarkets_passive(
            page_mock, main_market, period, odds_labels
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_visible_submarkets_passive_missing_odds_data(self, submarket_extractor, page_mock):
        # Arrange
        main_market = "Over/Under"
        period = "FullTime"
        odds_labels = ["odds_over", "odds_under", "extra_odds"]

        # Mock submarket elements
        submarket_element = AsyncMock()
        submarket_element.text_content = AsyncMock(return_value="Over/Under 2.5")
        page_mock.query_selector_all = AsyncMock(side_effect=[[submarket_element], []])

        # Act
        result = await submarket_extractor.extract_visible_submarkets_passive(
            page_mock, main_market, period, odds_labels
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_visible_submarkets_passive_without_odds_labels(self, submarket_extractor, page_mock):
        """Test extraction without providing odds labels."""
        # Arrange
        main_market = "Over/Under"
        period = "FullTime"
        odds_labels = None

        # Mock submarket elements
        submarket_element = AsyncMock()
        submarket_element.text_content = AsyncMock(return_value="Over/Under 2.5")
        page_mock.query_selector_all = AsyncMock(side_effect=[[submarket_element], []])

        # Act
        result = await submarket_extractor.extract_visible_submarkets_passive(
            page_mock, main_market, period, odds_labels
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_visible_submarkets_passive_exception_handling(self, submarket_extractor, page_mock):
        """Test exception handling during submarket extraction."""
        # Arrange
        main_market = "Over/Under"
        period = "FullTime"
        odds_labels = ["odds_over", "odds_under"]

        page_mock.query_selector_all = AsyncMock(side_effect=Exception("Test exception"))

        # Act
        result = await submarket_extractor.extract_visible_submarkets_passive(
            page_mock, main_market, period, odds_labels
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_visible_submarkets_passive_bookmaker_row_exception(self, submarket_extractor, page_mock):
        """Test exception handling when processing individual bookmaker rows."""
        # Arrange
        main_market = "Over/Under"
        period = "FullTime"
        odds_labels = ["odds_over", "odds_under"]

        # Mock submarket elements
        submarket_element = AsyncMock()
        submarket_element.text_content = AsyncMock(return_value="Over/Under 2.5")

        # Mock bookmaker row that raises exception
        bookmaker_row = AsyncMock()
        bookmaker_row.query_selector = AsyncMock(side_effect=Exception("Row processing error"))

        page_mock.query_selector_all = AsyncMock(side_effect=[[submarket_element], [bookmaker_row]])

        # Act
        result = await submarket_extractor.extract_visible_submarkets_passive(
            page_mock, main_market, period, odds_labels
        )

        # Assert
        assert result == []

    def test_logger_initialization(self, submarket_extractor):
        """Test that logger is properly initialized."""
        assert submarket_extractor.logger is not None
        assert submarket_extractor.logger.name == "SubmarketExtractor"


class TestExtractSubmarketName:
    """Tests for _extract_submarket_name using real HTML fixtures."""

    @pytest.fixture
    def extractor(self):
        return SubmarketExtractor()

    def _parse_row(self, html: str):
        """Parse HTML and return the first line row (<tr>) of the table body."""
        soup = BeautifulSoup(html, "html.parser")
        return soup.select_one("tbody tr")

    def test_strategy1_data_testid_with_clean_name(self, extractor):
        """Strategy 1: clean-name element with max-sm:hidden class."""
        row = self._parse_row(OVER_UNDER_HTML)
        result = extractor._extract_submarket_name(row, "Over/Under")
        assert result == "Over/Under +2.5"

    def test_strategy1_data_testid_fallback_to_first_p(self, extractor):
        """Fallback: no clean-name class, first non-numeric text wins."""
        row = self._parse_row(OVER_UNDER_FALLBACK_P_HTML)
        result = extractor._extract_submarket_name(row, "Over/Under")
        assert result == "Over/Under +1.5"

    def test_strategy2_flex_classes_with_clean_name(self, extractor):
        """Clean-name element also works for handicap labels."""
        row = self._parse_row(HANDICAP_FLEX_HTML)
        result = extractor._extract_submarket_name(row, "European Handicap")
        assert result == "European Handicap -1"

    def test_strategy2_flex_classes_fallback_to_first_p(self, extractor):
        """Fallback for handicap labels without a clean-name class."""
        row = self._parse_row(HANDICAP_FLEX_FALLBACK_HTML)
        result = extractor._extract_submarket_name(row, "Asian Handicap")
        assert result == "Asian Handicap -0.5"

    def test_strategy3_font_bold_p(self, extractor):
        """Strategy 3: font-bold class on <p> tag."""
        row = self._parse_row(FONT_BOLD_HTML)
        result = extractor._extract_submarket_name(row, "Draw No Bet")
        assert result == "Draw No Bet"

    def test_strategy4_correct_score_colon(self, extractor):
        """Strategy 4: Correct Score submarket with colon pattern."""
        row = self._parse_row(CORRECT_SCORE_HTML)
        result = extractor._extract_submarket_name(row, "Correct Score")
        assert result == "1:0"

    def test_no_name_returns_none(self, extractor):
        """Returns None when no submarket name can be identified."""
        row = self._parse_row(NO_NAME_ROW_HTML)
        result = extractor._extract_submarket_name(row, "Over/Under")
        assert result is None

    def test_market_key_normalization(self, extractor):
        """data-testid pattern handles special characters in market name."""
        # "Over/Under" -> "over-under-collapsed-option-box"
        row = self._parse_row(OVER_UNDER_HTML)
        result = extractor._extract_submarket_name(row, "Over/Under")
        assert result == "Over/Under +2.5"

    def test_strategy1_takes_priority_over_strategy2(self, extractor):
        """The clean-name element is tried before the generic text fallback."""
        html = """
        <table><tbody><tr class="h-9 cursor-pointer">
            <td><span>Generic Loser</span><span class="max-sm:hidden">Clean Winner</span></td>
            <td><div data-testid="odd-container-default">1.85</div></td>
        </tr></tbody></table>
        """
        row = self._parse_row(html)
        result = extractor._extract_submarket_name(row, "Over/Under")
        assert result == "Clean Winner"


class TestIsPreviewCompatibleMarketHTML:
    """Tests for is_preview_compatible_market with real HTML content."""

    @pytest.fixture
    def extractor(self):
        return SubmarketExtractor()

    @pytest.fixture
    def page_mock(self):
        mock = AsyncMock()
        mock.wait_for_timeout = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_compatible_multiple_submarkets_with_odds(self, extractor, page_mock):
        """Returns True for multiple submarkets with >= 2 odds each."""
        page_mock.content = AsyncMock(return_value=MULTI_SUBMARKET_PAGE_HTML)
        result = await extractor.is_preview_compatible_market(page_mock, "Over/Under")
        assert result is True

    @pytest.mark.asyncio
    async def test_incompatible_single_submarket(self, extractor, page_mock):
        """Returns False for only 1 submarket (need > 1)."""
        page_mock.content = AsyncMock(return_value=SINGLE_SUBMARKET_PAGE_HTML)
        result = await extractor.is_preview_compatible_market(page_mock, "Over/Under")
        assert result is False

    @pytest.mark.asyncio
    async def test_incompatible_no_odds(self, extractor, page_mock):
        """Returns False when submarkets have < 2 odds containers."""
        page_mock.content = AsyncMock(return_value=NO_ODDS_PAGE_HTML)
        result = await extractor.is_preview_compatible_market(page_mock, "Over/Under")
        assert result is False

    @pytest.mark.asyncio
    async def test_incompatible_empty_page(self, extractor, page_mock):
        """Returns False for an empty page."""
        page_mock.content = AsyncMock(return_value=EMPTY_PAGE_HTML)
        result = await extractor.is_preview_compatible_market(page_mock, "Over/Under")
        assert result is False

    @pytest.mark.asyncio
    async def test_non_string_content_handled(self, extractor, page_mock):
        """Handles non-string content gracefully."""
        page_mock.content = AsyncMock(return_value=None)
        result = await extractor.is_preview_compatible_market(page_mock, "Over/Under")
        assert result is False


class TestExtractVisibleSubmarketsPassiveHTML:
    """Tests for extract_visible_submarkets_passive with real HTML content."""

    @pytest.fixture
    def extractor(self):
        return SubmarketExtractor()

    @pytest.fixture
    def page_mock(self):
        mock = AsyncMock()
        mock.wait_for_timeout = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_extract_over_under_submarkets(self, extractor, page_mock):
        """Extracts multiple Over/Under submarkets with correct odds."""
        page_mock.content = AsyncMock(return_value=MULTI_SUBMARKET_PAGE_HTML)

        result = await extractor.extract_visible_submarkets_passive(
            page_mock, "Over/Under", "FullTime", ["odds_over", "odds_under"]
        )

        assert len(result) == 3
        assert result[0]["submarket_name"] == "Over/Under +1.5"
        assert result[0]["odds_over"] == "1.30"
        assert result[0]["odds_under"] == "3.40"
        assert result[0]["period"] == "FullTime"
        assert result[0]["market_type"] == "Over/Under"
        assert result[0]["extraction_mode"] == "passive"

        assert result[1]["submarket_name"] == "Over/Under +2.5"
        assert result[1]["odds_over"] == "1.85"
        assert result[1]["odds_under"] == "1.95"

        assert result[2]["submarket_name"] == "Over/Under +3.5"

    @pytest.mark.asyncio
    async def test_extract_empty_page(self, extractor, page_mock):
        """Returns empty list for page with no submarkets."""
        page_mock.content = AsyncMock(return_value=EMPTY_PAGE_HTML)

        result = await extractor.extract_visible_submarkets_passive(
            page_mock, "Over/Under", "FullTime", ["odds_over", "odds_under"]
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_with_default_labels(self, extractor, page_mock):
        """Uses default Over/Under labels when odds_labels is None."""
        page_mock.content = AsyncMock(return_value=MULTI_SUBMARKET_PAGE_HTML)

        result = await extractor.extract_visible_submarkets_passive(page_mock, "Over/Under", "FullTime", None)

        assert len(result) == 3
        assert "odds_over" in result[0]
        assert "odds_under" in result[0]

    @pytest.mark.asyncio
    async def test_extract_correct_score_default_labels(self, extractor, page_mock):
        """Uses correct_score default label when market is Correct Score."""
        page_mock.content = AsyncMock(return_value=CORRECT_SCORE_PAGE_HTML)

        result = await extractor.extract_visible_submarkets_passive(page_mock, "Correct Score", "FullTime", None)

        assert len(result) == 2
        assert result[0]["submarket_name"] == "1:0"
        assert result[0]["correct_score"] == "6.50"
        assert result[1]["submarket_name"] == "2:1"
        assert result[1]["correct_score"] == "8.00"

    @pytest.mark.asyncio
    async def test_extract_with_extra_odds(self, extractor, page_mock):
        """Extra odds beyond labels are stored with generic keys."""
        page_mock.content = AsyncMock(return_value=EXTRA_ODDS_HTML)

        result = await extractor.extract_visible_submarkets_passive(page_mock, "1X2", "FullTime", ["odds_1", "odds_x"])

        assert len(result) == 1
        assert result[0]["odds_1"] == "2.50"
        assert result[0]["odds_x"] == "3.10"
        assert result[0]["odds_option_3"] == "2.80"

    @pytest.mark.asyncio
    async def test_extract_skips_rows_with_insufficient_odds(self, extractor, page_mock):
        """Rows with fewer odds than required labels are skipped."""
        html = """
        <html><body>
        <div class="border-black-borders flex">
            <p class="font-bold">Market A</p>
            <p data-testid="odd-container-default">1.85</p>
        </div>
        </body></html>
        """
        page_mock.content = AsyncMock(return_value=html)

        result = await extractor.extract_visible_submarkets_passive(
            page_mock, "Over/Under", "FullTime", ["odds_over", "odds_under"]
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_non_string_content(self, extractor, page_mock):
        """Handles non-string page content gracefully."""
        page_mock.content = AsyncMock(return_value=None)

        result = await extractor.extract_visible_submarkets_passive(
            page_mock, "Over/Under", "FullTime", ["odds_over", "odds_under"]
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_skips_nameless_rows(self, extractor, page_mock):
        """Rows where submarket name cannot be determined are skipped."""
        page_mock.content = AsyncMock(return_value=f"<html><body>{NO_NAME_ROW_HTML}</body></html>")

        result = await extractor.extract_visible_submarkets_passive(
            page_mock, "Over/Under", "FullTime", ["odds_over", "odds_under"]
        )

        assert result == []
