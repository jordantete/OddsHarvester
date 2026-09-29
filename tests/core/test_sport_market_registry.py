import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oddsharvester.core.market_extraction.market_grouping import MarketGrouping
from oddsharvester.core.sport_market_registry import SportMarketRegistrar, SportMarketRegistry, format_line_number
from oddsharvester.utils.sport_market_constants import Sport


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
            target_bookmaker=None,
            preview_submarkets_only=False,
            sport=None,
            history_reference=None,
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

    def test_register_tennis_markets(self):
        """Test registering markets for tennis."""
        # Act
        SportMarketRegistrar.register_tennis_markets()

        # Assert
        tennis_markets = SportMarketRegistry.get_market_mapping(Sport.TENNIS.value)

        # Basic markets
        assert "match_winner" in tennis_markets

        # Over/Under Sets markets
        assert "over_under_sets_2_5" in tennis_markets

        # Over/Under Games markets
        assert "over_under_games_22_5" in tennis_markets

        # Asian Handicap Games markets
        assert any(key.startswith("asian_handicap_") and key.endswith("_games") for key in tennis_markets)

        # Asian Handicap Sets markets
        assert any(key.startswith("asian_handicap_") and key.endswith("_sets") for key in tennis_markets)

        # Correct Score markets
        assert "correct_score_2_0" in tennis_markets
        assert "correct_score_0_2" in tennis_markets

    def test_register_basketball_markets(self):
        """Test registering markets for basketball."""
        # Act
        SportMarketRegistrar.register_basketball_markets()

        # Assert
        basketball_markets = SportMarketRegistry.get_market_mapping(Sport.BASKETBALL.value)

        # Basic markets
        assert "1x2" in basketball_markets
        assert "home_away" in basketball_markets

        # Over/Under markets
        assert any(key.startswith("over_under_games_") for key in basketball_markets)

        # Asian Handicap markets
        assert any(key.startswith("asian_handicap_games_") for key in basketball_markets)

    def test_register_rugby_league_markets(self):
        """Test registering markets for rugby league."""
        # Act
        SportMarketRegistrar.register_rugby_league_markets()

        # Assert
        rugby_league_markets = SportMarketRegistry.get_market_mapping(Sport.RUGBY_LEAGUE.value)

        # Basic markets
        assert "1x2" in rugby_league_markets
        assert "home_away" in rugby_league_markets
        assert "dnb" in rugby_league_markets
        assert "double_chance" in rugby_league_markets

        # Over/Under markets
        assert "over_under_43_5" in rugby_league_markets

        # Handicap markets
        assert "handicap_-13_5" in rugby_league_markets

    def test_register_rugby_union_markets(self):
        """Test registering markets for rugby union."""
        # Act
        SportMarketRegistrar.register_rugby_union_markets()

        # Assert
        rugby_union_markets = SportMarketRegistry.get_market_mapping(Sport.RUGBY_UNION.value)

        # Basic markets
        assert "1x2" in rugby_union_markets
        assert "home_away" in rugby_union_markets
        assert "dnb" in rugby_union_markets
        assert "double_chance" in rugby_union_markets

        # Over/Under markets
        assert "over_under_43_5" in rugby_union_markets

        # Handicap markets
        assert "handicap_-13_5" in rugby_union_markets

    def test_register_ice_hockey_markets(self):
        """Test registering markets for ice hockey."""
        # Act
        SportMarketRegistrar.register_ice_hockey_markets()

        # Assert
        ice_hockey_markets = SportMarketRegistry.get_market_mapping(Sport.ICE_HOCKEY.value)

        # Basic markets
        assert "1x2" in ice_hockey_markets
        assert "home_away" in ice_hockey_markets
        assert "dnb" in ice_hockey_markets
        assert "btts" in ice_hockey_markets
        assert "double_chance" in ice_hockey_markets

        # Over/Under markets
        assert "over_under_5_5" in ice_hockey_markets

    def test_register_baseball_markets(self):
        """Test registering markets for baseball."""
        # Act
        SportMarketRegistrar.register_baseball_markets()

        # Assert
        baseball_markets = SportMarketRegistry.get_market_mapping(Sport.BASEBALL.value)

        # Basic markets
        assert "1x2" in baseball_markets
        assert "home_away" in baseball_markets

        # Over/Under markets
        assert "over_under_7_5" in baseball_markets

    def test_register_american_football_markets(self):
        """Test registering markets for American Football."""
        # Act
        SportMarketRegistrar.register_american_football_markets()

        # Assert
        american_football_markets = SportMarketRegistry.get_market_mapping(Sport.AMERICAN_FOOTBALL.value)

        # Basic markets
        assert "1x2" in american_football_markets
        assert "home_away" in american_football_markets

        # Over/Under markets
        assert "over_under_45_5" in american_football_markets
        assert "over_under_25_5" in american_football_markets
        assert "over_under_60_5" in american_football_markets

    def test_register_handball_markets(self):
        """Test registering markets for handball (regression guard: market registry was empty for handball)."""
        SportMarketRegistrar.register_handball_markets()

        handball_markets = SportMarketRegistry.get_market_mapping(Sport.HANDBALL.value)

        assert "1x2" in handball_markets
        assert "home_away" in handball_markets
        assert "dnb" in handball_markets
        assert "double_chance" in handball_markets
        assert "over_under_40_5" in handball_markets
        assert "handicap_-9_5" in handball_markets

    def test_register_volleyball_markets(self):
        """Test registering markets for volleyball (Home/Away, O/U+AH Sets/Points, Correct Score)."""
        SportMarketRegistrar.register_volleyball_markets()

        m = SportMarketRegistry.get_market_mapping(Sport.VOLLEYBALL.value)

        assert "home_away" in m
        assert "over_under_sets_3_5" in m
        assert "over_under_points_184_5" in m
        assert "asian_handicap_+2_5_sets" in m
        assert "asian_handicap_-2_5_sets" in m
        assert "asian_handicap_+2_5_points" in m
        assert "asian_handicap_-9_5_points" in m
        assert "correct_score_3_0" in m

    def test_register_cricket_markets(self):
        """Test registering markets for cricket (single Home/Away market)."""
        SportMarketRegistrar.register_cricket_markets()

        m = SportMarketRegistry.get_market_mapping(Sport.CRICKET.value)

        assert "home_away" in m

    def test_register_all_markets(self):
        """Test registering all markets for all sports."""
        # Act
        with patch.object(SportMarketRegistrar, "register_football_markets") as mock_football:
            with patch.object(SportMarketRegistrar, "register_tennis_markets") as mock_tennis:
                with patch.object(SportMarketRegistrar, "register_basketball_markets") as mock_basketball:
                    with patch.object(SportMarketRegistrar, "register_rugby_league_markets") as mock_rugby_league:
                        with patch.object(SportMarketRegistrar, "register_rugby_union_markets") as mock_rugby_union:
                            with patch.object(SportMarketRegistrar, "register_ice_hockey_markets") as mock_ice_hockey:
                                with patch.object(SportMarketRegistrar, "register_baseball_markets") as mock_baseball:
                                    with patch.object(
                                        SportMarketRegistrar, "register_american_football_markets"
                                    ) as mock_american_football:
                                        with patch.object(
                                            SportMarketRegistrar, "register_handball_markets"
                                        ) as mock_handball:
                                            with patch.object(
                                                SportMarketRegistrar, "register_volleyball_markets"
                                            ) as mock_volleyball:
                                                with patch.object(
                                                    SportMarketRegistrar, "register_cricket_markets"
                                                ) as mock_cricket:
                                                    SportMarketRegistrar.register_all_markets()

        # Assert
        mock_football.assert_called_once()
        mock_tennis.assert_called_once()
        mock_basketball.assert_called_once()
        mock_rugby_league.assert_called_once()
        mock_rugby_union.assert_called_once()
        mock_ice_hockey.assert_called_once()
        mock_baseball.assert_called_once()
        mock_american_football.assert_called_once()
        mock_handball.assert_called_once()
        mock_volleyball.assert_called_once()
        mock_cricket.assert_called_once()

    def test_register_all_markets_integration(self):
        """Test registering all markets in an integration test"""
        # Act
        SportMarketRegistrar.register_all_markets()

        # Assert - Check that all sports have markets registered
        for sport in Sport:
            markets = SportMarketRegistry.get_market_mapping(sport.value)
            assert markets, f"No markets registered for {sport.name}"

        # Check specific markets for each sport to ensure they were properly registered
        assert "1x2" in SportMarketRegistry.get_market_mapping(Sport.FOOTBALL.value)
        assert "match_winner" in SportMarketRegistry.get_market_mapping(Sport.TENNIS.value)
        assert "home_away" in SportMarketRegistry.get_market_mapping(Sport.BASKETBALL.value)
        assert "1x2" in SportMarketRegistry.get_market_mapping(Sport.RUGBY_LEAGUE.value)
        assert "double_chance" in SportMarketRegistry.get_market_mapping(Sport.RUGBY_UNION.value)
        assert "btts" in SportMarketRegistry.get_market_mapping(Sport.ICE_HOCKEY.value)
        assert "home_away" in SportMarketRegistry.get_market_mapping(Sport.BASEBALL.value)
        assert "home_away" in SportMarketRegistry.get_market_mapping(Sport.AMERICAN_FOOTBALL.value)
        assert "1x2" in SportMarketRegistry.get_market_mapping(Sport.HANDBALL.value)
        assert "home_away" in SportMarketRegistry.get_market_mapping(Sport.VOLLEYBALL.value)


