"""Tests for the integration-suite comparator."""

import copy
import json
from pathlib import Path

import pytest

from tests.integration.helpers.comparison import compare_golden, compare_match_data, compare_match_structure

pytestmark = pytest.mark.integration

LEICESTER_1X2 = (
    Path(__file__).parent / "fixtures/football/premier-league/leicester-brentford-xQ77QTN0/1x2_full_time_all.json"
)
HISTORY_ENTRY = {
    "1": "3.50",
    "X": "3.67",
    "2": "1.96",
    "bookmaker_name": "Betclic.fr",
    "period": "FullTime",
    "submarket_name": "1X2",
    "odds_history_data": [
        {
            "odds_history": [{"timestamp": "2026-01-03T14:57:00", "odds": 3.5}],
            "opening_odds": {"timestamp": "2026-12-20T10:00:00", "odds": 2.84},
        }
    ],
}


@pytest.fixture
def match():
    return json.loads(LEICESTER_1X2.read_text())[0]


def _entry(match, bookmaker):
    return next(e for e in match["1x2_market"] if e["bookmaker_name"] == bookmaker)


def _with_history(match):
    with_history = copy.deepcopy(match)
    with_history["1x2_market"] = [copy.deepcopy(HISTORY_ENTRY)]
    return with_history


def test_identical_match_passes(match):
    assert compare_match_data(copy.deepcopy(match), match).passed


def test_scraped_date_is_ignored(match):
    actual = copy.deepcopy(match)
    actual["scraped_date"] = "2030-01-01 00:00:00 UTC"
    assert compare_match_data(actual, match).passed


def test_audit_mutation_fails(match):
    actual = copy.deepcopy(match)
    actual["1x2_market"] = []
    actual["match_date"] = "2024-01-01 00:00:00 UTC"
    actual["league_name"] = "Serie A"
    actual["match_link"] = "https://www.oddsportal.com/football/italy/serie-a/x-y-AAAAAAAA/"
    result = compare_match_data(actual, match)
    assert not result.passed
    for needle in ("match_date", "league_name", "match_link", "1x2_market"):
        assert needle in str(result)


def test_missing_bookmaker_fails(match):
    actual = copy.deepcopy(match)
    actual["1x2_market"] = [e for e in actual["1x2_market"] if e["bookmaker_name"] != "Winamax"]
    result = compare_match_data(actual, match)
    assert not result.passed
    assert "Winamax" in str(result)


def test_changed_odd_fails(match):
    actual = copy.deepcopy(match)
    _entry(actual, "Betclic.fr")["1"] = "3.51"
    assert not compare_match_data(actual, match).passed


def test_one_differing_field_gives_one_short_line_naming_it(match):
    actual = copy.deepcopy(match)
    _entry(actual, "Betclic.fr")["1"] = "3.51"

    result = compare_match_data(actual, match)

    assert result.errors == [
        "1x2_market: entry ('Betclic.fr', 'FullTime', '1X2') differs in ['1']; '1': actual='3.51' vs expected='3.50'"
    ]


def test_extra_market_fails(match):
    actual = copy.deepcopy(match)
    actual["btts_market"] = []
    result = compare_match_data(actual, match)
    assert not result.passed
    assert "btts_market" in str(result)


def test_missing_field_fails(match):
    actual = copy.deepcopy(match)
    del actual["venue"]
    assert not compare_match_data(actual, match).passed


def test_extra_field_fails(match):
    actual = copy.deepcopy(match)
    actual["new_field"] = "x"
    assert not compare_match_data(actual, match).passed


def test_duplicate_entry_fails(match):
    actual = copy.deepcopy(match)
    actual["1x2_market"].append(copy.deepcopy(_entry(actual, "Betclic.fr")))
    result = compare_match_data(actual, match)
    assert not result.passed
    assert "2 times" in str(result)


def test_history_year_difference_fails(match):
    expected = _with_history(match)
    actual = copy.deepcopy(expected)
    block = actual["1x2_market"][0]["odds_history_data"][0]
    block["odds_history"][0]["timestamp"] = "2027-01-03T14:57:00"
    block["opening_odds"]["timestamp"] = "2027-12-20T10:00:00"

    result = compare_match_data(actual, expected)

    [error] = result.errors
    assert error.startswith("1x2_market: entry ('Betclic.fr', 'FullTime', '1X2') differs in ['odds_history_data']; ")
    # Both history values are longer than VALUE_WIDTH and cut on both sides of the windowed difference.
    assert error.count("...") == 4


def test_long_values_differing_only_after_char_200_show_the_difference(match):
    actual = copy.deepcopy(match)
    expected = copy.deepcopy(match)
    padding = "x" * 200
    _entry(actual, "Betclic.fr")["padding"] = padding + "AAA" + "y" * 100
    _entry(expected, "Betclic.fr")["padding"] = padding + "BBB" + "y" * 100

    result = compare_match_data(actual, expected)

    [error] = result.errors
    actual_part = error.split("actual=")[1].split(" vs expected=")[0]
    expected_part = error.split(" vs expected=")[1]
    assert actual_part != expected_part
    assert "AAA" in actual_part
    assert "BBB" in expected_part


def test_history_month_difference_fails(match):
    expected = _with_history(match)
    actual = copy.deepcopy(expected)
    actual["1x2_market"][0]["odds_history_data"][0]["odds_history"][0]["timestamp"] = "2026-02-03T14:57:00"
    assert not compare_match_data(actual, expected).passed


