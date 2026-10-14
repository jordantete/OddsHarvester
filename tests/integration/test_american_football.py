"""Integration tests for American football scraping."""

import pytest

from tests.integration.helpers.replay import replay_and_compare

NFL_MATCH = {
    "sport": "american-football",
    "league": "nfl",
    "match_id": "atlanta-falcons-baltimore-ravens-U7cApaRH",
    "url": "https://www.oddsportal.com/american-football/h2h/atlanta-falcons-hClIiQIR/baltimore-ravens-pUern3T0/#U7cApaRH",
}


@pytest.mark.integration
class TestAmericanFootballUmbrellas:
    def test_af_001_umbrellas(self, har_for_match, tmp_path):
        """AF-001: over_under and asian_handicap open every rendered line, whole lines included (issue #115)."""
        actual = replay_and_compare(
            har_for_match,
            tmp_path,
            NFL_MATCH,
            "asian_handicap_over_under_full_including_ot_all.json",
            markets=["over_under", "asian_handicap"],
            period="full_including_ot",
        )
        lines = {key: value for key, value in actual[0].items() if key.endswith("_market")}

        assert "over_under_market" not in lines
        assert "asian_handicap_market" not in lines
        assert [key for key, value in lines.items() if not value] == []
        assert any(key.startswith("asian_handicap_") and key != "asian_handicap_0_market" for key in lines)
        assert lines.get("over_under_44_0_market")
        assert lines.get("over_under_64_5_market")
