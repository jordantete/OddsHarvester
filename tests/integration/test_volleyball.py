"""Integration tests for volleyball scraping.

Regression guard: volleyball must STORE ODDS, not just match metadata.
The home_away_market field must be non-empty.

A real fixture + HAR were captured from the SuperLega 2024/2025
Piacenza vs Perugia match (see SUPERLEGA_MATCH). The match URL is an H2H
fragment URL (/volleyball/h2h/<team1-id>/<team2-id>/#<match-id>), but unlike
the NBA/real-madrid-barcelona H2H pages this historic match replays cleanly
from its HAR (no runtime-cache-buster redirect chain), so this test runs
deterministically in default HAR-replay mode — it is NOT marked live_only.
Run with --live to exercise it against the real site, or refresh the
fixture with:

    uv run python -m tests.integration.helpers.capture --sport volleyball \
        --league italy-superlega \
        --match-url "https://www.oddsportal.com/volleyball/h2h/perugia-EJS1lfOD/piacenza-IXfYN7pB/#I9QUfUfB" \
        --markets "home_away" \
        --period "full_time" \
        --bookies-filter "all" \
        --season 2024-2025 \
        --capture-har
"""

import pytest

from tests.integration.helpers.replay import replay_and_compare

SUPERLEGA_MATCH = {
    "sport": "volleyball",
    "league": "italy-superlega",
    "match_id": "piacenza-IXfYN7pB",
    "url": "https://www.oddsportal.com/volleyball/h2h/perugia-EJS1lfOD/piacenza-IXfYN7pB/#I9QUfUfB",
}


@pytest.mark.integration
class TestVolleyballBasicMarkets:
    """Regression tests for volleyball odds extraction (home_away_market must be non-empty)."""

    def test_vb_001_home_away_full_time(self, har_for_match, tmp_path):
        """VB-001: Volleyball home_away market, full time, all bookies — odds must be present."""
        actual = replay_and_compare(
            har_for_match,
            tmp_path,
            SUPERLEGA_MATCH,
            "home_away_full_time_all.json",
            markets=["home_away"],
            period="full_time",
            bookies_filter="all",
        )

        # Regression guard: volleyball must store odds, not just match metadata.
        home_away = actual[0].get("home_away_market")
        assert home_away, "Volleyball regression: home_away_market missing — scraper stored metadata only"

        # match_info is always None since the 2026-08 redesign: the react-event-header
        # JSON (eventData.staticInfo) no longer exists and the DOM carries no
        # equivalent note. Locked in as a known data regression (issue #85).
        assert actual[0].get("match_info") is None
