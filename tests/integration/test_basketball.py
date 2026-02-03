"""Integration tests for basketball scraping."""

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

# Match configurations
LAKERS_CELTICS = {
    "sport": "basketball",
    "league": "nba",
    "match_id": "los-angeles-lakers-boston-celtics-0fwUQJEk",
    "url": "https://www.oddsportal.com/basketball/usa/nba/los-angeles-lakers-boston-celtics-0fwUQJEk/",
}

LAKERS_WARRIORS = {
    "sport": "basketball",
    "league": "nba",
    "match_id": "los-angeles-lakers-golden-state-warriors-jZvOnVBk",
    "url": "https://www.oddsportal.com/basketball/usa/nba-2024-2025/los-angeles-lakers-golden-state-warriors-jZvOnVBk/",
}


@pytest.mark.integration
class TestBasketballBasicMarkets:
    """Tests for basic basketball markets."""

    def test_bb_001_home_away(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """BB-001: Test home_away market, full including OT."""
        fixture_name = "home_away_full_including_ot_all.json"

        if not fixture_exists(
            LAKERS_CELTICS["sport"],
            LAKERS_CELTICS["league"],
            LAKERS_CELTICS["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="basketball",
            match_link=LAKERS_CELTICS["url"],
            markets=["home_away"],
            output_path=output_path,
            period="full_including_ot",
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LAKERS_CELTICS["sport"],
            LAKERS_CELTICS["league"],
            LAKERS_CELTICS["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_bb_002_home_away_1x2(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """BB-002: Test home_away and 1x2 markets."""
        fixture_name = "1x2_home_away_full_including_ot_all.json"

        if not fixture_exists(
            LAKERS_CELTICS["sport"],
            LAKERS_CELTICS["league"],
            LAKERS_CELTICS["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="basketball",
            match_link=LAKERS_CELTICS["url"],
            markets=["home_away", "1x2"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LAKERS_CELTICS["sport"],
            LAKERS_CELTICS["league"],
            LAKERS_CELTICS["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_bb_003_lakers_warriors(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """BB-003: Test Lakers vs Warriors."""
        fixture_name = "home_away_full_including_ot_all.json"

        if not fixture_exists(
            LAKERS_WARRIORS["sport"],
            LAKERS_WARRIORS["league"],
            LAKERS_WARRIORS["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="basketball",
            match_link=LAKERS_WARRIORS["url"],
            markets=["home_away"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LAKERS_WARRIORS["sport"],
            LAKERS_WARRIORS["league"],
            LAKERS_WARRIORS["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)


@pytest.mark.integration
class TestBasketballPeriods:
    """Tests for basketball period options."""

    def test_bb_004_1st_half(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """BB-004: Test home_away market, 1st half."""
        fixture_name = "home_away_1st_half_all.json"

        if not fixture_exists(
            LAKERS_CELTICS["sport"],
            LAKERS_CELTICS["league"],
            LAKERS_CELTICS["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="basketball",
            match_link=LAKERS_CELTICS["url"],
            markets=["home_away"],
            output_path=output_path,
            period="1st_half",
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LAKERS_CELTICS["sport"],
            LAKERS_CELTICS["league"],
            LAKERS_CELTICS["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_bb_005_1st_quarter(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """BB-005: Test home_away market, 1st quarter."""
        fixture_name = "home_away_1st_quarter_all.json"

        if not fixture_exists(
            LAKERS_CELTICS["sport"],
            LAKERS_CELTICS["league"],
            LAKERS_CELTICS["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="basketball",
            match_link=LAKERS_CELTICS["url"],
            markets=["home_away"],
            output_path=output_path,
            period="1st_quarter",
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LAKERS_CELTICS["sport"],
            LAKERS_CELTICS["league"],
            LAKERS_CELTICS["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_bb_006_lakers_warriors_1st_half(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """BB-006: Test Lakers vs Warriors, 1st half."""
        fixture_name = "home_away_1st_half_all.json"

        if not fixture_exists(
            LAKERS_WARRIORS["sport"],
            LAKERS_WARRIORS["league"],
            LAKERS_WARRIORS["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="basketball",
            match_link=LAKERS_WARRIORS["url"],
            markets=["home_away"],
            output_path=output_path,
            period="1st_half",
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            LAKERS_WARRIORS["sport"],
            LAKERS_WARRIORS["league"],
            LAKERS_WARRIORS["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
