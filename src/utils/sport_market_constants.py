from enum import Enum


class Sport(Enum):
    """Supported sports."""

    FOOTBALL = "football"
    TENNIS = "tennis"
    BASKETBALL = "basketball"
    RUGBY_LEAGUE = "rugby-league"
    RUGBY_UNION = "rugby-union"
    ICE_HOCKEY = "ice-hockey"
    BASEBALL = "baseball"


class FootballMarket(Enum):
    """Football-specific markets."""

    ONE_X_TWO = "1x2"
    BTTS = "btts"
    DOUBLE_CHANCE = "double_chance"
    DNB = "dnb"


class BaseballMarket(Enum):
    """Football-specific markets."""

    ONE_X_TWO = "1x2"
    HOME_AWAY = "home_away"


class BaseballOverUnderMarket(Enum):
    OVER_UNDER_6_5 = "over_under_6_5"
    OVER_UNDER_7_0 = "over_under_7_0"
    OVER_UNDER_7_5 = "over_under_7_5"
    OVER_UNDER_8_0 = "over_under_8_0"
    OVER_UNDER_8_5 = "over_under_8_5"
    OVER_UNDER_9_0 = "over_under_9_0"
    OVER_UNDER_9_5 = "over_under_9_5"
    OVER_UNDER_10_0 = "over_under_10_0"
    OVER_UNDER_10_5 = "over_under_10_5"
    OVER_UNDER_11_0 = "over_under_11_0"
    OVER_UNDER_11_5 = "over_under_11_5"


class FootballOverUnderMarket(Enum):
    """Over/Under market values (from 0.5 to 6.5) for football."""

    OVER_UNDER_0_5 = "over_under_0_5"
    OVER_UNDER_1 = "over_under_1"
    OVER_UNDER_1_25 = "over_under_1_25"
    OVER_UNDER_1_5 = "over_under_1_5"
    OVER_UNDER_1_75 = "over_under_1_75"
    OVER_UNDER_2 = "over_under_2"
    OVER_UNDER_2_25 = "over_under_2_25"
    OVER_UNDER_2_5 = "over_under_2_5"
    OVER_UNDER_2_75 = "over_under_2_75"
    OVER_UNDER_3 = "over_under_3"
    OVER_UNDER_3_25 = "over_under_3_25"
    OVER_UNDER_3_5 = "over_under_3_5"
    OVER_UNDER_3_75 = "over_under_3_75"
    OVER_UNDER_4 = "over_under_4"
    OVER_UNDER_4_25 = "over_under_4_25"
    OVER_UNDER_4_5 = "over_under_4_5"
    OVER_UNDER_4_75 = "over_under_4_75"
    OVER_UNDER_5 = "over_under_5"
    OVER_UNDER_5_25 = "over_under_5_25"
    OVER_UNDER_5_5 = "over_under_5_5"
    OVER_UNDER_5_75 = "over_under_5_75"
    OVER_UNDER_6 = "over_under_6"
    OVER_UNDER_6_25 = "over_under_6_25"
    OVER_UNDER_6_5 = "over_under_6_5"
    OVER_UNDER_6_75 = "over_under_6_75"
    OVER_UNDER_7_5 = "over_under_7_5"
    OVER_UNDER_8_5 = "over_under_8_5"


class FootballEuropeanHandicapMarket(Enum):
    """European Handicap market values (-4 to +4) for football."""

    HANDICAP_MINUS_4 = "european_handicap_-4"
    HANDICAP_MINUS_3 = "european_handicap_-3"
    HANDICAP_MINUS_2 = "european_handicap_-2"
    HANDICAP_MINUS_1 = "european_handicap_-1"
    HANDICAP_PLUS_1 = "european_handicap_+1"
    HANDICAP_PLUS_2 = "european_handicap_+2"
    HANDICAP_PLUS_3 = "european_handicap_+3"
    HANDICAP_PLUS_4 = "european_handicap_+4"


