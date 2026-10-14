"""Integration tests for handball scraping.

Regression guard for the Reddit 'Bettet' issue: handball must STORE ODDS,
not just match results. The 1x2_market field must be non-empty.

A real fixture + HAR were captured from the Bundesliga 2025/2026
SC Magdeburg vs Hamburg match (see BUNDESLIGA_MATCH). The match URL is an
H2H fragment URL (/handball/h2h/<team1-id>/<team2-id>/#<match-id>), but unlike
the NBA/real-madrid-barcelona H2H pages this historic match replays cleanly
from its HAR (no runtime-cache-buster redirect chain), so this test runs
deterministically in default HAR-replay mode — it is NOT marked live_only.
Run with --live to exercise it against the real site, or refresh the
fixture with:

    uv run python -m tests.integration.helpers.capture --sport handball \
        --league germany-bundesliga \
        --match-url "https://www.oddsportal.com/handball/h2h/hsv-hamburg-2XSOzhbr/sc-magdeburg-t8qpYkr1/#vglQ4eEN" \
        --markets "1x2" \
        --period "full_time" \
        --bookies-filter "all" \
        --capture-har
"""

import pytest

from tests.integration.helpers.replay import replay_and_compare

BUNDESLIGA_MATCH = {
    "sport": "handball",
    "league": "germany-bundesliga",
    "match_id": "sc-magdeburg-t8qpYkr1",
    "url": "https://www.oddsportal.com/handball/h2h/hsv-hamburg-2XSOzhbr/sc-magdeburg-t8qpYkr1/#vglQ4eEN",
}


@pytest.mark.integration
class TestHandballBasicMarkets:
    """Regression tests for handball odds extraction.

    Guards the 'Bettet' regression: handball scraping must produce a non-empty
    1x2_market, not just match metadata.
    """

    def test_hb_001_1x2_full_time(self, har_for_match, tmp_path):
        """HB-001: Handball 1x2 market, full time, all bookies — odds must be present."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            BUNDESLIGA_MATCH,
            "1x2_full_time_all.json",
            markets=["1x2"],
            period="full_time",
            bookies_filter="all",
        )

    def test_hb_002_umbrellas(self, har_for_match, tmp_path):
        """HB-002: over_under and asian_handicap open every rendered line, whole lines included (issue #115)."""
        actual = replay_and_compare(
            har_for_match,
            tmp_path,
            BUNDESLIGA_MATCH,
            "asian_handicap_over_under_full_time_all.json",
            markets=["over_under", "asian_handicap"],
            period="full_time",
        )
        lines = {key: value for key, value in actual[0].items() if key.endswith("_market")}

        assert "over_under_market" not in lines
        assert "asian_handicap_market" not in lines
        assert [key for key, value in lines.items() if not value] == []
        assert any(key.startswith("over_under_") for key in lines)
        assert any(key.startswith("handicap_") and key != "handicap_0_market" for key in lines)
        assert lines.get("over_under_62_0_market")
        assert lines.get("over_under_30_5_market")
