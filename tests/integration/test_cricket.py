"""Integration tests for cricket scraping.

Since the 2026-08 redesign, cricket match pages carry a per-bookmaker odds table like the
other sports (docs/agentic-gotchas.md §19, which supersedes the empty-market rule of §14).
The test compares the full golden, then checks the teams and league and that
`home_away_market` is non-empty with a bookmaker name on every entry.

The fixture + HAR were captured via a non-France proxy (OddsPortal geo-hides cricket
listings from France). Refresh with:

    uv run python -m tests.integration.helpers.capture --sport cricket \
        --league one-day-international \
        --match-url "https://www.oddsportal.com/cricket/h2h/england-UJC5mtAU/india-fcOzl2uI/" \
        --markets "home_away" --period "full_including_ot" \
        --bookies-filter "all" --season current --capture-har --proxy-url http://<proxy>
"""

import pytest

from tests.integration.helpers.replay import replay_and_compare

ENGLAND_INDIA_MATCH = {
    "sport": "cricket",
    "league": "one-day-international",
    "match_id": "india-fcOzl2uI",
    "url": "https://www.oddsportal.com/cricket/h2h/england-UJC5mtAU/india-fcOzl2uI/",
}


@pytest.mark.integration
class TestCricketBasicMarkets:
    """Regression tests for cricket scraping (metadata and per-bookmaker odds)."""

    def test_ck_001_home_away_full_including_ot(self, har_for_match, tmp_path):
        """CK-001: Cricket home_away, full match, all bookies: metadata and per-bookmaker odds."""
        actual = replay_and_compare(
            har_for_match,
            tmp_path,
            ENGLAND_INDIA_MATCH,
            "home_away_full_including_ot_all.json",
            markets=["home_away"],
            period="full_including_ot",
            bookies_filter="all",
            season="current",
        )

        # Metadata must be extracted correctly (the wiring works end-to-end).
        assert actual[0].get("home_team") == "England"
        assert actual[0].get("away_team") == "India"
        assert actual[0].get("league_name") == "One Day International"

        # Since the 2026-08 redesign cricket detail pages DO render a per-bookmaker
        # odds table (they did not before — gotchas §14). Guard odds presence like
        # the other sports.
        home_away = actual[0].get("home_away_market")
        assert home_away, "Cricket regression: home_away_market missing — scraper stored metadata only"
        assert all(e.get("bookmaker_name") for e in home_away)