class FootballAsianHandicapMarket(Enum):
    """Asian Handicap market values for football (including quarters)."""

    HANDICAP_MINUS_4 = "asian_handicap_-4"
    HANDICAP_MINUS_3_75 = "asian_handicap_-3_75"
    HANDICAP_MINUS_3_5 = "asian_handicap_-3_5"
    HANDICAP_MINUS_3_25 = "asian_handicap_-3_25"
    HANDICAP_MINUS_3 = "asian_handicap_-3"
    HANDICAP_MINUS_2_75 = "asian_handicap_-2_75"
    HANDICAP_MINUS_2_5 = "asian_handicap_-2_5"
    HANDICAP_MINUS_2_25 = "asian_handicap_-2_25"
    HANDICAP_MINUS_2 = "asian_handicap_-2"
    HANDICAP_MINUS_1_75 = "asian_handicap_-1_75"
    HANDICAP_MINUS_1_5 = "asian_handicap_-1_5"
    HANDICAP_MINUS_1_25 = "asian_handicap_-1_25"
    HANDICAP_MINUS_1 = "asian_handicap_-1"
    HANDICAP_MINUS_0_75 = "asian_handicap_-0_75"
    HANDICAP_MINUS_0_5 = "asian_handicap_-0_5"
    HANDICAP_MINUS_0_25 = "asian_handicap_-0_25"
    HANDICAP_ZERO = "asian_handicap_0"
    HANDICAP_PLUS_0_25 = "asian_handicap_+0_25"
    HANDICAP_PLUS_0_5 = "asian_handicap_+0_5"
    HANDICAP_PLUS_0_75 = "asian_handicap_+0_75"
    HANDICAP_PLUS_1 = "asian_handicap_+1"
    HANDICAP_PLUS_1_25 = "asian_handicap_+1_25"
    HANDICAP_PLUS_1_5 = "asian_handicap_+1_5"
    HANDICAP_PLUS_1_75 = "asian_handicap_+1_75"
    HANDICAP_PLUS_2 = "asian_handicap_+2"


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
    OVER_UNDER_25_5 = "over_under_games_25_5"


class TennisAsianHandicapGamesMarket(Enum):
    """Asian Handicap markets in games (+2.5 to +8.5)."""

    HANDICAP_PLUS_2_5 = "asian_handicap_games_+2_5_games"
    HANDICAP_PLUS_3_5 = "asian_handicap_games_+3_5_games"
    HANDICAP_PLUS_4_5 = "asian_handicap_games_+4_5_games"
    HANDICAP_PLUS_5_5 = "asian_handicap_games_+5_5_games"
    HANDICAP_PLUS_6_5 = "asian_handicap_games_+6_5_games"
    HANDICAP_PLUS_7_5 = "asian_handicap_games_+7_5_games"
    HANDICAP_PLUS_8_5 = "asian_handicap_games_+8_5_games"
    HANDICAP_MINUS_2_5 = "asian_handicap_games_-2_5_games"
    HANDICAP_MINUS_3_5 = "asian_handicap_games_-3_5_games"
    HANDICAP_MINUS_4_5 = "asian_handicap_games_-4_5_games"


class TennisCorrectScoreMarket(Enum):
    """Correct Score markets in tennis (best of 3 sets)."""

    CORRECT_SCORE_2_0 = "correct_score_2_0"
    CORRECT_SCORE_2_1 = "correct_score_2_1"
    CORRECT_SCORE_0_2 = "correct_score_0_2"
    CORRECT_SCORE_1_2 = "correct_score_1_2"


class BasketballMarket(Enum):
    """Basketball-specific markets."""

    ONE_X_TWO = "1x2"
    home_away = "home_away"  # Match winner (FT including OT)


class BasketballOverUnderMarket(Enum):
    """Over/Under total points betting markets (from 220.5 to 245.5)."""

    OVER_UNDER_220_5 = "over_under_games_220_5"
    OVER_UNDER_221_5 = "over_under_games_221_5"
    OVER_UNDER_222_5 = "over_under_games_222_5"
    OVER_UNDER_223_5 = "over_under_games_223_5"
    OVER_UNDER_224_5 = "over_under_games_224_5"
    OVER_UNDER_225_5 = "over_under_games_225_5"
    OVER_UNDER_226_5 = "over_under_games_226_5"
    OVER_UNDER_227_5 = "over_under_games_227_5"
    OVER_UNDER_228_5 = "over_under_games_228_5"
    OVER_UNDER_229_5 = "over_under_games_229_5"
    OVER_UNDER_230_5 = "over_under_games_230_5"
    OVER_UNDER_231_5 = "over_under_games_231_5"
    OVER_UNDER_232_5 = "over_under_games_232_5"
    OVER_UNDER_233_5 = "over_under_games_233_5"
    OVER_UNDER_234_5 = "over_under_games_234_5"
    OVER_UNDER_235_5 = "over_under_games_235_5"
    OVER_UNDER_236_5 = "over_under_games_236_5"
    OVER_UNDER_237_5 = "over_under_games_237_5"
    OVER_UNDER_238_5 = "over_under_games_238_5"
    OVER_UNDER_239_5 = "over_under_games_239_5"
    OVER_UNDER_240_5 = "over_under_games_240_5"
    OVER_UNDER_241_5 = "over_under_games_241_5"
    OVER_UNDER_242_5 = "over_under_games_242_5"
    OVER_UNDER_243_5 = "over_under_games_243_5"
    OVER_UNDER_244_5 = "over_under_games_244_5"
    OVER_UNDER_245_5 = "over_under_games_245_5"


