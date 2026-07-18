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

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

ENGLAND_INDIA_MATCH = {
    "sport": "cricket",
    "league": "one-day-international",
    "match_id": "india-fcOzl2uI",
    "url": "https://www.oddsportal.com/cricket/h2h/england-UJC5mtAU/india-fcOzl2uI/",
}


@pytest.mark.integration
class TestCricketBasicMarkets:
    """Regression tests for cricket scraping (metadata extraction; odds absent on OddsPortal)."""

    def test_ck_001_home_away_full_including_ot(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """CK-001: Cricket home_away, full match, all bookies.

        Metadata must be extracted correctly; home_away_market is empty because
        OddsPortal exposes no per-bookmaker odds table for cricket.
        """
        fixture_name = "home_away_full_including_ot_all.json"

        if not fixture_exists(
            ENGLAND_INDIA_MATCH["sport"],
            ENGLAND_INDIA_MATCH["league"],
            ENGLAND_INDIA_MATCH["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name} — see module docstring")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="cricket",
            match_link=ENGLAND_INDIA_MATCH["url"],
            markets=["home_away"],
            output_path=output_path,
            period="full_including_ot",
            bookies_filter="all",
            season="current",
            har_path=har_for_match(
                ENGLAND_INDIA_MATCH["sport"],
                ENGLAND_INDIA_MATCH["league"],
                ENGLAND_INDIA_MATCH["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        # Metadata must be extracted correctly (the wiring works end-to-end).
        assert actual[0].get("home_team") == "England"
        assert actual[0].get("away_team") == "India"
        assert actual[0].get("league_name") == "One Day International"

        # Documented OddsPortal behavior: cricket detail pages carry no per-bookmaker
        # odds table, so home_away_market is empty. This is the inverse of the other
        # sports' non-empty odds guard.
        assert actual[0].get("home_away_market") == [], (
            "Cricket now returns odds — OddsPortal may have added a cricket odds table; "
            "revisit the home_away registration and this assertion (see module docstring)."
        )

        expected = load_fixture(
            ENGLAND_INDIA_MATCH["sport"],
            ENGLAND_INDIA_MATCH["league"],
            ENGLAND_INDIA_MATCH["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
