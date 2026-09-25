"""Tests for the integration-suite comparator."""

import copy
import json
from pathlib import Path

import pytest

from tests.integration.helpers.comparison import compare_match_data

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


def test_history_year_difference_is_ignored(match):
    expected = _with_history(match)
    actual = copy.deepcopy(expected)
    block = actual["1x2_market"][0]["odds_history_data"][0]
    block["odds_history"][0]["timestamp"] = "2027-01-03T14:57:00"
    block["opening_odds"]["timestamp"] = "2027-12-20T10:00:00"
    assert compare_match_data(actual, expected).passed


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