class BasketballAsianHandicapMarket(Enum):
    """Asian Handicap markets in basketball games (from -25.5 to +25.5 in 1-point steps)."""

    HANDICAP_MINUS_25_5 = "asian_handicap_games_-25_5_games"
    HANDICAP_MINUS_24_5 = "asian_handicap_games_-24_5_games"
    HANDICAP_MINUS_23_5 = "asian_handicap_games_-23_5_games"
    HANDICAP_MINUS_22_5 = "asian_handicap_games_-22_5_games"
    HANDICAP_MINUS_21_5 = "asian_handicap_games_-21_5_games"
    HANDICAP_MINUS_20_5 = "asian_handicap_games_-20_5_games"
    HANDICAP_MINUS_19_5 = "asian_handicap_games_-19_5_games"
    HANDICAP_MINUS_18_5 = "asian_handicap_games_-18_5_games"
    HANDICAP_MINUS_17_5 = "asian_handicap_games_-17_5_games"
    HANDICAP_MINUS_16_5 = "asian_handicap_games_-16_5_games"
    HANDICAP_MINUS_15_5 = "asian_handicap_games_-15_5_games"
    HANDICAP_MINUS_14_5 = "asian_handicap_games_-14_5_games"
    HANDICAP_MINUS_13_5 = "asian_handicap_games_-13_5_games"
    HANDICAP_MINUS_12_5 = "asian_handicap_games_-12_5_games"
    HANDICAP_MINUS_11_5 = "asian_handicap_games_-11_5_games"
    HANDICAP_MINUS_10_5 = "asian_handicap_games_-10_5_games"
    HANDICAP_MINUS_9_5 = "asian_handicap_games_-9_5_games"
    HANDICAP_MINUS_8_5 = "asian_handicap_games_-8_5_games"
    HANDICAP_MINUS_7_5 = "asian_handicap_games_-7_5_games"
    HANDICAP_MINUS_6_5 = "asian_handicap_games_-6_5_games"
    HANDICAP_MINUS_5_5 = "asian_handicap_games_-5_5_games"
    HANDICAP_MINUS_4_5 = "asian_handicap_games_-4_5_games"
    HANDICAP_MINUS_3_5 = "asian_handicap_games_-3_5_games"
    HANDICAP_MINUS_2_5 = "asian_handicap_games_-2_5_games"
    HANDICAP_MINUS_1_5 = "asian_handicap_games_-1_5_games"
    HANDICAP_PLUS_0_5 = "asian_handicap_games_+0_5_games"
    HANDICAP_PLUS_1_5 = "asian_handicap_games_+1_5_games"
    HANDICAP_PLUS_2_5 = "asian_handicap_games_+2_5_games"
    HANDICAP_PLUS_3_5 = "asian_handicap_games_+3_5_games"
    HANDICAP_PLUS_4_5 = "asian_handicap_games_+4_5_games"
    HANDICAP_PLUS_5_5 = "asian_handicap_games_+5_5_games"
    HANDICAP_PLUS_6_5 = "asian_handicap_games_+6_5_games"
    HANDICAP_PLUS_7_5 = "asian_handicap_games_+7_5_games"
    HANDICAP_PLUS_8_5 = "asian_handicap_games_+8_5_games"
    HANDICAP_PLUS_9_5 = "asian_handicap_games_+9_5_games"
    HANDICAP_PLUS_10_5 = "asian_handicap_games_+10_5_games"
    HANDICAP_PLUS_11_5 = "asian_handicap_games_+11_5_games"
    HANDICAP_PLUS_12_5 = "asian_handicap_games_+12_5_games"
    HANDICAP_PLUS_13_5 = "asian_handicap_games_+13_5_games"
    HANDICAP_PLUS_14_5 = "asian_handicap_games_+14_5_games"
    HANDICAP_PLUS_15_5 = "asian_handicap_games_+15_5_games"
    HANDICAP_PLUS_16_5 = "asian_handicap_games_+16_5_games"
    HANDICAP_PLUS_17_5 = "asian_handicap_games_+17_5_games"
    HANDICAP_PLUS_18_5 = "asian_handicap_games_+18_5_games"
    HANDICAP_PLUS_19_5 = "asian_handicap_games_+19_5_games"
    HANDICAP_PLUS_20_5 = "asian_handicap_games_+20_5_games"
    HANDICAP_PLUS_21_5 = "asian_handicap_games_+21_5_games"
    HANDICAP_PLUS_22_5 = "asian_handicap_games_+22_5_games"
    HANDICAP_PLUS_23_5 = "asian_handicap_games_+23_5_games"
    HANDICAP_PLUS_24_5 = "asian_handicap_games_+24_5_games"
    HANDICAP_PLUS_25_5 = "asian_handicap_games_+25_5_games"


