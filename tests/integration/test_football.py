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

    def test_fb_007_real_madrid_barcelona(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
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
