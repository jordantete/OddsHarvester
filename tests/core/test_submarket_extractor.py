from unittest.mock import AsyncMock

import pytest

from src.core.market_extraction.submarket_extractor import SubmarketExtractor


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
