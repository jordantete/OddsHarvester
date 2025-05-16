from src.utils.sport_market_constants import (
    Sport, FootballOverUnderMarket, FootballEuropeanHandicapMarket, FootballAsianHandicapMarket,
    TennisOverUnderSetsMarket, TennisOverUnderGamesMarket, TennisAsianHandicapGamesMarket, TennisCorrectScoreMarket,
    BasketballOverUnderMarket, BasketballAsianHandicapMarket,
    RugbyLeagueMarket, RugbyUnionMarket
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
        return lambda extractor, page, period="FullTime", scrape_odds_history=False, target_bookmaker=None: extractor.extract_market_odds(
            page=page, 
            main_market=main_market, 
            specific_market=specific_market, 
            period=period, 
            odds_labels=odds_labels,
            scrape_odds_history=scrape_odds_history,
            target_bookmaker=target_bookmaker
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
        
        # Register Asian Handicap Markets
        for handicap in FootballAsianHandicapMarket:
            raw_handicap = handicap.value.replace("asian_handicap_", "")
            formatted_handicap = raw_handicap.replace("_", ".")
            SportMarketRegistry.register(Sport.FOOTBALL, {
                handicap.value: cls.create_market_lambda(
                    main_market="Asian Handicap",
                    specific_market=f"Asian Handicap {formatted_handicap}",
                    odds_labels=["team1_handicap", "team2_handicap"]
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
    def register_basketball_markets(cls):
        """Registers all basketball betting markets."""
        SportMarketRegistry.register(Sport.BASKETBALL, {
            "1x2": cls.create_market_lambda("1X2", odds_labels=["1", "X", "2"]),
            "home_away": cls.create_market_lambda("Home/Away", odds_labels=["1", "2"]),
        })

        # Register Over/Under Games Markets
        for over_under in BasketballOverUnderMarket:
            numeric_part = over_under.value.replace("over_under_games_", "").replace("_", ".")
            SportMarketRegistry.register(Sport.BASKETBALL, {
                over_under.value: cls.create_market_lambda(
                    main_market="Over/Under",
                    specific_market=f"Over/Under +{numeric_part}",
                    odds_labels=["odds_over", "odds_under"]
                )
            })

        # Register Asian Handicap Markets
        for handicap in BasketballAsianHandicapMarket:
            numeric_part = handicap.value.replace("asian_handicap_games_", "").replace("_games", "").replace("_", ".")
            specific_market = f"Asian Handicap {numeric_part}"
            SportMarketRegistry.register(Sport.BASKETBALL, {
                handicap.value: cls.create_market_lambda(
                    main_market="Asian Handicap",
                    specific_market=specific_market,
                    odds_labels=["handicap_team_1", "handicap_team_2"]
                )
            })

    @classmethod
    def register_rugby_league_markets(cls):
        """Registers all rugby league betting markets."""
        SportMarketRegistry.register(Sport.RUGBY_LEAGUE, {
            "1x2": cls.create_market_lambda("1X2", odds_labels=["1", "X", "2"]),
            "home_away": cls.create_market_lambda("Home/Away", odds_labels=["1", "2"]),
            "dnb": cls.create_market_lambda("Draw No Bet", odds_labels=["dnb_team1", "dnb_team2"]),
            "double_chance": cls.create_market_lambda("Double Chance", odds_labels=["1X", "12", "X2"]),
        })

        # Over/Under Markets
        for over_under in [
            RugbyLeagueMarket.OVER_UNDER_32_5,
            RugbyLeagueMarket.OVER_UNDER_36_5,
            RugbyLeagueMarket.OVER_UNDER_40_5,
            RugbyLeagueMarket.OVER_UNDER_44_5,
            RugbyLeagueMarket.OVER_UNDER_48_5,
            RugbyLeagueMarket.OVER_UNDER_52_5,
        ]:
            numeric_part = over_under.value.replace("over_under_", "").replace("_", ".")
            SportMarketRegistry.register(Sport.RUGBY_LEAGUE, {
                over_under.value: cls.create_market_lambda(
                    main_market="Over/Under",
                    specific_market=f"Over/Under +{numeric_part}",
                    odds_labels=["odds_over", "odds_under"]
                )
            })

        # Handicap Markets
        for handicap in [
            RugbyLeagueMarket.HANDICAP_MINUS_4_5,
            RugbyLeagueMarket.HANDICAP_PLUS_4_5,
            RugbyLeagueMarket.HANDICAP_MINUS_8_5,
            RugbyLeagueMarket.HANDICAP_PLUS_8_5,
            RugbyLeagueMarket.HANDICAP_MINUS_12_5,
            RugbyLeagueMarket.HANDICAP_PLUS_12_5,
            RugbyLeagueMarket.HANDICAP_MINUS_16_5,
            RugbyLeagueMarket.HANDICAP_PLUS_16_5,
        ]:
            numeric_part = handicap.value.replace("handicap_", "").replace("_", ".")
            SportMarketRegistry.register(Sport.RUGBY_LEAGUE, {
                handicap.value: cls.create_market_lambda(
                    main_market="Handicap",
                    specific_market=f"Handicap {numeric_part}",
                    odds_labels=["handicap_team_1", "handicap_team_2"]
                )
            })

    @classmethod
    def register_rugby_union_markets(cls):
        """Registers all rugby union betting markets."""
        SportMarketRegistry.register(Sport.RUGBY_UNION, {
            "1x2": cls.create_market_lambda("1X2", odds_labels=["1", "X", "2"]),
            "home_away": cls.create_market_lambda("Home/Away", odds_labels=["1", "2"]),
            "dnb": cls.create_market_lambda("Draw No Bet", odds_labels=["dnb_team1", "dnb_team2"]),
            "double_chance": cls.create_market_lambda("Double Chance", odds_labels=["1X", "12", "X2"]),
        })

        # Over/Under Markets
        for over_under in [
            RugbyUnionMarket.OVER_UNDER_35_5,
            RugbyUnionMarket.OVER_UNDER_39_5,
            RugbyUnionMarket.OVER_UNDER_43_5,
            RugbyUnionMarket.OVER_UNDER_47_5,
            RugbyUnionMarket.OVER_UNDER_51_5,
            RugbyUnionMarket.OVER_UNDER_55_5,
        ]:
            numeric_part = over_under.value.replace("over_under_", "").replace("_", ".")
            SportMarketRegistry.register(Sport.RUGBY_UNION, {
                over_under.value: cls.create_market_lambda(
                    main_market="Over/Under",
                    specific_market=f"Over/Under +{numeric_part}",
                    odds_labels=["odds_over", "odds_under"]
                )
            })

        # Handicap Markets
        for handicap in [
            RugbyUnionMarket.HANDICAP_MINUS_5_5,
            RugbyUnionMarket.HANDICAP_PLUS_5_5,
            RugbyUnionMarket.HANDICAP_MINUS_9_5,
            RugbyUnionMarket.HANDICAP_PLUS_9_5,
            RugbyUnionMarket.HANDICAP_MINUS_13_5,
            RugbyUnionMarket.HANDICAP_PLUS_13_5,
            RugbyUnionMarket.HANDICAP_MINUS_17_5,
            RugbyUnionMarket.HANDICAP_PLUS_17_5,
        ]:
            numeric_part = handicap.value.replace("handicap_", "").replace("_", ".")
            SportMarketRegistry.register(Sport.RUGBY_UNION, {
                handicap.value: cls.create_market_lambda(
                    main_market="Handicap",
                    specific_market=f"Handicap {numeric_part}",
                    odds_labels=["handicap_team_1", "handicap_team_2"]
                )
            })

    @classmethod
    def register_all_markets(cls):
        """Registers all sports markets."""
        cls.register_football_markets()
        cls.register_tennis_markets()
        cls.register_basketball_markets()
        cls.register_rugby_league_markets()
        cls.register_rugby_union_markets()