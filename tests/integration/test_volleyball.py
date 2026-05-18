"""Integration tests for volleyball scraping.

Regression guard: volleyball must STORE ODDS, not just match metadata.
The home_away odds field must be non-empty.

NOTE: volleyball leagues on OddsPortal use H2H fragment URLs
(/volleyball/h2h/<team1-id>/<team2-id>/#<match-id>), which cannot be replayed
deterministically from HAR (same limitation as NBA/baseball/handball H2H tests).
This test is marked live_only and SKIPS in default HAR-replay mode. Run with
--live against a real H2H URL, or capture a fixture once a direct match URL is
available:

    uv run python -m tests.integration.helpers.capture --sport volleyball \
        --league italy-superlega \
        --match-url "<MATCH_URL>" \
        --markets "home_away" \
        --period "full_time" \
        --bookies-filter "all" \
        --capture-har
"""

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

SUPERLEGA_MATCH = {
    "sport": "volleyball",
    "league": "italy-superlega",
    "match_id": "PLACEHOLDER_CAPTURE_PENDING",
    "url": "https://www.oddsportal.com/volleyball/italy/superlega/",
}


@pytest.mark.integration
@pytest.mark.live_only
class TestVolleyballBasicMarkets:
    """Regression tests for volleyball odds extraction (home_away must be non-empty)."""

    def test_vb_001_home_away_full_time(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """VB-001: Volleyball home_away market, full time, all bookies — odds must be present."""
        fixture_name = "home_away_full_time_all.json"

        if not fixture_exists(
            SUPERLEGA_MATCH["sport"],
            SUPERLEGA_MATCH["league"],
            SUPERLEGA_MATCH["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not yet captured: {fixture_name} — see module docstring")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="volleyball",
            match_link=SUPERLEGA_MATCH["url"],
            markets=["home_away"],
            output_path=output_path,
            period="full_time",
            bookies_filter="all",
            har_path=har_for_match(
                SUPERLEGA_MATCH["sport"],
                SUPERLEGA_MATCH["league"],
                SUPERLEGA_MATCH["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        assert actual[0].get("home_away") or (actual[0].get("odds") or {}).get(
            "home_away"
        ), "Volleyball regression: home_away odds missing — scraper stored metadata only"

        expected = load_fixture(
            SUPERLEGA_MATCH["sport"],
            SUPERLEGA_MATCH["league"],
            SUPERLEGA_MATCH["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
