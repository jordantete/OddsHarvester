"""Integration tests for basketball scraping."""

import pytest

from tests.integration.helpers.replay import replay_and_compare

# Match configurations
LAKERS_CELTICS = {
    "sport": "basketball",
    "league": "nba",
    "match_id": "los-angeles-lakers-boston-celtics-0fwUQJEk",
    "url": "https://www.oddsportal.com/basketball/h2h/boston-celtics-KYD9hVEm/los-angeles-lakers-ngegZ8bg/#0fwUQJEk",
}

LAKERS_WARRIORS = {
    "sport": "basketball",
    "league": "nba",
    "match_id": "los-angeles-lakers-golden-state-warriors-jZvOnVBk",
    "url": "https://www.oddsportal.com/basketball/h2h/golden-state-warriors-SxUtXqch/los-angeles-lakers-ngegZ8bg/#jZvOnVBk",
}


@pytest.mark.integration
class TestBasketballBasicMarkets:
    """Tests for basic basketball markets."""

    def test_bb_001_home_away(self, har_for_match, tmp_path):
        """BB-001: Test home_away market, full including OT."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LAKERS_CELTICS,
            "home_away_full_including_ot_all.json",
            markets=["home_away"],
            period="full_including_ot",
        )

    def test_bb_002_home_away_1x2(self, har_for_match, tmp_path):
        """BB-002: Test home_away and 1x2 markets."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LAKERS_CELTICS,
            "1x2_home_away_full_including_ot_all.json",
            markets=["home_away", "1x2"],
        )

    def test_bb_003_lakers_warriors(self, har_for_match, tmp_path):
        """BB-003: Test Lakers vs Warriors."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LAKERS_WARRIORS,
            "home_away_full_including_ot_all.json",
            markets=["home_away"],
        )


@pytest.mark.integration
class TestBasketballPeriods:
    """Tests for basketball period options."""

    def test_bb_004_1st_half(self, har_for_match, tmp_path):
        """BB-004: home_away for the 1st half, read from the period tab's own odds."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LAKERS_CELTICS,
            "home_away_1st_half_all.json",
            markets=["home_away"],
            period="1st_half",
        )

    def test_bb_005_1st_quarter(self, har_for_match, tmp_path):
        """BB-005: home_away for the 1st quarter, read from the period tab's own odds."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LAKERS_CELTICS,
            "home_away_1st_quarter_all.json",
            markets=["home_away"],
            period="1st_quarter",
        )

    def test_bb_006_lakers_warriors_1st_half(self, har_for_match, tmp_path):
        """BB-006: home_away for the Lakers - Warriors 1st half, read from the period tab's own odds."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LAKERS_WARRIORS,
            "home_away_1st_half_all.json",
            markets=["home_away"],
            period="1st_half",
        )
