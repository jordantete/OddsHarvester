"""Integration tests for tennis scraping."""

import pytest

from tests.integration.helpers.replay import replay_and_compare, run_replay

# Match configurations
DJOKOVIC_SINNER = {
    "sport": "tennis",
    "league": "australian-open",
    "match_id": "djokovic-novak-sinner-jannik-IwSMNP62",
    "url": "https://www.oddsportal.com/tennis/h2h/djokovic-novak-AZg49Et9/sinner-jannik-6HdC3z4H/#IwSMNP62",
}

DJOKOVIC_LEHECKA = {
    "sport": "tennis",
    "league": "australian-open",
    "match_id": "djokovic-novak-lehecka-jiri-0ShOHpqe",
    "url": "https://www.oddsportal.com/tennis/h2h/djokovic-novak-AZg49Et9/lehecka-jiri-6PlgfXKR/#0ShOHpqe",
}

HUMBERT_ZVEREV = {
    "sport": "tennis",
    "league": "australian-open",
    "match_id": "humbert-ugo-zverev-alexander-MssXFOD7",
    "url": "https://www.oddsportal.com/tennis/h2h/humbert-ugo-O4ywE5Ah/zverev-alexander-dGbUhw9m/#MssXFOD7",
}


@pytest.mark.integration
class TestTennisBasicMarkets:
    """Tests for basic tennis markets."""

    def test_tn_001_match_winner(self, har_for_match, tmp_path):
        """TN-001: Test match_winner market - Djokovic vs Sinner."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            DJOKOVIC_SINNER,
            "match_winner_full_time_all.json",
            markets=["match_winner"],
        )

    def test_tn_002_multiple_markets(self, har_for_match, tmp_path):
        """TN-002: Test match_winner + over_under_sets markets."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            DJOKOVIC_SINNER,
            "match_winner_over_under_sets_2_5_full_time_all.json",
            markets=["match_winner", "over_under_sets_2_5"],
        )

    def test_tn_003_djokovic_lehecka(self, har_for_match, tmp_path):
        """TN-003: Test Djokovic vs Lehecka."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            DJOKOVIC_LEHECKA,
            "match_winner_full_time_all.json",
            markets=["match_winner"],
        )

    def test_tn_006_local_kickoff_multi_timezone(self, har_for_match, tmp_path):
        """TN-006: --local-kickoff resolves a multi-timezone country by host city (Melbourne)."""
        record = run_replay(
            har_for_match,
            tmp_path,
            DJOKOVIC_LEHECKA,
            "match_winner_full_time_all.json",
            markets=["match_winner"],
            local_kickoff=True,
        )[0]

        # Australia is multi-timezone; resolution goes through the host-city lookup.
        assert record["venue_timezone"] == "Australia/Melbourne"
        # Melbourne is AEDT (UTC+11) in January; kickoff 08:15 UTC -> 19:15 local.
        assert record["match_date_venue_local"].startswith("2025-01-19 19:15:00")
        assert "+1100" in record["match_date_venue_local"]
        # UTC value stays canonical.
        assert record["match_date"].endswith("UTC")

    def test_tn_004_over_under_games(self, har_for_match, tmp_path):
        """TN-004: Test over/under games market."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            DJOKOVIC_LEHECKA,
            "over_under_games_22_5_full_time_all.json",
            markets=["over_under_games_22_5"],
        )

    def test_tn_005_humbert_zverev(self, har_for_match, tmp_path):
        """TN-005: Test Humbert vs Zverev."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            HUMBERT_ZVEREV,
            "match_winner_full_time_all.json",
            markets=["match_winner"],
        )


@pytest.mark.integration
class TestTennisPeriods:
    """Tests for tennis period options."""

    def test_tn_006_1st_set(self, har_for_match, tmp_path):
        """TN-006: Test match_winner market, 1st set - Djokovic vs Sinner."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            DJOKOVIC_SINNER,
            "match_winner_1st_set_all.json",
            markets=["match_winner"],
            period="1st_set",
        )
