from unittest.mock import MagicMock

import pytest

from oddsharvester.core.market_extraction.market_grouping import MarketGrouping


def _make_lambda_with_closure(main_market, odds_labels):
    """Helper to create a lambda with main_market and odds_labels in its closure."""
    return lambda self, page, period, hist, bk, preview, sport: (main_market, odds_labels)


class TestMarketGrouping:
    """Unit tests for the MarketGrouping class."""

    @pytest.fixture
    def market_grouping(self):
        """Create an instance of MarketGrouping."""
        return MarketGrouping()

    # --- get_main_market_info ---

    def test_get_main_market_info_no_closure(self, market_grouping):
        """Test extraction when market method has no closure."""
        mock_market_method = MagicMock()
        mock_market_method.__name__ = "test_market"
        mock_market_method.__closure__ = None

        result = market_grouping.get_main_market_info(mock_market_method)
        assert result is None

    def test_get_main_market_info_with_valid_closure(self, market_grouping):
        """Test extraction from a lambda that captures main_market and odds_labels."""
        main_market = "Over/Under"
        odds_labels = ["odds_over", "odds_under"]
        func = _make_lambda_with_closure(main_market, odds_labels)

        result = market_grouping.get_main_market_info(func)
        assert result is not None
        assert result["main_market"] == "Over/Under"
        assert result["odds_labels"] == ["odds_over", "odds_under"]

    def test_get_main_market_info_closure_without_main_market(self, market_grouping):
        """Test extraction from a closure that doesn't have main_market."""
        some_value = 42
        func = lambda: some_value  # noqa: E731

        result = market_grouping.get_main_market_info(func)
        assert result is None

    def test_get_main_market_info_no_hasattr_closure(self, market_grouping):
        """Test extraction when method has no __closure__ attribute at all."""

        def plain_func():
            pass

        result = market_grouping.get_main_market_info(plain_func)
        assert result is None

    def test_get_main_market_info_exception_returns_none(self, market_grouping):
        """Test that exceptions during inspection return None."""
        mock = MagicMock()
        mock.__closure__ = MagicMock()
        # Force an exception when iterating closure cells
        mock.__code__ = MagicMock()
        mock.__code__.co_freevars = ["main_market"]
        mock.__closure__.__iter__ = MagicMock(side_effect=TypeError("broken"))

        result = market_grouping.get_main_market_info(mock)
        assert result is None

    # --- group_markets_by_main_market ---

    def test_group_markets_by_main_market_empty_markets(self, market_grouping):
        """Test grouping with empty markets list."""
        result = market_grouping.group_markets_by_main_market([], {})
        assert result == {}

    def test_group_markets_single_group(self, market_grouping):
        """Test grouping markets that share the same main market."""
        main_market = "Over/Under"
        odds_labels = ["odds_over", "odds_under"]
        func_a = _make_lambda_with_closure(main_market, odds_labels)
        func_b = _make_lambda_with_closure(main_market, odds_labels)

        markets = ["over_under_1_5", "over_under_2_5"]
        market_methods = {"over_under_1_5": func_a, "over_under_2_5": func_b}

        result = market_grouping.group_markets_by_main_market(markets, market_methods)
        assert result == {"Over/Under": ["over_under_1_5", "over_under_2_5"]}

    def test_group_markets_multiple_groups(self, market_grouping):
        """Test grouping markets into distinct main market groups."""
        func_ou = _make_lambda_with_closure("Over/Under", ["odds_over", "odds_under"])
        func_1x2 = _make_lambda_with_closure("1X2", ["1", "X", "2"])

        markets = ["over_under_2_5", "1x2"]
        market_methods = {"over_under_2_5": func_ou, "1x2": func_1x2}

        result = market_grouping.group_markets_by_main_market(markets, market_methods)
        assert result == {"Over/Under": ["over_under_2_5"], "1X2": ["1x2"]}

    def test_group_markets_skips_unknown_markets(self, market_grouping):
        """Test that markets not in market_methods are silently skipped."""
        func = _make_lambda_with_closure("1X2", ["1", "X", "2"])
        markets = ["1x2", "nonexistent"]
        market_methods = {"1x2": func}

        result = market_grouping.group_markets_by_main_market(markets, market_methods)
        assert result == {"1X2": ["1x2"]}
        assert "nonexistent" not in str(result)

    def test_group_markets_skips_unextractable_info(self, market_grouping):
        """Test that markets whose closure can't be inspected are skipped."""
        mock = MagicMock()
        mock.__closure__ = None
        markets = ["broken_market"]
        market_methods = {"broken_market": mock}

        result = market_grouping.group_markets_by_main_market(markets, market_methods)
        assert result == {}

    def test_logger_initialization(self, market_grouping):
        """Test that logger is properly initialized."""
        assert market_grouping.logger is not None
        assert market_grouping.logger.name == "MarketGrouping"
