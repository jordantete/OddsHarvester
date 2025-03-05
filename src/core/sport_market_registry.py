from utils.sport_market_constants import (
    Sport, FootballOverUnderMarket, FootballEuropeanHandicapMarket, TennisOverUnderSetsMarket, 
    TennisOverUnderGamesMarket, TennisAsianHandicapGamesMarket, TennisCorrectScoreMarket
)

class SportMarketRegistry:
    """Registry to dynamically store market mappings for each sport."""
    
    _registry = {}

    @classmethod
    def register(cls, sport: Sport, market_mapping: dict):
        """Register a market mapping for a sport."""
        if sport.value not in cls._registry:
            cls._registry[sport.value] = {}
        cls._registry[sport.value].update(market_mapping)

    @classmethod
    def get_market_mapping(cls, sport: str) -> dict:
        """Retrieve market mappings for a given sport."""
        return cls._registry.get(sport, {})

class SportMarketRegistrar:
    """Handles the registration of betting markets for different sports."""

    @staticmethod
    def create_market_lambda(main_market, specific_market=None, odds_labels=None):
        """
        Creates a lambda function for market extraction.
        """
        return lambda extractor, page, period="FullTime": extractor.extract_market_odds(
            page=page, 
            main_market=main_market, 
            specific_market=specific_market, 
            period=period, 
            odds_labels=odds_labels
        )

    @classmethod
    def register_football_markets(cls):
        """Registers all football betting markets."""
        SportMarketRegistry.register(Sport.FOOTBALL, {
            "1x2": cls.create_market_lambda("1X2", odds_labels=["1", "X", "2"]),
            "btts": cls.create_market_lambda("Both Teams to Score", odds_labels=["btts_yes", "btts_no"]),
            "double_chance": cls.create_market_lambda("Double Chance", odds_labels=["1X", "12", "X2"]),
            "dnb": cls.create_market_lambda("Draw No Bet", odds_labels=["dnb_team1", "dnb_team2"]),
        })

        # Register Over/Under Markets
        for over_under in FootballOverUnderMarket:
            SportMarketRegistry.register(Sport.FOOTBALL, {
                over_under.value: cls.create_market_lambda(
                    main_market="Over/Under",
                    specific_market=f"Over/Under +{over_under.value.replace('over_under_', '').replace('_', '.')}",
                    odds_labels=["odds_over", "odds_under"]
                )
            })

        # Register European Handicap Markets
        for handicap in FootballEuropeanHandicapMarket:
            SportMarketRegistry.register(Sport.FOOTBALL, {
                handicap.value: cls.create_market_lambda(
                    main_market="European Handicap",
                    specific_market=f"European Handicap {handicap.value.split('_')[-1]}",
                    odds_labels=["team1_handicap", "draw_handicap", "team2_handicap"]
                )
            })

    @classmethod
    def register_tennis_markets(cls):
        """Registers all tennis betting markets."""
        SportMarketRegistry.register(Sport.TENNIS, {
            "match_winner": cls.create_market_lambda("Home/Away", odds_labels=["player_1", "player_2"]),
        })

        # Register Over/Under Sets Markets
        for over_under in TennisOverUnderSetsMarket:
            numeric_part = over_under.value.replace("over_under_sets_", "").replace("_", ".")
            SportMarketRegistry.register(Sport.TENNIS, {
                over_under.value: cls.create_market_lambda(
                    main_market="Over/Under",
                    specific_market=f"Over/Under +{numeric_part} Sets",
                    odds_labels=["odds_over", "odds_under"]
                )
            })

        # Register Over/Under Games Markets
        for over_under in TennisOverUnderGamesMarket:
            numeric_part = over_under.value.replace("over_under_games_", "").replace("_", ".")
            SportMarketRegistry.register(Sport.TENNIS, {
                over_under.value: cls.create_market_lambda(
                    main_market="Over/Under",
                    specific_market=f"Over/Under +{numeric_part} Games",
                    odds_labels=["odds_over", "odds_under"]
                )
            })

        # Register Asian Handicap Games Markets
        for handicap in TennisAsianHandicapGamesMarket:
            numeric_part = handicap.value.replace("asian_handicap_games_", "").replace("_games", "").replace("_", ".")
            specific_market = f"Asian Handicap {numeric_part} Games"
            SportMarketRegistry.register(Sport.TENNIS, {
                handicap.value: cls.create_market_lambda(
                    main_market="Asian Handicap",
                    specific_market=specific_market,
                    odds_labels=["handicap_player_1", "handicap_player_2"]
                )
            })

        # Register Correct Score Markets
        for correct_score in TennisCorrectScoreMarket:
            numeric_part = correct_score.value.replace("correct_score_", "").replace("_", ":")
            specific_market = f"{numeric_part}"
            SportMarketRegistry.register(Sport.TENNIS, {
                correct_score.value: cls.create_market_lambda(
                    main_market="Correct Score",
                    specific_market=specific_market,
                    odds_labels=["correct_score"]
                )
            })

    @classmethod
    def register_all_markets(cls):
        """Registers all sports markets."""
        cls.register_football_markets()
        cls.register_tennis_markets()