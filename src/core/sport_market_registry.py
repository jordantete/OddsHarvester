from utils.sport_market_constants import (
    Sport, FootballOverUnderMarket, FootballEuropeanHandicapMarket, 
    TennisOverUnderSetsMarket, TennisOverUnderGamesMarket, TennisAsianHandicapGamesMarket, TennisCorrectScoreMarket
)

class MarketRegistry:
    """Registry to dynamically store market mappings for each sport."""

    _registry = {}

    @classmethod
    def register(cls, sport: Sport, market_mapping: dict):
        """Register a market mapping for a sport."""
        cls._registry[sport.value] = market_mapping

    @classmethod
    def get_market_mapping(cls, sport: str) -> dict:
        """Retrieve market mappings for a given sport."""
        return cls._registry.get(sport, {})

# Registering Football Markets
MarketRegistry.register(Sport.FOOTBALL, {
    "1x2": lambda extractor, period="FullTime": extractor.extract_market_odds(
        main_market="1X2", period=period, odds_labels=["1", "X", "2"]
    ),
    "btts": lambda extractor, period="FullTime": extractor.extract_market_odds(
        main_market="Both Teams to Score", period=period, odds_labels=["btts_yes", "btts_no"]
    ),
    "double_chance": lambda extractor, period="FullTime": extractor.extract_market_odds(
        main_market="Double Chance", period=period, odds_labels=["1X", "12", "X2"]
    ),
    "dnb": lambda extractor, period="FullTime": extractor.extract_market_odds(
        main_market="Draw No Bet",period= period, odds_labels=["dnb_team1", "dnb_team2"]
    ),
})

for over_under in FootballOverUnderMarket:
    MarketRegistry._registry[Sport.FOOTBALL.value][over_under.value] = lambda extractor, period="FullTime", ou=over_under: extractor.extract_market_odds(
        main_market="Over/Under", 
        specific_market=f"Over/Under +{ou.value.replace('over_under_', '').replace('_', '.')}",
        period=period, 
        odds_labels=["odds_over", "odds_under"]
    )

for handicap in FootballEuropeanHandicapMarket:
    MarketRegistry._registry[Sport.FOOTBALL.value][handicap.value] = lambda extractor, period="FullTime", h=handicap: extractor.extract_market_odds(
        main_market="European Handicap", 
        specific_market=f"European Handicap {h.value.split('_')[-1]}", 
        period=period,
        odds_labels=["team1_handicap", "draw_handicap", "team2_handicap"]
    )

# Registering Tennis Markets
MarketRegistry.register(Sport.TENNIS, {
    "match_winner": lambda extractor, period="FullTime": extractor.extract_market_odds(
        main_market="Home Away", 
        period=period, 
        odds_labels=["player_1", "player_2"]
    ),
})

for over_under in TennisOverUnderSetsMarket:
    MarketRegistry._registry[Sport.TENNIS.value][over_under.value] = lambda extractor, period="FullTime", ou=over_under: extractor.extract_market_odds(
        main_market="Over/Under Sets", 
        specific_market=f"Over/Under +{ou.value.split('_')[-1].replace('_', '.')}", 
        period=period, 
        odds_labels=["odds_over", "odds_under"]
    )

for over_under in TennisOverUnderGamesMarket:
    MarketRegistry._registry[Sport.TENNIS.value][over_under.value] = lambda extractor, period="FullTime", ou=over_under: extractor.extract_market_odds(
        main_market="Over/Under Games", 
        specific_market=f"Over/Under +{ou.value.split('_')[-1].replace('_', '.')}", 
        period=period, 
        odds_labels=["odds_over", "odds_under"]
    )

for handicap in TennisAsianHandicapGamesMarket:
    MarketRegistry._registry[Sport.TENNIS.value][handicap.value] = lambda extractor, period="FullTime", h=handicap: extractor.extract_market_odds(
        main_market="Asian Handicap Games", 
        specific_market=f"Asian Handicap +{h.value.split('_')[-1].replace('_', '.')}", 
        period=period, 
        odds_labels=["handicap_player_1", "handicap_player_2"]
    )

for correct_score in TennisCorrectScoreMarket:
    MarketRegistry._registry[Sport.TENNIS.value][correct_score.value] = lambda extractor, period="FullTime", cs=correct_score: extractor.extract_market_odds(
        main_market="Correct Score", 
        specific_market=f"Correct Score {cs.value.split('_')[-1]}", 
        period=period, 
        odds_labels=["correct_score"]
    )