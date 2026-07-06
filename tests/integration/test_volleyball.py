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

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

SUPERLEGA_MATCH = {
    "sport": "volleyball",
    "league": "italy-superlega",
    "match_id": "piacenza-IXfYN7pB",
    "url": "https://www.oddsportal.com/volleyball/h2h/perugia-EJS1lfOD/piacenza-IXfYN7pB/#I9QUfUfB",
}


@pytest.mark.integration
class TestVolleyballBasicMarkets:
    """Regression tests for volleyball odds extraction (home_away_market must be non-empty)."""

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
            pytest.skip(f"Fixture not available: {fixture_name} — see module docstring")

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

        # Regression guard: volleyball must store odds, not just match metadata.
        home_away = actual[0].get("home_away_market")
        assert home_away, "Volleyball regression: home_away_market missing — scraper stored metadata only"

        # End-to-end coverage for match_info: this playoff match carries a populated
        # eventData.staticInfo (the only captured fixture that does).
        assert actual[0].get("match_info") == "Perugia wins series 3-0., Third leg."

        expected = load_fixture(
            SUPERLEGA_MATCH["sport"],
            SUPERLEGA_MATCH["league"],
            SUPERLEGA_MATCH["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
