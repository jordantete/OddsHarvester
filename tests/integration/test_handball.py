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
        --season 2024-2025 \
        --capture-har
"""

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

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

    def test_hb_001_1x2_full_time(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """HB-001: Handball 1x2 market, full time, all bookies — odds must be present."""
        fixture_name = "1x2_full_time_all.json"

        if not fixture_exists(
            BUNDESLIGA_MATCH["sport"],
            BUNDESLIGA_MATCH["league"],
            BUNDESLIGA_MATCH["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name} — see module docstring")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="handball",
            match_link=BUNDESLIGA_MATCH["url"],
            markets=["1x2"],
            output_path=output_path,
            period="full_time",
            bookies_filter="all",
            har_path=har_for_match(
                BUNDESLIGA_MATCH["sport"],
                BUNDESLIGA_MATCH["league"],
                BUNDESLIGA_MATCH["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        # Regression guard: handball must store odds, not just match metadata.
        one_x_two = actual[0].get("1x2_market")
        assert one_x_two, "Handball regression: 1x2_market missing — scraper stored metadata only"

        expected = load_fixture(
            BUNDESLIGA_MATCH["sport"],
            BUNDESLIGA_MATCH["league"],
            BUNDESLIGA_MATCH["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
