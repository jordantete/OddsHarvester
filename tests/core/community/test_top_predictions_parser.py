"""Unit tests for the Community Top Predictions parser."""

from pathlib import Path

import pytest

from oddsharvester.core.community.top_predictions_parser import parse_top_predictions

FIXTURE = Path(__file__).parents[2] / "data" / "community" / "top_predictions_football.html"


@pytest.fixture(scope="module")
def records():
    return parse_top_predictions(FIXTURE.read_text(encoding="utf-8"), tz_name="UTC")


def test_parses_all_game_rows(records):
    html = FIXTURE.read_text(encoding="utf-8")
    assert len(records) == html.count('data-testid="game-row"')
    assert len(records) > 0


def test_record_fields_populated(records):
    for record in records:
        assert record["country"]
        assert record["league"]
        assert record["home_team"]
        assert record["away_team"]
        assert record["home_team"] != record["away_team"]
        assert record["market"]
        assert record["match_url"].startswith("https://www.oddsportal.com/")
        assert record["kickoff_text"]


def test_outcomes_consistent(records):
    for record in records:
        outcomes = [o["outcome"] for o in record["odds"]]
        assert outcomes == [p["outcome"] for p in record["community_votes_pct"]]
        assert 2 <= len(outcomes) <= 3
        for odd in record["odds"]:
            if odd["odds"] is not None:
                assert odd["odds"] > 1.0


def test_percentages_roughly_sum_to_100(records):
    for record in records:
        total = sum(p["pct"] for p in record["community_votes_pct"])
        assert 95 <= total <= 105


def test_non_today_date_row_parses_kickoff(records):
    # Fixture row 7 (Spain vs Argentina) renders a slash-separated future date
    # "19/Jul," which base_scraper._parse_date_header cannot parse as-is.
    row = next(r for r in records if "19/Jul" in r["kickoff_text"])
    assert row["kickoff"] is not None
    assert row["kickoff"].endswith("T21:00")
    assert "-07-19" in row["kickoff"]


def test_malformed_row_is_skipped():
    html = """
    <div data-testid="sport-country-league-item">
      <a data-testid="header-sport-item" href="/football/"><div>Football</div></a>
      <a data-testid="header-country-item" href="/football/europe/"><p>Europe</p></a>
      <a data-testid="header-tournament-item" href="/football/europe/x/">League X</a>
    </div>
    <div data-testid="betting-tip-header">1</div>
    <div data-testid="betting-tip-header">X</div>
    <div data-testid="betting-tip-header">2</div>
    <div data-testid="game-row"><p>garbage, no link, no cells</p></div>
    """
    assert parse_top_predictions(html) == []


def test_empty_html_returns_empty_list():
    assert parse_top_predictions("<html><body></body></html>") == []
