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

BURSASPOR_GALATASARAY = {
    "sport": "basketball",
    "league": "super-lig-turkey",
    "match_id": "bursaspor-durmazlar-galatasaray-Ymj4jlAE",
    "url": "https://www.oddsportal.com/basketball/h2h/bursaspor-durmazlar-O2jT8AmT/galatasaray-QR2OmUw1/#Ymj4jlAE",
}

VIRTUS_ZAGREB_ZADAR = {
    "sport": "basketball",
    "league": "basketball-league-croatia",
    "match_id": "virtus-zagreb-zadar-U1bHQrEa",
    "url": "https://www.oddsportal.com/basketball/h2h/virtus-zagreb-Wlg8DmGL/zadar-4Itk3GMs/#U1bHQrEa",
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
        """BB-002: Test home_away and 1x2 markets; 1X2 has no FT including OT period, so it comes back empty."""
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


@pytest.mark.integration
class TestBasketballUmbrellas:
    """Issue #115: the umbrellas open the lines rendered under FT including OT, and only those."""

    @pytest.mark.parametrize("match", [BURSASPOR_GALATASARAY, VIRTUS_ZAGREB_ZADAR], ids=["bursaspor", "virtus-zagreb"])
    def test_bb_007_umbrellas_open_the_rendered_lines(self, har_for_match, tmp_path, match):
        """BB-007: every line the umbrellas expand to carries odds; lines read under another period came back empty."""
        actual = replay_and_compare(
            har_for_match,
            tmp_path,
            match,
            "asian_handicap_over_under_full_including_ot_all.json",
            markets=["over_under", "asian_handicap"],
            period="full_including_ot",
        )
        record = actual[0]
        lines = {key: value for key, value in record.items() if key.endswith("_market")}

        assert "over_under_market" not in lines
        assert "asian_handicap_market" not in lines
        assert any(key.startswith("over_under_games_") for key in lines)
        assert any(
            key.startswith("asian_handicap_games_") and key != "asian_handicap_games_0_games_market" for key in lines
        )
        assert [key for key, value in lines.items() if not value] == []
