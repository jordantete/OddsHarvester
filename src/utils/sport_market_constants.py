from enum import Enum

class Sport(Enum):
    """Supported sports."""
    FOOTBALL = "football"
    TENNIS = "tennis"

class FootballMarket(Enum):
    """Football-specific markets."""
    ONE_X_TWO = "1x2"
    BTTS = "btts"
    DOUBLE_CHANCE = "double_chance"
    DNB = "dnb"

class FootballOverUnderMarket(Enum):
    """Over/Under market values (from 0.5 to 6.5) for football."""
    OVER_UNDER_0_5 = "over_under_0_5"
    OVER_UNDER_1 = "over_under_1"
    OVER_UNDER_1_5 = "over_under_1_5"
    OVER_UNDER_2 = "over_under_2"
    OVER_UNDER_2_5 = "over_under_2_5"
    OVER_UNDER_3 = "over_under_3"
    OVER_UNDER_3_5 = "over_under_3_5"
    OVER_UNDER_4 = "over_under_4"
    OVER_UNDER_4_5 = "over_under_4_5"
    OVER_UNDER_5 = "over_under_5"
    OVER_UNDER_5_5 = "over_under_5_5"
    OVER_UNDER_6 = "over_under_6"
    OVER_UNDER_6_5 = "over_under_6_5"

class FootballEuropeanHandicapMarket(Enum):
    """European Handicap market values (-4 to +4) for football."""
    HANDICAP_MINUS_4 = "european_handicap_-4"
    HANDICAP_MINUS_3 = "european_handicap_-3"
    HANDICAP_MINUS_2 = "european_handicap_-2"
    HANDICAP_MINUS_1 = "european_handicap_-1"
    HANDICAP_PLUS_1 = "european_handicap_1"
    HANDICAP_PLUS_2 = "european_handicap_2"
    HANDICAP_PLUS_3 = "european_handicap_3"
    HANDICAP_PLUS_4 = "european_handicap_4"

class TennisMarket(Enum):
    """Tennis-specific markets."""
    MATCH_WINNER = "match_winner"  # Home/Away

class TennisOverUnderSetsMarket(Enum):
    """Over/Under sets betting markets."""
    OVER_UNDER_2_5 = "over_under_sets_2_5"

class TennisOverUnderGamesMarket(Enum):
    """Over/Under total games betting markets (16.5 to 24.5)."""
    OVER_UNDER_16_5 = "over_under_games_16_5"
    OVER_UNDER_17_5 = "over_under_games_17_5"
    OVER_UNDER_18_5 = "over_under_games_18_5"
    OVER_UNDER_19_5 = "over_under_games_19_5"
    OVER_UNDER_20_5 = "over_under_games_20_5"
    OVER_UNDER_21_5 = "over_under_games_21_5"
    OVER_UNDER_22_5 = "over_under_games_22_5"
    OVER_UNDER_23_5 = "over_under_games_23_5"
    OVER_UNDER_24_5 = "over_under_games_24_5"

class TennisAsianHandicapGamesMarket(Enum):
    """Asian Handicap markets in games (+2.5 to +8.5)."""
    HANDICAP_PLUS_2_5 = "asian_handicap_games_2_5"
    HANDICAP_PLUS_3_5 = "asian_handicap_games_3_5"
    HANDICAP_PLUS_4_5 = "asian_handicap_games_4_5"
    HANDICAP_PLUS_5_5 = "asian_handicap_games_5_5"
    HANDICAP_PLUS_6_5 = "asian_handicap_games_6_5"
    HANDICAP_PLUS_7_5 = "asian_handicap_games_7_5"
    HANDICAP_PLUS_8_5 = "asian_handicap_games_8_5"

class TennisCorrectScoreMarket(Enum):
    """Correct Score markets in tennis (best of 3 sets)."""
    CORRECT_SCORE_2_0 = "correct_score_2_0"
    CORRECT_SCORE_2_1 = "correct_score_2_1"
    CORRECT_SCORE_0_2 = "correct_score_0_2"
    CORRECT_SCORE_1_2 = "correct_score_1_2"