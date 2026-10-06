"""Integration tests for CLI options (format, bookies-filter), replayed from the match fixtures' HARs."""

import csv
import json
from pathlib import Path

import pytest

from tests.integration.helpers.replay import replay_and_compare

FOOTBALL_MATCH_URL = "https://www.oddsportal.com/football/h2h/brentford-xYe7DwID/leicester-KrrdAMyI/#xQ77QTN0"
BASKETBALL_MATCH_URL = (
    "https://www.oddsportal.com/basketball/h2h/boston-celtics-KYD9hVEm/los-angeles-lakers-ngegZ8bg/#0fwUQJEk"
)
TENNIS_MATCH_URL = "https://www.oddsportal.com/tennis/h2h/djokovic-novak-AZg49Et9/sinner-jannik-6HdC3z4H/#IwSMNP62"

# (sport, league, match dir) of each URL's committed fixtures.
FOOTBALL_FIXTURES = ("football", "premier-league", "leicester-brentford-xQ77QTN0")
BASKETBALL_FIXTURES = ("basketball", "nba", "los-angeles-lakers-boston-celtics-0fwUQJEk")
TENNIS_FIXTURES = ("tennis", "australian-open", "djokovic-novak-sinner-jannik-IwSMNP62")


@pytest.mark.integration
class TestOutputFormatJSON:
    """Tests for JSON output format (default)."""

    def test_opt_json_output_football(
        self,
        run_scraper,
        temp_output_dir,
        har_for_match,
    ):
        """Test JSON output format for football."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2"],
            output_path=output_path,
            output_format="json",
            har_path=har_for_match(*FOOTBALL_FIXTURES, "1x2_full_time_all.json"),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        json_path = Path(f"{output_path}.json")
        assert json_path.exists(), "JSON output not created"

        with open(json_path) as f:
            data = json.load(f)

        assert isinstance(data, list), "JSON should contain a list"
        assert len(data) >= 1, "JSON has no matches"
        assert "home_team" in data[0], "Missing home_team field"
        assert "away_team" in data[0], "Missing away_team field"


@pytest.mark.integration
class TestOutputFormatCSV:
    """Tests for CSV output format."""

    def test_opt_003_csv_output_football(
        self,
        run_scraper,
        temp_output_dir,
        har_for_match,
    ):
        """OPT-003: Test CSV output format for football."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2"],
            output_path=output_path,
            output_format="csv",
            har_path=har_for_match(*FOOTBALL_FIXTURES, "1x2_full_time_all.json"),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        csv_path = Path(f"{output_path}.csv")
        assert csv_path.exists(), "CSV output not created"

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) >= 1, "CSV has no data rows"
        # Check for common field names (may vary in casing)
        fieldnames_lower = [f.lower() for f in reader.fieldnames]
        assert any("home" in f for f in fieldnames_lower), "Missing home team field"

    def test_opt_004_csv_output_basketball(
        self,
        run_scraper,
        temp_output_dir,
        har_for_match,
    ):
        """OPT-004: Test CSV output format for basketball."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="basketball",
            match_link=BASKETBALL_MATCH_URL,
            markets=["home_away"],
            output_path=output_path,
            output_format="csv",
            har_path=har_for_match(*BASKETBALL_FIXTURES, "home_away_full_including_ot_all.json"),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        csv_path = Path(f"{output_path}.csv")
        assert csv_path.exists(), "CSV output not created"

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) >= 1, "CSV has no data rows"

    def test_opt_005_csv_output_tennis(
        self,
        run_scraper,
        temp_output_dir,
        har_for_match,
    ):
        """OPT-005: Test CSV output format for tennis."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="tennis",
            match_link=TENNIS_MATCH_URL,
            markets=["match_winner"],
            output_path=output_path,
            output_format="csv",
            har_path=har_for_match(*TENNIS_FIXTURES, "match_winner_full_time_all.json"),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        csv_path = Path(f"{output_path}.csv")
        assert csv_path.exists(), "CSV output not created"

        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) >= 1, "CSV has no data rows"


@pytest.mark.integration
class TestBookiesFilter:
    """Tests for --bookies-filter option."""

    def test_opt_001_classic_bookies(
        self,
        run_scraper,
        temp_output_dir,
        har_for_match,
    ):
        """OPT-001: Test classic bookies filter."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2"],
            output_path=output_path,
            bookies_filter="classic",
            har_path=har_for_match(*FOOTBALL_FIXTURES, "1x2_full_time_classic.json"),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        assert len(actual) >= 1, "No matches returned"
        # Verify output has odds data (market data is stored as {market}_market)
        market_data = actual[0].get("1x2_market", [])
        assert market_data, "No odds data in output"

    def test_opt_002_crypto_bookies(self, temp_output_dir, har_for_match):
        """OPT-002: the crypto panel's bookmakers, as the golden captured them."""
        replay_and_compare(
            har_for_match,
            temp_output_dir,
            {
                "sport": "football",
                "league": "premier-league",
                "match_id": FOOTBALL_FIXTURES[2],
                "url": FOOTBALL_MATCH_URL,
            },
            "1x2_full_time_crypto.json",
            markets=["1x2"],
            bookies_filter="crypto",
        )

    def test_opt_all_bookies(
        self,
        run_scraper,
        temp_output_dir,
        har_for_match,
    ):
        """Test all bookies filter (default)."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2"],
            output_path=output_path,
            bookies_filter="all",
            har_path=har_for_match(*FOOTBALL_FIXTURES, "1x2_full_time_all.json"),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        assert len(actual) >= 1, "No matches returned"
        market_data = actual[0].get("1x2_market", [])
        assert market_data, "No odds data in output"
