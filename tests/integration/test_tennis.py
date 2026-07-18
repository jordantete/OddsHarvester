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

    @pytest.mark.live_only
    def test_tn_001_match_winner(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
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
            har_path=har_for_match(
                DJOKOVIC_SINNER["sport"], DJOKOVIC_SINNER["league"], DJOKOVIC_SINNER["match_id"], fixture_name
            ),
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

    @pytest.mark.live_only
    def test_tn_002_multiple_markets(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
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
            har_path=har_for_match(
                DJOKOVIC_SINNER["sport"], DJOKOVIC_SINNER["league"], DJOKOVIC_SINNER["match_id"], fixture_name
            ),
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
        har_for_match,
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
            har_path=har_for_match(
                DJOKOVIC_LEHECKA["sport"], DJOKOVIC_LEHECKA["league"], DJOKOVIC_LEHECKA["match_id"], fixture_name
            ),
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

    def test_tn_006_local_kickoff_multi_timezone(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """TN-006: --local-kickoff resolves a multi-timezone country by host city (Melbourne)."""
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
            local_kickoff=True,
            har_path=har_for_match(
                DJOKOVIC_LEHECKA["sport"], DJOKOVIC_LEHECKA["league"], DJOKOVIC_LEHECKA["match_id"], fixture_name
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            record = json.load(f)[0]

        # Australia is multi-timezone; resolution goes through the host-city lookup.
        assert record["venue_timezone"] == "Australia/Melbourne"
        # Melbourne is AEDT (UTC+11) in January; kickoff 08:15 UTC -> 19:15 local.
        assert record["match_date_venue_local"].startswith("2025-01-19 19:15:00")
        assert "+1100" in record["match_date_venue_local"]
        # UTC value stays canonical.
        assert record["match_date"].endswith("UTC")

    def test_tn_004_over_under_games(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
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
            har_path=har_for_match(
                DJOKOVIC_LEHECKA["sport"], DJOKOVIC_LEHECKA["league"], DJOKOVIC_LEHECKA["match_id"], fixture_name
            ),
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
        har_for_match,
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
            har_path=har_for_match(
                HUMBERT_ZVEREV["sport"], HUMBERT_ZVEREV["league"], HUMBERT_ZVEREV["match_id"], fixture_name
            ),
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

    @pytest.mark.live_only
    def test_tn_006_1st_set(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
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
            har_path=har_for_match(
                DJOKOVIC_SINNER["sport"], DJOKOVIC_SINNER["league"], DJOKOVIC_SINNER["match_id"], fixture_name
            ),
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
