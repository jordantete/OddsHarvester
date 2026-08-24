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


def test_non_today_date_row_parses_kickoff():
    # Future rows render a slash-separated date "19/Jul," which
    # base_scraper._parse_date_header cannot parse as-is. The live fixture only
    # carries today's picks, so this row is synthetic (same markup shape).
    html = """
    <div data-testid="sport-country-league-item">
      <a data-testid="header-sport-item" href="/football/"><div>Football</div></a>
      <a data-testid="header-country-item" href="/football/world/"><p>World</p></a>
      <a data-testid="header-tournament-item" href="/football/world/friendly/">Friendly</a>
    </div>
    <div data-testid="game-row">
      <div data-testid="betting-tip-header">1</div>
      <div data-testid="betting-tip-header">X</div>
      <div data-testid="betting-tip-header">2</div>
      <a href="/football/h2h/spain-a/argentina-b/#fff">
        <div data-testid="date-time-item"><p>19/Jul,</p><p>21:00</p><span>1X2</span></div>
        <div data-testid="event-participants"><p data-testid="participant-name">Spain</p>
        <p data-testid="participant-name">Argentina</p></div>
      </a>
      <p data-testid="odd-container-default">1.69</p>
      <div data-testid="prediction-container"><a href="#">89%</a></div>
      <p data-testid="odd-container-default">3.68</p>
      <div data-testid="prediction-container"><a href="#">9%</a></div>
      <p data-testid="odd-container-default">4.70</p>
      <div data-testid="prediction-container"><a href="#">2%</a></div>
    </div>
    """
    rows = parse_top_predictions(html, tz_name="UTC")
    assert len(rows) == 1
    assert rows[0]["kickoff"] is not None
    assert rows[0]["kickoff"].endswith("T21:00")
    assert "-07-19" in rows[0]["kickoff"]


def test_malformed_row_is_skipped():
    html = """
    <div data-testid="sport-country-league-item">
      <a data-testid="header-sport-item" href="/football/"><div>Football</div></a>
      <a data-testid="header-country-item" href="/football/europe/"><p>Europe</p></a>
      <a data-testid="header-tournament-item" href="/football/europe/x/">League X</a>
    </div>
    <div data-testid="game-row">
      <div data-testid="betting-tip-header">1</div>
      <div data-testid="betting-tip-header">X</div>
      <div data-testid="betting-tip-header">2</div>
      <p>garbage, no link, no cells</p>
    </div>
    """
    assert parse_top_predictions(html) == []


def test_empty_html_returns_empty_list():
    assert parse_top_predictions("<html><body></body></html>") == []
