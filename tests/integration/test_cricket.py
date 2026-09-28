"""Integration tests for cricket scraping.

Unlike every other sport, OddsPortal does NOT expose a per-bookmaker odds table on
cricket match-detail pages. Cricket detail pages render "No odds available for this
match" and their `home_away_market` comes back empty, even for marquee internationals
(verified on England vs India, One Day International) and even through a non-France
proxy. The listing pages show aggregate teaser odds only. See docs/agentic-gotchas.md.

So this test is the inverse of the other sports' regression guards: it asserts that
cricket scraping extracts match metadata correctly end-to-end (teams, league,
structure) AND that `home_away_market` is empty, which is the real, current OddsPortal
behavior. It guards the cricket wiring (a parsing regression would corrupt the metadata
or crash) without asserting odds that the source does not provide.

The fixture + HAR were captured via a non-France proxy (OddsPortal geo-hides cricket
listings from France; the detail odds are absent from every region). Refresh with:

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
    """Regression tests for cricket scraping (metadata extraction; odds absent on OddsPortal)."""

    def test_ck_001_home_away_full_including_ot(self, har_for_match, tmp_path):
        """CK-001: Cricket home_away, full match, all bookies.

        Metadata must be extracted correctly; home_away_market is empty because
        OddsPortal exposes no per-bookmaker odds table for cricket.
        """
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
