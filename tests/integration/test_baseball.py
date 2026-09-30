"""Integration tests for baseball scraping.

Covers issue #60 — H2H fragment match_date correctness on MLB historic scrapes.
"""

import pytest

from tests.integration.helpers.comparison import compare_golden
from tests.integration.helpers.replay import is_live, load_golden, run_replay

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
        fixture_name = "home_away_full_including_ot_all.json"
        actual = run_replay(
            har_for_match,
            tmp_path,
            ROYALS_MARINERS,
            fixture_name,
            markets=["home_away"],
            period="full_including_ot",
        )

        # Hard guard against the issue regressing: the buggy upcoming-match date
        # must never appear, regardless of fixture freshness.
        assert "2026-05-22 23:40:00" not in (actual[0].get("match_date") or ""), (
            f"Issue #60 regressed: match_date is the upcoming-match date: {actual[0]['match_date']}"
        )

        golden = load_golden(ROYALS_MARINERS, fixture_name)[0]

        # A finished match's kickoff does not move, so this still catches the JSON-LD trap
        # under --live, where compare_golden ignores match_date as part of structure-only compare.
        assert actual[0]["match_date"] == golden["match_date"], (
            f"Issue #60 regressed: match_date {actual[0]['match_date']} "
            f"is not the captured kickoff {golden['match_date']}"
        )

        live = is_live(har_for_match, ROYALS_MARINERS, fixture_name)
        result = compare_golden(actual[0], golden, live=live)
        assert result.passed, str(result)
