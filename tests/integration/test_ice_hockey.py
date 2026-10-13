"""Integration tests for ice hockey scraping."""

import pytest

from tests.integration.helpers.replay import replay_and_compare

KHL_MATCH = {
    "sport": "ice-hockey",
    "league": "khl",
    "match_id": "bars-kazan-sochi-bVwZOEbc",
    "url": "https://www.oddsportal.com/hockey/h2h/bars-kazan-v320kOMr/sochi-zu1IGfCr/#bVwZOEbc",
}


@pytest.mark.integration
class TestIceHockeyUmbrella:
    def test_ih_001_over_under_umbrella(self, har_for_match, tmp_path):
        """IH-001: over_under opens every rendered line, whole lines included (issue #115)."""
        actual = replay_and_compare(
            har_for_match,
            tmp_path,
            KHL_MATCH,
            "over_under_full_time_all.json",
            markets=["over_under"],
            period="full_time",
        )
        lines = {key: value for key, value in actual[0].items() if key.endswith("_market")}

        assert "over_under_market" not in lines
        assert [key for key, value in lines.items() if not value] == []
        assert lines.get("over_under_5_0_market")