def test_market_lambda_forwards_history_reference():
    extractor = MagicMock()
    extractor.extract_market_odds = AsyncMock(return_value=[])
    func = SportMarketRegistrar.create_market_lambda("1X2", odds_labels=["1", "X", "2"])
    reference = datetime(2026, 1, 4, 18, 30)

    asyncio.run(func(extractor, "page", "FullTime", True, None, False, "football", history_reference=reference))

    assert extractor.extract_market_odds.await_args.kwargs["history_reference"] == reference


class TestLineLabels:
    """The registry builds each line label the way the page shows it (checked live on 2026-09-29)."""

    def setup_method(self):
        SportMarketRegistry._registry = {}
        SportMarketRegistrar.register_all_markets()

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("7_0", "7"),
            ("10_0", "10"),
            ("-21_0", "-21"),
            ("-1_75", "-1.75"),
            ("+0_5", "+0.5"),
            ("184_5", "184.5"),
            ("+1", "+1"),
            ("0", "0"),
        ],
    )
    def test_format_line_number_drops_a_zero_decimal(self, raw, expected):
        assert format_line_number(raw) == expected

    @pytest.mark.parametrize(
        ("sport", "market", "label"),
        [
            (Sport.BASEBALL, "over_under_7_0", "Over/Under +7"),
            (Sport.BASEBALL, "over_under_7_5", "Over/Under +7.5"),
            (Sport.TENNIS, "asian_handicap_-1_0_sets", "Asian Handicap -1"),
            (Sport.TENNIS, "asian_handicap_0_sets", "Asian Handicap 0"),
            (Sport.TENNIS, "asian_handicap_+3_5_games", "Asian Handicap +3.5"),
            (Sport.TENNIS, "over_under_games_7_0", "Over/Under +7"),
            (Sport.TENNIS, "over_under_games_39_5", "Over/Under +39.5"),
            (Sport.TENNIS, "over_under_sets_2_5", "Over/Under +2.5"),
            (Sport.VOLLEYBALL, "over_under_points_184_5", "Over/Under +184.5"),
            (Sport.VOLLEYBALL, "asian_handicap_+2_5_sets", "Asian Handicap +2.5"),
            (Sport.AMERICAN_FOOTBALL, "asian_handicap_-21_0", "Asian Handicap -21"),
            (Sport.FOOTBALL, "asian_handicap_-1", "Asian Handicap -1"),
            (Sport.FOOTBALL, "asian_handicap_+0_25", "Asian Handicap +0.25"),
            (Sport.FOOTBALL, "over_under_2_5", "Over/Under +2.5"),
            (Sport.FOOTBALL, "european_handicap_-1", "European Handicap -1"),
        ],
    )
    def test_line_label_is_the_one_the_page_shows(self, sport, market, label):
        assert SportMarketRegistry.get_market_mapping(sport.value)[market].specific_market == label

    def test_no_label_ends_in_a_zero_decimal_or_an_axis_word(self):
        labels = [
            method.specific_market
            for sport in Sport
            for method in SportMarketRegistry.get_market_mapping(sport.value).values()
            if method.specific_market
        ]

        assert labels
        assert [
            label for label in labels if label.endswith(".0") or label.split()[-1] in {"Sets", "Games", "Points"}
        ] == []

    def test_create_market_lambda_carries_its_labels(self):
        method = SportMarketRegistrar.create_market_lambda("Over/Under", "Over/Under +2.5", ["odds_over", "odds_under"])

        assert (method.main_market, method.specific_market) == ("Over/Under", "Over/Under +2.5")
        assert MarketGrouping().get_main_market_info(method) == {
            "main_market": "Over/Under",
            "odds_labels": ["odds_over", "odds_under"],
        }

    def test_tennis_refuses_the_lines_its_sets_and_games_markets_share(self):
        assert set(SportMarketRegistry.ambiguous_markets(Sport.TENNIS.value)) == {
            *(f"over_under_{axis}_{n}_5" for axis in ("sets", "games") for n in range(6, 11)),
            *(f"asian_handicap_{sign}2_5_{axis}" for sign in "+-" for axis in ("sets", "games")),
        }

    def test_volleyball_refuses_the_handicap_lines_its_sets_and_points_markets_share(self):
        assert set(SportMarketRegistry.ambiguous_markets(Sport.VOLLEYBALL.value)) == {
            f"asian_handicap_{sign}{n}_5_{axis}" for sign in "+-" for n in (1, 2) for axis in ("sets", "points")
        }

    def test_a_refused_market_names_the_market_sharing_its_line(self):
        assert SportMarketRegistry.ambiguous_markets(Sport.TENNIS.value)["over_under_sets_6_5"] == (
            "over_under_games_6_5",
        )

    @pytest.mark.parametrize("sport", [sport for sport in Sport if sport not in (Sport.TENNIS, Sport.VOLLEYBALL)])
    def test_other_sports_refuse_no_line(self, sport):
        assert SportMarketRegistry.ambiguous_markets(sport.value) == {}
