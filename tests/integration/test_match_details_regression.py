"""Regression tests for match-details extraction (PR #54 bug).

For some matches, OddsPortal's embedded react-event-header JSON returns
data for a different (typically the most-recent) match than the URL's
page-fragment-disambiguated target. The fix in `_extract_match_details_event_header`
prefers DOM-rendered values (post React hydration) over the JSON, with
per-field fallback.

These tests run the scraper against captured HARs of known-affected
matches and assert that match-details fields equal the DOM (correct)
values curated in `metadata.json`. If the DOM-first dispatcher regresses,
the assertions will fail with the JSON (stale) values.
"""

import pytest

from tests.integration.helpers.replay import run_replay

BARCELONA_LEGANES_2020 = {
    "sport": "football",
    "league": "laliga",
    "match_id": "leganes-Mi0rXQg7",
    "url": "https://www.oddsportal.com/football/h2h/barcelona-SKbpVP5K/leganes-Mi0rXQg7/#hYV97ShC",
    "fixture_name": "1x2_full_time_all.json",
}


REGRESSION_MATCHES = [BARCELONA_LEGANES_2020]


@pytest.mark.integration
@pytest.mark.parametrize("match", REGRESSION_MATCHES, ids=lambda m: m["match_id"])
def test_match_details_match_curated_metadata(match, load_metadata, har_for_match, tmp_path, monkeypatch):
    """The 7 PR #54 fields must match the curated metadata.json values.

    HAR was captured with OH_TIMEZONE=UTC; replay must use the same
    so the DOM date string is interpreted in UTC and converts to itself.
    """
    monkeypatch.setenv("OH_TIMEZONE", "UTC")
    if har_for_match(match["sport"], match["league"], match["match_id"], match["fixture_name"]) is None:
        pytest.skip("replay only: the curated values describe the captured page")

    actual = run_replay(
        har_for_match,
        tmp_path,
        match,
        match["fixture_name"],
        markets=["1x2"],
        period="full_time",
        bookies_filter="all",
    )
    record = actual[0]

    expected = load_metadata(match["sport"], match["league"], match["match_id"])

    assert record["home_team"] == expected["home_team"], (
        f"home_team: expected {expected['home_team']!r}, got {record.get('home_team')!r}"
    )
    assert record["away_team"] == expected["away_team"], (
        f"away_team: expected {expected['away_team']!r}, got {record.get('away_team')!r}"
    )
    assert record["league_name"] == expected["league_name"], (
        f"league_name: expected {expected['league_name']!r}, got {record.get('league_name')!r}"
    )
    assert record["match_date"] == expected["match_date"], (
        f"match_date: expected {expected['match_date']!r}, got {record.get('match_date')!r}"
    )
    assert str(record["home_score"]) == expected["final_score"]["home"], (
        f"home_score: expected {expected['final_score']['home']!r}, got {record.get('home_score')!r}"
    )
    assert str(record["away_score"]) == expected["final_score"]["away"], (
        f"away_score: expected {expected['final_score']['away']!r}, got {record.get('away_score')!r}"
    )
    assert record["partial_results"] == expected["partial_results"], (
        f"partial_results: expected {expected['partial_results']!r}, got {record.get('partial_results')!r}"
    )