def test_missing_history_fails(match):
    expected = _with_history(match)
    actual = copy.deepcopy(expected)
    del actual["1x2_market"][0]["odds_history_data"]
    assert not compare_match_data(actual, expected).passed


def test_market_regressed_to_none_fails(match):
    actual = copy.deepcopy(match)
    actual["1x2_market"] = None
    result = compare_match_data(actual, match)
    assert not result.passed
    assert "1x2_market" in str(result)


def test_identical_none_market_passes(match):
    expected = copy.deepcopy(match)
    expected["1x2_market"] = None
    assert compare_match_data(copy.deepcopy(expected), expected).passed


def test_structure_ignores_values_and_the_bookmaker_panel(match):
    actual = copy.deepcopy(match)
    _entry(actual, "Betclic.fr")["1"] = "9.99"
    _entry(actual, "Winamax")["bookmaker_name"] = "NewBook"
    actual["1x2_market"] = actual["1x2_market"][1:]
    actual["venue"] = None
    assert compare_match_structure(actual, match).passed


def test_structure_allows_extra_fields(match):
    actual = copy.deepcopy(match)
    actual["new_field"] = "x"
    actual["btts_market"] = []
    assert compare_match_structure(actual, match).passed


def test_structure_missing_market_fails(match):
    actual = copy.deepcopy(match)
    del actual["1x2_market"]
    result = compare_match_structure(actual, match)
    assert not result.passed
    assert "1x2_market" in str(result)


def test_structure_empty_market_fails(match):
    actual = copy.deepcopy(match)
    actual["1x2_market"] = []
    result = compare_match_structure(actual, match)
    assert not result.passed
    assert "1x2_market" in str(result)


def test_structure_missing_entry_key_fails(match):
    actual = copy.deepcopy(match)
    del _entry(actual, "Betclic.fr")["X"]
    result = compare_match_structure(actual, match)
    assert result.errors == ["1x2_market: entry ('Betclic.fr', 'FullTime', '1X2') lacks ['X']"]


def test_structure_field_emptied_to_none_fails(match):
    actual = copy.deepcopy(match)
    actual["home_team"] = None
    result = compare_match_structure(actual, match)
    assert not result.passed
    assert "home_team" in str(result)


def test_structure_accepts_a_market_the_golden_holds_empty(match):
    expected = copy.deepcopy(match)
    expected["1x2_market"] = []
    actual = copy.deepcopy(match)
    assert compare_match_structure(actual, expected).passed


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("home_team", "Chelsea"),
        ("away_team", "Arsenal"),
        ("home_score", "1"),
        ("away_score", "3"),
        ("partial_results", "(0:2, 0:2)"),
        ("match_date", "2025-02-22 20:00:00 UTC"),
    ],
)
def test_structure_another_match_fails(match, field, value):
    actual = copy.deepcopy(match)
    actual[field] = value
    result = compare_match_structure(actual, match)
    assert result.errors == [f"Field '{field}' mismatch: actual={value!r} vs expected={match[field]!r}"]


def test_structure_accepts_a_renamed_league(match):
    """Sponsors rename leagues (gotchas §4), so a live league_name may differ from the golden's."""
    actual = copy.deepcopy(match)
    actual["league_name"] = "Barclays Premier League"
    assert compare_match_structure(actual, match).passed


def test_structure_skips_an_identity_field_the_golden_leaves_empty(match):
    """A golden captured before kickoff holds no score; the live page of the played match shows one."""
    expected = copy.deepcopy(match)
    expected["home_score"] = expected["away_score"] = expected["partial_results"] = None
    assert compare_match_structure(copy.deepcopy(match), expected).passed


def test_structure_empty_odds_string_fails(match):
    actual = copy.deepcopy(match)
    _entry(actual, "Betclic.fr")["X"] = ""
    result = compare_match_structure(actual, match)
    assert result.errors == ["1x2_market: entry ('Betclic.fr', 'FullTime', '1X2') has no value in ['X']"]


def test_structure_does_not_require_a_value_the_golden_leaves_empty_in_one_entry(match):
    expected = copy.deepcopy(match)
    _entry(expected, "Winamax")["X"] = ""
    actual = copy.deepcopy(match)
    _entry(actual, "Betclic.fr")["X"] = ""
    assert compare_match_structure(actual, expected).passed


def test_structure_accepts_an_empty_history_list(match):
    expected = _with_history(match)
    actual = copy.deepcopy(expected)
    actual["1x2_market"][0]["odds_history_data"] = []
    assert compare_match_structure(actual, expected).passed


def test_golden_compare_is_exact_on_replay(match):
    actual = copy.deepcopy(match)
    _entry(actual, "Betclic.fr")["1"] = "3.51"
    assert not compare_golden(actual, match, live=False).passed


def test_golden_compare_checks_structure_under_live(match):
    moved = copy.deepcopy(match)
    _entry(moved, "Betclic.fr")["1"] = "3.51"
    emptied = copy.deepcopy(match)
    emptied["1x2_market"] = []
    assert compare_golden(moved, match, live=True).passed
    assert not compare_golden(emptied, match, live=True).passed


def test_golden_compare_on_replay_still_fails_on_a_renamed_league(match):
    actual = copy.deepcopy(match)
    actual["league_name"] = "Barclays Premier League"
    assert not compare_golden(actual, match, live=False).passed
