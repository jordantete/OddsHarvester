import pytest

from oddsharvester.core.market_extraction.line_tokens import line_name_to_token
from oddsharvester.core.sport_market_registry import SportMarketRegistrar, SportMarketRegistry


@pytest.fixture(scope="module", autouse=True)
def registered_markets():
    SportMarketRegistry._registry = {}
    SportMarketRegistrar.register_all_markets()


@pytest.mark.parametrize(
    ("main", "name", "expected"),
    [
        ("Over/Under", "Over/Under +2.5", "over_under_2_5"),
        ("Over/Under", "Over/Under +1", "over_under_1"),
        ("Over/Under", "Over/Under +1.25", "over_under_1_25"),
        ("Asian Handicap", "Asian Handicap -0.5", "asian_handicap_-0_5"),
        ("Asian Handicap", "Asian Handicap +1", "asian_handicap_+1"),
    ],
)
def test_line_name_to_token_valid(main, name, expected):
    assert line_name_to_token("football", main, name) == expected


@pytest.mark.parametrize(
    ("sport", "main", "name", "expected"),
    [
        ("basketball", "Over/Under", "Over/Under +160.5", "over_under_games_160_5"),
        ("basketball", "Over/Under", "Más/Menos de +160.5", "over_under_games_160_5"),
        ("basketball", "Asian Handicap", "Asian Handicap -5.5", "asian_handicap_games_-5_5_games"),
        ("american-football", "Asian Handicap", "Asian Handicap -21", "asian_handicap_-21_0"),
        ("handball", "Asian Handicap", "Asian Handicap +3.5", "handicap_+3_5"),
        ("ice-hockey", "Over/Under", "Over/Under +5.5", "over_under_5_5"),
        ("baseball", "Over/Under", "Over/Under +7", "over_under_7_0"),
        ("rugby-league", "Handicap", "Asian Handicap -4.5", "handicap_-4_5"),
        ("rugby-union", "Over/Under", "Over/Under +40.5", "over_under_40_5"),
    ],
)
def test_a_line_maps_to_its_sport_s_token(sport, main, name, expected):
    assert line_name_to_token(sport, main, name) == expected


def test_a_line_two_tokens_share_maps_to_none():
    """Tennis sets and games both register Over/Under +6.5, and the page does not say which row it is (§8)."""
    assert line_name_to_token("tennis", "Over/Under", "Over/Under +6.5") is None


def test_a_tab_the_sport_does_not_register_maps_to_none():
    assert line_name_to_token("ice-hockey", "Asian Handicap", "Asian Handicap -1.5") is None


def test_a_name_made_of_a_bare_number_maps_to_none():
    """Every line row also carries its bookmaker count as a lone number, which must not pass for the 0 line."""
    assert line_name_to_token("football", "Asian Handicap", "0") is None
    assert line_name_to_token("football", "Asian Handicap", "Asian Handicap 0") == "asian_handicap_0"


def test_line_name_to_token_unknown_line_returns_none():
    assert line_name_to_token("football", "Over/Under", "Over/Under +99.5") is None


def test_line_name_to_token_garbage_returns_none():
    assert line_name_to_token("football", "Over/Under", "not a line") is None


def test_line_name_to_token_unknown_main_market_returns_none():
    assert line_name_to_token("football", "1X2", "1X2") is None


@pytest.mark.parametrize(
    ("main", "english", "localized", "expected"),
    [
        ("Over/Under", "Over/Under +2.5", "Más/Menos de +2.5", "over_under_2_5"),
        ("Over/Under", "Over/Under +1", "Más/Menos de +1", "over_under_1"),
        ("Asian Handicap", "Asian Handicap -1.5", "Hándicap asiático -1.5", "asian_handicap_-1_5"),
        ("Asian Handicap", "Asian Handicap +0.25", "Hándicap asiático +0.25", "asian_handicap_+0_25"),
        ("Asian Handicap", "Asian Handicap 0", "Hándicap asiático 0", "asian_handicap_0"),
    ],
)
def test_a_localized_line_name_maps_to_the_english_token(main, english, localized, expected):
    """A5: on cuotasahora.com the umbrella found no line, since names had to start with the English label."""
    assert line_name_to_token("football", main, english) == expected
    assert line_name_to_token("football", main, localized) == expected


@pytest.mark.parametrize(
    "name",
    ["Más/Menos de +2.5 Goles", "Más/Menos de", "Más/Menos de+2.5", "Over/Under +2.5O/U", ""],
)
def test_a_name_without_a_trailing_line_maps_to_none(name):
    assert line_name_to_token("football", "Over/Under", name) is None


def test_an_over_under_line_below_zero_maps_to_none():
    assert line_name_to_token("football", "Over/Under", "Over/Under -2.5") is None
