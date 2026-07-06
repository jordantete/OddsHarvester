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
