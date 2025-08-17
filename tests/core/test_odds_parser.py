from unittest.mock import MagicMock, patch

import pytest

from src.core.market_extraction.odds_parser import OddsParser


class TestOddsParser:
    """Unit tests for the OddsParser class."""

    @pytest.fixture
    def odds_parser(self):
        """Create an instance of OddsParser."""
        return OddsParser()

    # Sample HTML for testing
    SAMPLE_HTML_ODDS = """
    <div class="border-black-borders flex h-9">
        <img class="bookmaker-logo" title="Bookmaker1">
        <div class="flex-center flex-col font-bold">1.90</div>
        <div class="flex-center flex-col font-bold">3.50</div>
        <div class="flex-center flex-col font-bold">4.20</div>
    </div>
    <div class="border-black-borders flex h-9">
        <img class="bookmaker-logo" title="Bookmaker2">
        <div class="flex-center flex-col font-bold">1.85</div>
        <div class="flex-center flex-col font-bold">3.60</div>
        <div class="flex-center flex-col font-bold">4.10</div>
    </div>
    """

    SAMPLE_HTML_ODDS_HISTORY = """
    <div>
        <h3>Odds movement</h3>
        <div class="flex flex-col gap-1">
            <div class="flex gap-3">
                <div class="font-normal">10 Jun, 14:30</div>
            </div>
            <div class="flex gap-3">
                <div class="font-normal">10 Jun, 12:00</div>
            </div>
        </div>
        <div class="flex flex-col gap-1">
            <div class="font-bold">1.95</div>
            <div class="font-bold">1.90</div>
        </div>
        <div class="mt-2 gap-1">
            <div class="flex gap-1">
                <div>10 Jun, 08:00</div>
                <div class="font-bold">1.85</div>
            </div>
        </div>
    </div>
    """

    def test_parse_market_odds_success(self, odds_parser):
        """Test successful parsing of market odds."""
        # Arrange
        odds_labels = ["1", "X", "2"]

        # Act
        result = odds_parser.parse_market_odds(self.SAMPLE_HTML_ODDS, "FullTime", odds_labels)

        # Assert
        assert len(result) == 2
        assert result[0]["bookmaker_name"] == "Bookmaker1"
        assert result[0]["1"] == "1.90"
        assert result[0]["X"] == "3.50"
        assert result[0]["2"] == "4.20"
        assert result[0]["period"] == "FullTime"
        assert result[1]["bookmaker_name"] == "Bookmaker2"

    def test_parse_market_odds_with_target_bookmaker(self, odds_parser):
        """Test parsing odds with a specific target bookmaker."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        target_bookmaker = "Bookmaker1"

        # Act
        result = odds_parser.parse_market_odds(self.SAMPLE_HTML_ODDS, "FullTime", odds_labels, target_bookmaker)

        # Assert
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"
        assert result[0]["1"] == "1.90"
        assert result[0]["X"] == "3.50"
        assert result[0]["2"] == "4.20"

    def test_parse_market_odds_no_bookmakers(self, odds_parser):
        """Test parsing odds when no bookmakers are found."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        empty_html = "<div>No bookmakers found</div>"

        # Act
        result = odds_parser.parse_market_odds(empty_html, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0

    def test_parse_market_odds_missing_data(self, odds_parser):
        """Test parsing odds when a bookmaker has incomplete data."""
        # Arrange
        odds_labels = ["1", "X", "2", "Extras"]

        # Act
        result = odds_parser.parse_market_odds(self.SAMPLE_HTML_ODDS, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0

    def test_parse_market_odds_error_handling(self, odds_parser):
        """Test error handling during odds parsing."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        broken_html = """
        <div class="border-black-borders flex h-9">
            <img class="bookmaker-logo" title="Bookmaker1">
            <!-- Data manquante/corrompue -->
        </div>
        """

        # Act
        result = odds_parser.parse_market_odds(broken_html, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0  # Should handle error gracefully

    def test_parse_market_odds_duplicate_odds_removal(self, odds_parser):
        """Test that duplicate odds values are properly cleaned."""
        # Arrange
        html_with_duplicates = """
        <div class="border-black-borders flex h-9">
            <img class="bookmaker-logo" title="Bookmaker1">
            <div class="flex-center flex-col font-bold">1.901.90</div>
            <div class="flex-center flex-col font-bold">3.50</div>
        </div>
        """
        odds_labels = ["1", "X"]

        # Act
        result = odds_parser.parse_market_odds(html_with_duplicates, "FullTime", odds_labels)

        # Assert
        assert len(result) == 1
        assert result[0]["1"] == "1.90"  # Duplicate should be removed

    def test_parse_market_odds_fallback_selector(self, odds_parser):
        """Test parsing with fallback selector when primary selector fails."""
        # Arrange
        html_with_fallback = """
        <div class="border-black-borders flex h-9">
            <img class="bookmaker-logo" title="Bookmaker1">
            <div class="flex-center flex-col font-bold">1.90</div>
            <div class="flex-center flex-col font-bold">3.50</div>
        </div>
        """
        odds_labels = ["1", "X"]

        # Act
        result = odds_parser.parse_market_odds(html_with_fallback, "FullTime", odds_labels)

        # Assert
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"

    def test_parse_odds_history_modal_success(self, odds_parser):
        """Test successful parsing of odds history modal."""
        # Arrange
        with patch("src.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: __import__("datetime").datetime.strptime(
                *args, **kwargs
            )

            # Act
            result = odds_parser.parse_odds_history_modal(self.SAMPLE_HTML_ODDS_HISTORY)

            # Assert
            assert "odds_history" in result
            assert len(result["odds_history"]) == 2
            assert result["odds_history"][0]["odds"] == 1.95
            assert result["odds_history"][1]["odds"] == 1.90
            assert "opening_odds" in result

    def test_parse_odds_history_modal_invalid_html(self, odds_parser):
        """Test parsing odds history from invalid HTML."""
        # Arrange
        with patch("src.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: __import__("datetime").datetime.strptime(
                *args, **kwargs
            )

            # Act
            invalid_html = "<div>Invalid HTML content</div>"
            result = odds_parser.parse_odds_history_modal(invalid_html)

            # Assert
            assert result == {}

    def test_parse_odds_history_modal_invalid_date(self, odds_parser):
        """Test parsing odds history with invalid date format."""
        # Arrange
        with patch("src.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            # Force ValueError on strptime
            mock_datetime.strptime.side_effect = ValueError("Invalid date format")

            # Act
            result = odds_parser.parse_odds_history_modal(self.SAMPLE_HTML_ODDS_HISTORY)

            # Assert
            assert "odds_history" in result
            assert len(result["odds_history"]) == 0

    def test_logger_initialization(self, odds_parser):
        """Test that logger is properly initialized."""
        assert odds_parser.logger is not None
        assert odds_parser.logger.name == "OddsParser"
