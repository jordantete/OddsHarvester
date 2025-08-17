from unittest.mock import MagicMock

import pytest

from src.core.market_extraction.market_grouping import MarketGrouping


class TestMarketGrouping:
    """Unit tests for the MarketGrouping class."""

    @pytest.fixture
    def market_grouping(self):
        """Create an instance of MarketGrouping."""
        return MarketGrouping()

    def test_get_main_market_info_no_constants(self, market_grouping):
        """Test extraction when market method has no constants."""
        # Arrange
        mock_market_method = MagicMock()
        mock_market_method.__name__ = "test_market"
        mock_market_method.__closure__ = None

        # Act
        result = market_grouping.get_main_market_info(mock_market_method)

        # Assert
        assert result is None

    def test_group_markets_by_main_market_empty_markets(self, market_grouping):
        """Test grouping with empty markets list."""
        # Arrange
        markets = []
        market_methods = {}

        # Act
        result = market_grouping.group_markets_by_main_market(markets, market_methods)

        # Assert
        assert result == {}

    def test_logger_initialization(self, market_grouping):
        """Test that logger is properly initialized."""
        assert market_grouping.logger is not None
        assert market_grouping.logger.name == "MarketGrouping"