class RugbyLeagueMarket(Enum):
    """Rugby League-specific markets."""

    ONE_X_TWO = "1x2"
    HOME_AWAY = "home_away"
    DNB = "dnb"
    DOUBLE_CHANCE = "double_chance"
    OVER_UNDER_32_5 = "over_under_32_5"
    OVER_UNDER_36_5 = "over_under_36_5"
    OVER_UNDER_40_5 = "over_under_40_5"
    OVER_UNDER_41_5 = "over_under_41_5"
    OVER_UNDER_42_5 = "over_under_42_5"
    OVER_UNDER_43_5 = "over_under_43_5"
    OVER_UNDER_44_5 = "over_under_44_5"
    OVER_UNDER_45_5 = "over_under_45_5"
    OVER_UNDER_46_5 = "over_under_46_5"
    OVER_UNDER_47_5 = "over_under_47_5"
    OVER_UNDER_48_5 = "over_under_48_5"
    OVER_UNDER_49_5 = "over_under_49_5"
    OVER_UNDER_50_5 = "over_under_50_5"
    OVER_UNDER_51_5 = "over_under_51_5"
    OVER_UNDER_52_5 = "over_under_52_5"
    HANDICAP_MINUS_4_5 = "handicap_-4_5"
    HANDICAP_PLUS_4_5 = "handicap_+4_5"
    HANDICAP_MINUS_8_5 = "handicap_-8_5"
    HANDICAP_PLUS_8_5 = "handicap_+8_5"
    HANDICAP_MINUS_12_5 = "handicap_-12_5"
    HANDICAP_PLUS_12_5 = "handicap_+12_5"
    HANDICAP_MINUS_16_5 = "handicap_-16_5"
    HANDICAP_PLUS_16_5 = "handicap_+16_5"


class RugbyUnionMarket(Enum):
    """Rugby Union-specific markets."""

    ONE_X_TWO = "1x2"
    HOME_AWAY = "home_away"
    DNB = "dnb"
    DOUBLE_CHANCE = "double_chance"
    OVER_UNDER_35_5 = "over_under_35_5"
    OVER_UNDER_39_5 = "over_under_39_5"
    OVER_UNDER_43_5 = "over_under_43_5"
    OVER_UNDER_47_5 = "over_under_47_5"
    OVER_UNDER_51_5 = "over_under_51_5"
    OVER_UNDER_55_5 = "over_under_55_5"
    HANDICAP_MINUS_5_5 = "handicap_-5_5"
    HANDICAP_PLUS_5_5 = "handicap_+5_5"
    HANDICAP_MINUS_9_5 = "handicap_-9_5"
    HANDICAP_PLUS_9_5 = "handicap_+9_5"
    HANDICAP_MINUS_10_5 = "handicap_-10_5"
    HANDICAP_PLUS_10_5 = "handicap_+10_5"
    HANDICAP_MINUS_11_5 = "handicap_-11_5"
    HANDICAP_PLUS_11_5 = "handicap_+11_5"
    HANDICAP_MINUS_13_5 = "handicap_-13_5"
    HANDICAP_PLUS_13_5 = "handicap_+13_5"
    HANDICAP_MINUS_17_5 = "handicap_-17_5"
    HANDICAP_PLUS_17_5 = "handicap_+17_5"


