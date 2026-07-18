"""Integration tests for football scraping."""

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

# Match configurations
LEICESTER_BRENTFORD = {
    "sport": "football",
    "league": "premier-league",
    "match_id": "leicester-brentford-xQ77QTN0",
    "url": "https://www.oddsportal.com/football/england/premier-league/leicester-brentford-xQ77QTN0",
}

REAL_MADRID_BARCELONA = {
    "sport": "football",
    "league": "super-cup-2025",
    "match_id": "real-madrid-barcelona-bZrHkILa",
    "url": "https://www.oddsportal.com/football/spain/super-cup-2025/real-madrid-barcelona-bZrHkILa/",
}


@pytest.mark.integration
class TestFootballBasicMarkets:
    """Tests for basic football markets."""

    def test_fb_001_1x2_full_time(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """FB-001: Test 1x2 market, full time, all bookies."""
        fixture_name = "1x2_full_time_all.json"

        if not fixture_exists(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="football",
            match_link=LEICESTER_BRENTFORD["url"],
            markets=["1x2"],
            output_path=output_path,
            period="full_time",
            bookies_filter="all",
            har_path=har_for_match(
                LEICESTER_BRENTFORD["sport"],
                LEICESTER_BRENTFORD["league"],
                LEICESTER_BRENTFORD["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_fb_002_multiple_markets(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """FB-002: Test 1x2 + btts + double_chance markets."""
        fixture_name = "1x2_btts_double_chance_full_time_all.json"

        if not fixture_exists(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="football",
            match_link=LEICESTER_BRENTFORD["url"],
            markets=["1x2", "btts", "double_chance"],
            output_path=output_path,
            har_path=har_for_match(
                LEICESTER_BRENTFORD["sport"],
                LEICESTER_BRENTFORD["league"],
                LEICESTER_BRENTFORD["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_fb_003_over_under(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """FB-003: Test over/under markets."""
        fixture_name = "over_under_1_5_over_under_2_5_full_time_all.json"

        if not fixture_exists(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="football",
            match_link=LEICESTER_BRENTFORD["url"],
            markets=["over_under_2_5", "over_under_1_5"],
            output_path=output_path,
            har_path=har_for_match(
                LEICESTER_BRENTFORD["sport"],
                LEICESTER_BRENTFORD["league"],
                LEICESTER_BRENTFORD["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_fb_004_over_under_umbrella(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """FB-004: Test the over_under umbrella token expands into per-line markets.

        Reuses the FB-003 fixture (captured for the explicit over_under_1_5 /
        over_under_2_5 lines) but requests the umbrella token `over_under` instead.
        The umbrella enumerates every O/U line rendered on the page and produces one
        `{token}_market` key per line rather than a single `over_under_market` key.
        Only the two lines this fixture was captured for are asserted here, since
        those are the ones guaranteed to carry real odds data under HAR replay.
        """
        fixture_name = "over_under_1_5_over_under_2_5_full_time_all.json"

        if not fixture_exists(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="football",
            match_link=LEICESTER_BRENTFORD["url"],
            markets=["over_under"],
            output_path=output_path,
            har_path=har_for_match(
                LEICESTER_BRENTFORD["sport"],
                LEICESTER_BRENTFORD["league"],
                LEICESTER_BRENTFORD["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

        record = actual[0]

        # Umbrella must expand into per-line keys, not collapse to a single market key.
        assert "over_under_market" not in record

        for line_key in ("over_under_1_5_market", "over_under_2_5_market"):
            assert line_key in record, f"Expected umbrella to produce '{line_key}'"
            assert record[line_key], f"'{line_key}' should be non-empty"
            assert record[line_key] == expected[0][line_key]

    def test_fb_008_local_kickoff(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """FB-008: Test --local-kickoff adds venue_timezone and match_date_venue_local, UTC untouched."""
        fixture_name = "1x2_full_time_all.json"

        if not fixture_exists(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="football",
            match_link=LEICESTER_BRENTFORD["url"],
            markets=["1x2"],
            output_path=output_path,
            period="full_time",
            bookies_filter="all",
            local_kickoff=True,
            har_path=har_for_match(
                LEICESTER_BRENTFORD["sport"],
                LEICESTER_BRENTFORD["league"],
                LEICESTER_BRENTFORD["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        record = actual[0]
        assert record["venue_timezone"] == "Europe/London"
        assert record["match_date_venue_local"] is not None
        assert record["match_date"].endswith("UTC")

    @pytest.mark.live_only
    def test_fb_007_real_madrid_barcelona(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """FB-007: Test Real Madrid vs Barcelona."""
        fixture_name = "1x2_btts_full_time_all.json"

        if not fixture_exists(
            REAL_MADRID_BARCELONA["sport"],
            REAL_MADRID_BARCELONA["league"],
            REAL_MADRID_BARCELONA["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="football",
            match_link=REAL_MADRID_BARCELONA["url"],
            markets=["1x2", "btts"],
            output_path=output_path,
            har_path=har_for_match(
                REAL_MADRID_BARCELONA["sport"],
                REAL_MADRID_BARCELONA["league"],
                REAL_MADRID_BARCELONA["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            REAL_MADRID_BARCELONA["sport"],
            REAL_MADRID_BARCELONA["league"],
            REAL_MADRID_BARCELONA["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)


@pytest.mark.integration
class TestFootballPeriods:
    """Tests for football period options."""

    def test_fb_005_1st_half(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """FB-005: Test 1x2 market, 1st half period."""
        fixture_name = "1x2_1st_half_all.json"

        if not fixture_exists(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="football",
            match_link=LEICESTER_BRENTFORD["url"],
            markets=["1x2"],
            output_path=output_path,
            period="1st_half",
            har_path=har_for_match(
                LEICESTER_BRENTFORD["sport"],
                LEICESTER_BRENTFORD["league"],
                LEICESTER_BRENTFORD["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)


@pytest.mark.integration
class TestFootballBookiesFilter:
    """Tests for football bookies filter option."""

    def test_fb_006_classic_bookies(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """FB-006: Test 1x2 market with classic bookies only."""
        fixture_name = "1x2_full_time_classic.json"

        if not fixture_exists(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="football",
            match_link=LEICESTER_BRENTFORD["url"],
            markets=["1x2"],
            output_path=output_path,
            bookies_filter="classic",
            har_path=har_for_match(
                LEICESTER_BRENTFORD["sport"],
                LEICESTER_BRENTFORD["league"],
                LEICESTER_BRENTFORD["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LEICESTER_BRENTFORD["sport"],
            LEICESTER_BRENTFORD["league"],
            LEICESTER_BRENTFORD["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
