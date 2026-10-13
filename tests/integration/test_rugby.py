"""Integration tests for rugby league and rugby union scraping."""

import pytest

from tests.integration.helpers.replay import replay_and_compare

NRL_MATCH = {
    "sport": "rugby-league",
    "league": "australia-nrl",
    "match_id": "newcastle-knights-sydney-roosters-CA9Z7lzR",
    "url": "https://www.oddsportal.com/rugby-league/h2h/newcastle-knights-YqPIXNl6/sydney-roosters-AHjFxceb/#CA9Z7lzR",
}

TOP_14_MATCH = {
    "sport": "rugby-union",
    "league": "france-top-14",
    "match_id": "aviron-bayonnais-stade-toulousain-fXeSq7ek",
    "url": "https://www.oddsportal.com/rugby-union/h2h/aviron-bayonnais-8E1xxyQA/stade-toulousain-2LK4pW1j/#fXeSq7ek",
}


@pytest.mark.integration
class TestRugbyUmbrellas:
    @pytest.mark.parametrize(
        ("match", "new_lines"),
        [
            (NRL_MATCH, ("handicap_-2_5_market", "handicap_-18_5_market")),
            (TOP_14_MATCH, ("over_under_53_5_market", "handicap_-40_5_market", "over_under_79_5_market")),
        ],
        ids=["rugby-league", "rugby-union"],
    )
    def test_rg_001_umbrellas(self, har_for_match, tmp_path, match, new_lines):
        """RG-001: over_under and handicap open every rendered line, the ones the old ladder missed included."""
        actual = replay_and_compare(
            har_for_match,
            tmp_path,
            match,
            "handicap_over_under_full_time_all.json",
            markets=["over_under", "handicap"],
            period="full_time",
        )
        lines = {key: value for key, value in actual[0].items() if key.endswith("_market")}

        assert "over_under_market" not in lines
        assert "handicap_market" not in lines
        assert [key for key, value in lines.items() if not value] == []
        assert any(key.startswith("over_under_") for key in lines)
        assert any(key.startswith("handicap_") for key in lines)
        assert [key for key in new_lines if not lines.get(key)] == []
