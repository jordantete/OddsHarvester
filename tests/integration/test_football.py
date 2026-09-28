"""Integration tests for football scraping."""

import pytest

from tests.integration.helpers.comparison import compare_match_data
from tests.integration.helpers.replay import load_golden, replay_and_compare, run_replay

# Match configurations
LEICESTER_BRENTFORD = {
    "sport": "football",
    "league": "premier-league",
    "match_id": "leicester-brentford-xQ77QTN0",
    "url": "https://www.oddsportal.com/football/h2h/brentford-xYe7DwID/leicester-KrrdAMyI/#xQ77QTN0",
}

REAL_MADRID_BARCELONA = {
    "sport": "football",
    "league": "super-cup-2025",
    "match_id": "real-madrid-barcelona-bZrHkILa",
    "url": "https://www.oddsportal.com/football/h2h/barcelona-SKbpVP5K/real-madrid-W8mj7MDD/#bZrHkILa",
}


@pytest.mark.integration
class TestFootballBasicMarkets:
    """Tests for basic football markets."""

    def test_fb_001_1x2_full_time(self, har_for_match, tmp_path):
        """FB-001: Test 1x2 market, full time, all bookies."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_full_time_all.json",
            markets=["1x2"],
            period="full_time",
            bookies_filter="all",
        )

    def test_fb_002_multiple_markets(self, har_for_match, tmp_path):
        """FB-002: Test 1x2 + btts + double_chance markets."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_btts_double_chance_full_time_all.json",
            markets=["1x2", "btts", "double_chance"],
        )

    def test_fb_003_over_under(self, har_for_match, tmp_path):
        """FB-003: Test over/under markets."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "over_under_1_5_over_under_2_5_full_time_all.json",
            markets=["over_under_2_5", "over_under_1_5"],
        )

    def test_fb_004_over_under_umbrella(self, har_for_match, tmp_path):
        """FB-004: Test the over_under umbrella token expands into per-line markets.

        Reuses the FB-003 fixture (captured for the explicit over_under_1_5 /
        over_under_2_5 lines) but requests the umbrella token `over_under` instead.
        The umbrella enumerates every O/U line rendered on the page and produces one
        `{token}_market` key per line rather than a single `over_under_market` key.
        Only the two lines this fixture was captured for are asserted here, since
        those are the ones guaranteed to carry real odds data under HAR replay.
        """
        fixture_name = "over_under_1_5_over_under_2_5_full_time_all.json"
        actual = run_replay(har_for_match, tmp_path, LEICESTER_BRENTFORD, fixture_name, markets=["over_under"])
        expected = load_golden(LEICESTER_BRENTFORD, fixture_name)

        # The umbrella also yields lines this fixture was not captured for; compare only the captured ones.
        captured = {k: v for k, v in actual[0].items() if not k.endswith("_market") or k in expected[0]}
        result = compare_match_data(captured, expected[0])
        assert result.passed, str(result)

        record = actual[0]

        # Umbrella must expand into per-line keys, not collapse to a single market key.
        assert "over_under_market" not in record

        for line_key in ("over_under_1_5_market", "over_under_2_5_market"):
            assert line_key in record, f"Expected umbrella to produce '{line_key}'"
            assert record[line_key], f"'{line_key}' should be non-empty"
            assert record[line_key] == expected[0][line_key]

    def test_fb_008_local_kickoff(self, har_for_match, tmp_path):
        """FB-008: Test --local-kickoff adds venue_timezone and match_date_venue_local, UTC untouched."""
        actual = run_replay(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_full_time_all.json",
            markets=["1x2"],
            period="full_time",
            bookies_filter="all",
            local_kickoff=True,
        )

        record = actual[0]
        assert record["venue_timezone"] == "Europe/London"
        assert record["match_date_venue_local"] is not None
        assert record["match_date"].endswith("UTC")

    def test_fb_007_real_madrid_barcelona(self, har_for_match, tmp_path):
        """FB-007: Test Real Madrid vs Barcelona."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            REAL_MADRID_BARCELONA,
            "1x2_btts_full_time_all.json",
            markets=["1x2", "btts"],
        )


@pytest.mark.integration
class TestFootballPeriods:
    """Tests for football period options."""

    def test_fb_005_1st_half(self, har_for_match, tmp_path):
        """FB-005: Test 1x2 market, 1st half period."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_1st_half_all.json",
            markets=["1x2"],
            period="1st_half",
        )


@pytest.mark.integration
class TestFootballBookiesFilter:
    """Tests for football bookies filter option."""

    def test_fb_006_classic_bookies(self, har_for_match, tmp_path):
        """FB-006: Test 1x2 market with classic bookies only."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_full_time_classic.json",
            markets=["1x2"],
            bookies_filter="classic",
        )
