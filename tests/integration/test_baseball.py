"""Integration tests for baseball scraping.

Covers issue #60 — H2H fragment match_date correctness on MLB historic scrapes.
"""

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

ROYALS_MARINERS = {
    "sport": "baseball",
    "league": "mlb",
    "match_id": "kansas-city-royals-IL2QbgJ4-seattle-mariners-txYPhSac",
    "url": ("https://www.oddsportal.com/baseball/h2h/kansas-city-royals-IL2QbgJ4/seattle-mariners-txYPhSac/#WbDmMwm1"),
}


@pytest.mark.integration
@pytest.mark.live_only
class TestBaseballH2HFragment:
    """Issue #60: match_date must be the fragment-targeted match, not the next upcoming H2H."""

    def test_bb_mlb_001_royals_mariners_h2h_fragment(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """Match_date in output must match the fragment-targeted historic match."""
        fixture_name = "home_away_full_time_all.json"

        if not fixture_exists(
            ROYALS_MARINERS["sport"],
            ROYALS_MARINERS["league"],
            ROYALS_MARINERS["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="baseball",
            match_link=ROYALS_MARINERS["url"],
            markets=["home_away"],
            output_path=output_path,
            period="full_time",
            har_path=har_for_match(
                ROYALS_MARINERS["sport"],
                ROYALS_MARINERS["league"],
                ROYALS_MARINERS["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            ROYALS_MARINERS["sport"],
            ROYALS_MARINERS["league"],
            ROYALS_MARINERS["match_id"],
            fixture_name,
        )

        # Hard guard against the issue regressing: the buggy upcoming-match date
        # must never appear, regardless of fixture freshness.
        assert "2026-05-22 23:40:00" not in (actual[0].get("match_date") or ""), (
            f"Issue #60 regressed: match_date is the upcoming-match date: {actual[0]['match_date']}"
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
