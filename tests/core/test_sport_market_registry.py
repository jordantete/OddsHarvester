from unittest.mock import MagicMock, patch
from src.utils.sport_market_constants import Sport
from src.core.sport_market_registry import SportMarketRegistry, SportMarketRegistrar

class TestSportMarketRegistry:
    """Unit tests for the SportMarketRegistry class."""

    def setup_method(self):
        """Reset the registry before each test."""
        SportMarketRegistry._registry = {}

    def test_register_new_sport(self):
        """Test registering a new sport in the registry."""
        # Arrange
        sport = Sport.FOOTBALL
        market_mapping = {"1x2": lambda x: x}

        # Act
        SportMarketRegistry.register(sport, market_mapping)

        # Assert
        assert sport.value in SportMarketRegistry._registry
        assert "1x2" in SportMarketRegistry._registry[sport.value]
        assert SportMarketRegistry._registry[sport.value]["1x2"] == market_mapping["1x2"]

    def test_register_existing_sport(self):
        """Test adding a market to an already registered sport."""
        # Arrange
        sport = Sport.FOOTBALL
        market_mapping1 = {"1x2": lambda x: x}
        market_mapping2 = {"btts": lambda x: x * 2}

        # Act
        SportMarketRegistry.register(sport, market_mapping1)
        SportMarketRegistry.register(sport, market_mapping2)

        # Assert
        assert sport.value in SportMarketRegistry._registry
        assert "1x2" in SportMarketRegistry._registry[sport.value]
        assert "btts" in SportMarketRegistry._registry[sport.value]
        assert SportMarketRegistry._registry[sport.value]["1x2"] == market_mapping1["1x2"]
        assert SportMarketRegistry._registry[sport.value]["btts"] == market_mapping2["btts"]

    def test_get_market_mapping_existing_sport(self):
        """Test retrieving the mapping for an existing sport."""
        # Arrange
        sport = Sport.FOOTBALL
        market_mapping = {"1x2": lambda x: x}
        SportMarketRegistry.register(sport, market_mapping)

        # Act
        result = SportMarketRegistry.get_market_mapping(sport.value)

        # Assert
        assert result == market_mapping

    def test_get_market_mapping_nonexistent_sport(self):
        """Test retrieving the mapping for a non-existent sport."""
        # Act
        result = SportMarketRegistry.get_market_mapping("nonexistent_sport")

        # Assert
        assert result == {}


class TestSportMarketRegistrar:
    """Unit tests for the SportMarketRegistrar class."""

    def setup_method(self):
        """Reset the registry before each test."""
        SportMarketRegistry._registry = {}

    def test_create_market_lambda(self):
        """Test the creation of a lambda function for market extraction."""
        # Arrange
        main_market = "1X2"
        specific_market = None
        odds_labels = ["1", "X", "2"]
        
        extractor_mock = MagicMock()
        page_mock = MagicMock()

        # Act
        lambda_func = SportMarketRegistrar.create_market_lambda(main_market, specific_market, odds_labels)
        lambda_func(extractor_mock, page_mock)

        # Assert
        extractor_mock.extract_market_odds.assert_called_once_with(
            page=page_mock,
            main_market=main_market,
            specific_market=specific_market,
            period="FullTime",
            odds_labels=odds_labels,
            scrape_odds_history=False,
            target_bookmaker=None
        )

    def test_register_football_markets(self):
        """Test registering markets for football."""
        # Act
        SportMarketRegistrar.register_football_markets()
        
        # Assert
        football_markets = SportMarketRegistry.get_market_mapping(Sport.FOOTBALL.value)
        assert "1x2" in football_markets
        assert "btts" in football_markets
        assert "double_chance" in football_markets
        assert "dnb" in football_markets
        
        # Check some Over/Under markets
        assert "over_under_2_5" in football_markets
        
        # Check some handicap markets
        assert "european_handicap_-1" in football_markets
        assert "asian_handicap_-1" in football_markets

    def test_register_all_markets(self):
        """Test registering all markets for all sports."""
        # Act
        with patch.object(SportMarketRegistrar, 'register_football_markets') as mock_football:
            with patch.object(SportMarketRegistrar, 'register_tennis_markets') as mock_tennis:
                with patch.object(SportMarketRegistrar, 'register_basketball_markets') as mock_basketball:
                    with patch.object(SportMarketRegistrar, 'register_rugby_league_markets') as mock_rugby_league:
                        with patch.object(SportMarketRegistrar, 'register_rugby_union_markets') as mock_rugby_union:
                            with patch.object(SportMarketRegistrar, 'register_ice_hockey_markets') as mock_ice_hockey:
                                with patch.object(SportMarketRegistrar, 'register_baseball_markets') as mock_baseball:
                                    SportMarketRegistrar.register_all_markets()
        
        # Assert
        mock_football.assert_called_once()
        mock_tennis.assert_called_once()
        mock_basketball.assert_called_once()
        mock_rugby_league.assert_called_once()
        mock_rugby_union.assert_called_once()
        mock_ice_hockey.assert_called_once()
        mock_baseball.assert_called_once() 