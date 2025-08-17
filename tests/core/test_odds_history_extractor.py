from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.market_extraction.odds_history_extractor import OddsHistoryExtractor


class TestOddsHistoryExtractor:
    """Unit tests for the OddsHistoryExtractor class."""

    @pytest.fixture
    def odds_history_extractor(self):
        """Create an instance of OddsHistoryExtractor."""
        return OddsHistoryExtractor()

    @pytest.fixture
    def page_mock(self):
        """Create a mock for the Playwright page."""
        mock = AsyncMock()
        mock.wait_for_timeout = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_success(self, odds_history_extractor, page_mock):
        """Test successful extraction of odds history for a bookmaker."""
        # Arrange
        bookmaker_name = "Bookmaker1"
        sample_html = "<div>Sample modal HTML</div>"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value=bookmaker_name)
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for odds blocks
        odds_block = AsyncMock()
        bookmaker_row.query_selector_all = AsyncMock(return_value=[odds_block])

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])
        page_mock.wait_for_selector = AsyncMock()

        # Create mock for modal wrapper and element
        modal_wrapper = AsyncMock()
        modal_element = AsyncMock()
        modal_element.inner_html = AsyncMock(return_value=sample_html)
        modal_wrapper.as_element = MagicMock(return_value=modal_element)

        # Set up the chain of mocks
        page_mock.wait_for_selector.return_value.evaluate_handle.return_value = modal_wrapper

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert len(result) == 1
        assert result[0] == sample_html
        page_mock.wait_for_timeout.assert_called_with(2000)  # SCROLL_PAUSE_TIME

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_no_match(self, odds_history_extractor, page_mock):
        """Test extraction when no matching bookmaker is found."""
        # Arrange
        bookmaker_name = "NonExistentBookmaker"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value="DifferentBookmaker")
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_no_logo(self, odds_history_extractor, page_mock):
        """Test extraction when bookmaker row has no logo."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock for bookmaker row without logo
        bookmaker_row = AsyncMock()
        bookmaker_row.query_selector = AsyncMock(return_value=None)

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_no_odds_blocks(self, odds_history_extractor, page_mock):
        """Test extraction when bookmaker has no odds blocks."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value=bookmaker_name)
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for odds blocks (empty)
        bookmaker_row.query_selector_all = AsyncMock(return_value=[])

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_modal_not_found(self, odds_history_extractor, page_mock):
        """Test extraction when odds movement modal is not found."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value=bookmaker_name)
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for odds blocks
        odds_block = AsyncMock()
        bookmaker_row.query_selector_all = AsyncMock(return_value=[odds_block])

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])
        page_mock.wait_for_selector = AsyncMock(side_effect=Exception("Modal not found"))

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_modal_element_none(self, odds_history_extractor, page_mock):
        """Test extraction when modal element is None."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value=bookmaker_name)
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for odds blocks
        odds_block = AsyncMock()
        bookmaker_row.query_selector_all = AsyncMock(return_value=[odds_block])

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])
        page_mock.wait_for_selector = AsyncMock()

        # Create mock for modal wrapper that returns None
        modal_wrapper = AsyncMock()
        modal_wrapper.as_element = MagicMock(return_value=None)

        # Set up the chain of mocks
        page_mock.wait_for_selector.return_value.evaluate_handle.return_value = modal_wrapper

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_multiple_odds_blocks(self, odds_history_extractor, page_mock):
        """Test extraction with multiple odds blocks for the same bookmaker."""
        # Arrange
        bookmaker_name = "Bookmaker1"
        sample_html1 = "<div>Modal HTML 1</div>"
        sample_html2 = "<div>Modal HTML 2</div>"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value=bookmaker_name)
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for multiple odds blocks
        odds_block1 = AsyncMock()
        odds_block2 = AsyncMock()
        bookmaker_row.query_selector_all = AsyncMock(return_value=[odds_block1, odds_block2])

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])
        page_mock.wait_for_selector = AsyncMock()

        # Create mock for modal wrapper and elements
        modal_wrapper1 = AsyncMock()
        modal_element1 = AsyncMock()
        modal_element1.inner_html = AsyncMock(return_value=sample_html1)
        modal_wrapper1.as_element = MagicMock(return_value=modal_element1)

        modal_wrapper2 = AsyncMock()
        modal_element2 = AsyncMock()
        modal_element2.inner_html = AsyncMock(return_value=sample_html2)
        modal_wrapper2.as_element = MagicMock(return_value=modal_element2)

        # Set up the chain of mocks
        page_mock.wait_for_selector.return_value.evaluate_handle.side_effect = [modal_wrapper1, modal_wrapper2]

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert len(result) == 2
        assert result[0] == sample_html1
        assert result[1] == sample_html2

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_multiple_bookmakers(self, odds_history_extractor, page_mock):
        """Test extraction with multiple bookmakers, only one matching."""
        # Arrange
        bookmaker_name = "Bookmaker1"
        sample_html = "<div>Sample modal HTML</div>"

        # Create mock for first bookmaker row (no match)
        bookmaker_row1 = AsyncMock()
        logo_img1 = AsyncMock()
        logo_img1.get_attribute = AsyncMock(return_value="DifferentBookmaker")
        bookmaker_row1.query_selector = AsyncMock(return_value=logo_img1)

        # Create mock for second bookmaker row (match)
        bookmaker_row2 = AsyncMock()
        logo_img2 = AsyncMock()
        logo_img2.get_attribute = AsyncMock(return_value=bookmaker_name)
        bookmaker_row2.query_selector = AsyncMock(return_value=logo_img2)

        # Create mock for odds blocks
        odds_block = AsyncMock()
        bookmaker_row2.query_selector_all = AsyncMock(return_value=[odds_block])

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row1, bookmaker_row2])
        page_mock.wait_for_selector = AsyncMock()

        # Create mock for modal wrapper and element
        modal_wrapper = AsyncMock()
        modal_element = AsyncMock()
        modal_element.inner_html = AsyncMock(return_value=sample_html)
        modal_wrapper.as_element = MagicMock(return_value=modal_element)

        # Set up the chain of mocks
        page_mock.wait_for_selector.return_value.evaluate_handle.return_value = modal_wrapper

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert len(result) == 1
        assert result[0] == sample_html

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_exception_handling(self, odds_history_extractor, page_mock):
        """Test exception handling during odds history extraction."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock that raises an exception
        page_mock.query_selector_all = AsyncMock(side_effect=Exception("Test exception"))

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_row_exception_handling(self, odds_history_extractor, page_mock):
        """Test exception handling when processing individual bookmaker rows."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock for bookmaker row that raises exception
        bookmaker_row = AsyncMock()
        bookmaker_row.query_selector = AsyncMock(side_effect=Exception("Row processing error"))

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])

        # Act
        result = await odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert result == []

    def test_logger_initialization(self, odds_history_extractor):
        """Test that logger is properly initialized."""
        assert odds_history_extractor.logger is not None
        assert odds_history_extractor.logger.name == "OddsHistoryExtractor"
