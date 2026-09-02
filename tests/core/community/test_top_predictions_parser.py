"""Unit tests for the Community Top Predictions parser."""

from pathlib import Path

import pytest
from tests.dom_builders import community_column, community_row, community_section

from oddsharvester.core.community.top_predictions_parser import parse_top_predictions

FIXTURE = Path(__file__).parents[2] / "data" / "community" / "top_predictions_football.html"


@pytest.fixture(scope="module")
def records():
    return parse_top_predictions(FIXTURE.read_text(encoding="utf-8"), tz_name="UTC")


def test_parses_all_game_rows(records):
    html = FIXTURE.read_text(encoding="utf-8")
    assert len(records) == html.count("/h2h/")
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
    columns = (
        community_column("1", "1.69", "89%") + community_column("X", "3.68", "9%") + community_column("2", "4.70", "2%")
    )
    html = community_section(
        community_row(
            "/football/h2h/spain-a/argentina-b/#fff",
            columns,
            date="19/Jul,",
            time="21:00",
            home="Spain",
            away="Argentina",
        ),
        country="World",
        league="friendly",
    )

    rows = parse_top_predictions(html, tz_name="UTC")

    assert len(rows) == 1
    assert rows[0]["kickoff"].endswith("T21:00")
    assert "-07-19" in rows[0]["kickoff"]


def test_malformed_row_is_skipped():
    # A row with no outcome columns carries no picks to report.
    html = community_section(community_row("/football/h2h/a/b/#x", columns=""))

    assert parse_top_predictions(html) == []


def test_empty_html_returns_empty_list():
    assert parse_top_predictions("<html><body></body></html>") == []