class IceHockeyMarket(Enum):
    """Ice Hockey-specific markets."""

    ONE_X_TWO = "1x2"
    HOME_AWAY = "home_away"
    DNB = "dnb"
    BTTS = "btts"
    DOUBLE_CHANCE = "double_chance"
    OVER_UNDER_1_5 = "over_under_1_5"
    OVER_UNDER_2_5 = "over_under_2_5"
    OVER_UNDER_3_5 = "over_under_3_5"
    OVER_UNDER_4_5 = "over_under_4_5"
    OVER_UNDER_5_5 = "over_under_5_5"
    OVER_UNDER_6_5 = "over_under_6_5"
    OVER_UNDER_7_5 = "over_under_7_5"
    OVER_UNDER_8_5 = "over_under_8_5"
    OVER_UNDER_9_5 = "over_under_9_5"
    OVER_UNDER_10_5 = "over_under_10_5"
    OVER_UNDER_11_5 = "over_under_11_5"


class RugbyOverUnderMarket(Enum):
    """Over/Under market values for rugby (from 32.5 to 55.5)."""

    OVER_UNDER_32_5 = "over_under_32_5"
    OVER_UNDER_35_5 = "over_under_35_5"
    OVER_UNDER_36_5 = "over_under_36_5"
    OVER_UNDER_39_5 = "over_under_39_5"
    OVER_UNDER_40_5 = "over_under_40_5"
    OVER_UNDER_41_5 = "over_under_41_5"
    OVER_UNDER_42_5 = "over_under_42_5"
    OVER_UNDER_43_5 = "over_under_43_5"
    OVER_UNDER_44_5 = "over_under_44_5"
    OVER_UNDER_45_5 = "over_under_45_5"
    OVER_UNDER_46_5 = "over_under_46_5"
    OVER_UNDER_47_5 = "over_under_47_5"
    OVER_UNDER_48_5 = "over_under_48_5"
    OVER_UNDER_49_5 = "over_under_49_5"
    OVER_UNDER_50_5 = "over_under_50_5"
    OVER_UNDER_51_5 = "over_under_51_5"
    OVER_UNDER_52_5 = "over_under_52_5"
    OVER_UNDER_55_5 = "over_under_55_5"


class RugbyHandicapMarket(Enum):
    """Handicap market values for rugby (from -17.5 to +17.5)."""

    HANDICAP_MINUS_17_5 = "handicap_-17_5"
    HANDICAP_MINUS_16_5 = "handicap_-16_5"
    HANDICAP_MINUS_13_5 = "handicap_-13_5"
    HANDICAP_MINUS_12_5 = "handicap_-12_5"
    HANDICAP_MINUS_11_5 = "handicap_-11_5"
    HANDICAP_MINUS_10_5 = "handicap_-10_5"
    HANDICAP_MINUS_9_5 = "handicap_-9_5"
    HANDICAP_MINUS_8_5 = "handicap_-8_5"
    HANDICAP_MINUS_5_5 = "handicap_-5_5"
    HANDICAP_MINUS_4_5 = "handicap_-4_5"
    HANDICAP_PLUS_4_5 = "handicap_+4_5"
    HANDICAP_PLUS_5_5 = "handicap_+5_5"
    HANDICAP_PLUS_8_5 = "handicap_+8_5"
    HANDICAP_PLUS_9_5 = "handicap_+9_5"
    HANDICAP_PLUS_10_5 = "handicap_+10_5"
    HANDICAP_PLUS_11_5 = "handicap_+11_5"
    HANDICAP_PLUS_12_5 = "handicap_+12_5"
    HANDICAP_PLUS_13_5 = "handicap_+13_5"
    HANDICAP_PLUS_16_5 = "handicap_+16_5"
    HANDICAP_PLUS_17_5 = "handicap_+17_5"


class IceHockeyOverUnderMarket(Enum):
    """Over/Under market values for ice hockey (from 1.5 to 11.5)."""

    OVER_UNDER_1_5 = "over_under_1_5"
    OVER_UNDER_2_5 = "over_under_2_5"
    OVER_UNDER_3_5 = "over_under_3_5"
    OVER_UNDER_4_5 = "over_under_4_5"
    OVER_UNDER_5_5 = "over_under_5_5"
    OVER_UNDER_6_5 = "over_under_6_5"
    OVER_UNDER_7_5 = "over_under_7_5"
    OVER_UNDER_8_5 = "over_under_8_5"
    OVER_UNDER_9_5 = "over_under_9_5"
    OVER_UNDER_10_5 = "over_under_10_5"
    OVER_UNDER_11_5 = "over_under_11_5"
