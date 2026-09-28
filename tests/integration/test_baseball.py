"""Integration tests for baseball scraping.

Covers issue #60 — H2H fragment match_date correctness on MLB historic scrapes.
"""

import pytest

from tests.integration.helpers.comparison import compare_match_data
from tests.integration.helpers.replay import load_golden, run_replay

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

    def test_bb_mlb_001_royals_mariners_h2h_fragment(self, har_for_match, tmp_path):
        """Match_date in output must match the fragment-targeted historic match."""
        fixture_name = "home_away_full_time_all.json"
        actual = run_replay(
            har_for_match,
            tmp_path,
            ROYALS_MARINERS,
            fixture_name,
            markets=["home_away"],
            period="full_time",
        )

        # Hard guard against the issue regressing: the buggy upcoming-match date
        # must never appear, regardless of fixture freshness. Runs before the golden
        # compare since this test is live_only, where golden drift is expected.
        assert "2026-05-22 23:40:00" not in (actual[0].get("match_date") or ""), (
            f"Issue #60 regressed: match_date is the upcoming-match date: {actual[0]['match_date']}"
        )

        result = compare_match_data(actual[0], load_golden(ROYALS_MARINERS, fixture_name)[0])
        assert result.passed, str(result)
