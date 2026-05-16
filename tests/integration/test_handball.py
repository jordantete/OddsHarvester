"""Integration tests for handball scraping.

Regression guard for the Reddit 'Bettet' issue: handball must STORE ODDS,
not just match results. The 1x2 odds field must be non-empty.

NOTE: fixture not yet captured — all handball leagues on OddsPortal use
H2H fragment URLs (/handball/h2h/<team1-id>/<team2-id>/#<match-id>), which
cannot be replayed deterministically from HAR (same limitation as NBA/baseball
H2H tests, marked live_only). Capture with a direct match URL once OddsPortal
exposes one, or run with --live against an H2H URL:

    uv run python -m tests.integration.helpers.capture --sport handball \
        --league ehf-champions-league \
        --match-url "<MATCH_URL>" \
        --markets "1x2" \
        --period "full_time" \
        --bookies-filter "all" \
        --capture-har
"""

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

# NOTE: fixture not yet captured — see module docstring for capture instructions.
# The fixture_exists guard below makes this test SKIP (not fail) until a fixture
# is available.
EHF_MATCH = {
    "sport": "handball",
    "league": "ehf-champions-league",
    "match_id": "PLACEHOLDER_CAPTURE_PENDING",
    "url": "https://www.oddsportal.com/handball/europe/ehf-champions-league/",
}


@pytest.mark.integration
class TestHandballBasicMarkets:
    """Regression tests for handball odds extraction.

    Guards the 'Bettet' regression: handball scraping must produce non-empty
    1x2 odds, not just match metadata.
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
            EHF_MATCH["sport"],
            EHF_MATCH["league"],
            EHF_MATCH["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not yet captured: {fixture_name} — see module docstring")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="handball",
            match_link=EHF_MATCH["url"],
            markets=["1x2"],
            output_path=output_path,
            period="full_time",
            bookies_filter="all",
            har_path=har_for_match(
                EHF_MATCH["sport"],
                EHF_MATCH["league"],
                EHF_MATCH["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        # Regression guard: handball must store odds, not just match metadata.
        assert actual[0].get("1x2") or (actual[0].get("odds") or {}).get(
            "1x2"
        ), "Handball regression: 1x2 odds missing — scraper stored metadata only"

        expected = load_fixture(
            EHF_MATCH["sport"],
            EHF_MATCH["league"],
            EHF_MATCH["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
