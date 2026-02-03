"""Integration tests for tennis scraping."""

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

# Match configurations
DJOKOVIC_SINNER = {
    "sport": "tennis",
    "league": "australian-open",
    "match_id": "djokovic-novak-sinner-jannik-IwSMNP62",
    "url": "https://www.oddsportal.com/tennis/australia/atp-australian-open-2024/djokovic-novak-sinner-jannik-IwSMNP62/",
}

DJOKOVIC_LEHECKA = {
    "sport": "tennis",
    "league": "australian-open",
    "match_id": "djokovic-novak-lehecka-jiri-0ShOHpqe",
    "url": "https://www.oddsportal.com/tennis/australia/atp-australian-open/djokovic-novak-lehecka-jiri-0ShOHpqe/",
}

HUMBERT_ZVEREV = {
    "sport": "tennis",
    "league": "australian-open",
    "match_id": "humbert-ugo-zverev-alexander-MssXFOD7",
    "url": "https://www.oddsportal.com/tennis/australia/atp-australian-open/humbert-ugo-zverev-alexander-MssXFOD7/",
}


@pytest.mark.integration
class TestTennisBasicMarkets:
    """Tests for basic tennis markets."""

    def test_tn_001_match_winner(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """TN-001: Test match_winner market - Djokovic vs Sinner."""
        fixture_name = "match_winner_full_time_all.json"

        if not fixture_exists(
            DJOKOVIC_SINNER["sport"],
            DJOKOVIC_SINNER["league"],
            DJOKOVIC_SINNER["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="tennis",
            match_link=DJOKOVIC_SINNER["url"],
            markets=["match_winner"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            DJOKOVIC_SINNER["sport"],
            DJOKOVIC_SINNER["league"],
            DJOKOVIC_SINNER["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_tn_002_multiple_markets(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """TN-002: Test match_winner + over_under_sets markets."""
        fixture_name = "match_winner_over_under_sets_2_5_full_time_all.json"

        if not fixture_exists(
            DJOKOVIC_SINNER["sport"],
            DJOKOVIC_SINNER["league"],
            DJOKOVIC_SINNER["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="tennis",
            match_link=DJOKOVIC_SINNER["url"],
            markets=["match_winner", "over_under_sets_2_5"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            DJOKOVIC_SINNER["sport"],
            DJOKOVIC_SINNER["league"],
            DJOKOVIC_SINNER["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_tn_003_djokovic_lehecka(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """TN-003: Test Djokovic vs Lehecka."""
        fixture_name = "match_winner_full_time_all.json"

        if not fixture_exists(
            DJOKOVIC_LEHECKA["sport"],
            DJOKOVIC_LEHECKA["league"],
            DJOKOVIC_LEHECKA["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="tennis",
            match_link=DJOKOVIC_LEHECKA["url"],
            markets=["match_winner"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            DJOKOVIC_LEHECKA["sport"],
            DJOKOVIC_LEHECKA["league"],
            DJOKOVIC_LEHECKA["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_tn_004_over_under_games(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """TN-004: Test over/under games market."""
        fixture_name = "over_under_games_22_5_full_time_all.json"

        if not fixture_exists(
            DJOKOVIC_LEHECKA["sport"],
            DJOKOVIC_LEHECKA["league"],
            DJOKOVIC_LEHECKA["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="tennis",
            match_link=DJOKOVIC_LEHECKA["url"],
            markets=["over_under_games_22_5"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            DJOKOVIC_LEHECKA["sport"],
            DJOKOVIC_LEHECKA["league"],
            DJOKOVIC_LEHECKA["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)

    def test_tn_005_humbert_zverev(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """TN-005: Test Humbert vs Zverev."""
        fixture_name = "match_winner_full_time_all.json"

        if not fixture_exists(
            HUMBERT_ZVEREV["sport"],
            HUMBERT_ZVEREV["league"],
            HUMBERT_ZVEREV["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="tennis",
            match_link=HUMBERT_ZVEREV["url"],
            markets=["match_winner"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            HUMBERT_ZVEREV["sport"],
            HUMBERT_ZVEREV["league"],
            HUMBERT_ZVEREV["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)


@pytest.mark.integration
class TestTennisPeriods:
    """Tests for tennis period options."""

    def test_tn_006_1st_set(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
    ):
        """TN-006: Test match_winner market, 1st set - Djokovic vs Sinner."""
        fixture_name = "match_winner_1st_set_all.json"

        if not fixture_exists(
            DJOKOVIC_SINNER["sport"],
            DJOKOVIC_SINNER["league"],
            DJOKOVIC_SINNER["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not available: {fixture_name}")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="tennis",
            match_link=DJOKOVIC_SINNER["url"],
            markets=["match_winner"],
            output_path=output_path,
            period="1st_set",
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        expected = load_fixture(
            DJOKOVIC_SINNER["sport"],
            DJOKOVIC_SINNER["league"],
            DJOKOVIC_SINNER["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
