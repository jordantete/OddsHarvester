import pytest

from oddsharvester.core.market_extraction.line_tokens import line_name_to_token


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
    assert line_name_to_token(main, name) == expected


def test_line_name_to_token_unknown_line_returns_none():
    assert line_name_to_token("Over/Under", "Over/Under +99.5") is None


def test_line_name_to_token_garbage_returns_none():
    assert line_name_to_token("Over/Under", "not a line") is None


def test_line_name_to_token_unknown_main_market_returns_none():
    assert line_name_to_token("1X2", "1X2") is None


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
    assert line_name_to_token(main, english) == expected
    assert line_name_to_token(main, localized) == expected


@pytest.mark.parametrize(
    "name",
    ["Más/Menos de +2.5 Goles", "Más/Menos de", "Más/Menos de+2.5", "Over/Under +2.5O/U", ""],
)
def test_a_name_without_a_trailing_line_maps_to_none(name):
    assert line_name_to_token("Over/Under", name) is None


def test_an_over_under_line_below_zero_maps_to_none():
    assert line_name_to_token("Over/Under", "Over/Under -2.5") is None
