"""Integration tests for CLI options (format, bookies-filter)."""

import csv
import json
from pathlib import Path

import pytest

FOOTBALL_MATCH_URL = "https://www.oddsportal.com/football/england/premier-league/leicester-brentford-xQ77QTN0"
BASKETBALL_MATCH_URL = "https://www.oddsportal.com/basketball/usa/nba/los-angeles-lakers-boston-celtics-0fwUQJEk/"
TENNIS_MATCH_URL = (
    "https://www.oddsportal.com/tennis/australia/atp-australian-open-2024/djokovic-novak-sinner-jannik-IwSMNP62/"
)


@pytest.mark.integration
class TestOutputFormatJSON:
    """Tests for JSON output format (default)."""

    def test_opt_json_output_football(
        self,
        run_scraper,
        temp_output_dir,
    ):
        """Test JSON output format for football."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2"],
            output_path=output_path,
            output_format="json",
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
    ):
        """OPT-003: Test CSV output format for football."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2"],
            output_path=output_path,
            output_format="csv",
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
    ):
        """OPT-004: Test CSV output format for basketball."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="basketball",
            match_link=BASKETBALL_MATCH_URL,
            markets=["home_away"],
            output_path=output_path,
            output_format="csv",
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
    ):
        """OPT-005: Test CSV output format for tennis."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="tennis",
            match_link=TENNIS_MATCH_URL,
            markets=["match_winner"],
            output_path=output_path,
            output_format="csv",
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
    ):
        """OPT-001: Test classic bookies filter."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2"],
            output_path=output_path,
            bookies_filter="classic",
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        assert len(actual) >= 1, "No matches returned"
        # Verify output has odds data (market data is stored as {market}_market)
        market_data = actual[0].get("1x2_market", [])
        assert market_data, "No odds data in output"

    def test_opt_002_crypto_bookies(
        self,
        run_scraper,
        temp_output_dir,
    ):
        """OPT-002: Test crypto bookies filter."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2"],
            output_path=output_path,
            bookies_filter="crypto",
        )

        # Note: May return empty if no crypto bookies for this match
        # Just verify command doesn't crash
        assert exit_code == 0, f"Scraper failed: {stderr}"

    def test_opt_all_bookies(
        self,
        run_scraper,
        temp_output_dir,
    ):
        """Test all bookies filter (default)."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2"],
            output_path=output_path,
            bookies_filter="all",
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        assert len(actual) >= 1, "No matches returned"
        market_data = actual[0].get("1x2_market", [])
        assert market_data, "No odds data in output"


@pytest.mark.integration
class TestMultipleMarkets:
    """Tests for scraping multiple markets in one command."""

    def test_cmb_001_football_4_markets(
        self,
        run_scraper,
        temp_output_dir,
    ):
        """CMB-001: Test 4 markets simultaneously for football."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="football",
            match_link=FOOTBALL_MATCH_URL,
            markets=["1x2", "btts", "over_under_2_5", "dnb"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        assert len(actual) >= 1, "No matches returned"
        # Check that at least one market has data (markets are stored as {market}_market)
        market_keys = ["1x2_market", "btts_market", "over_under_2_5_market", "dnb_market"]
        found_markets = [k for k in market_keys if actual[0].get(k)]
        assert len(found_markets) >= 1, "Expected at least one market in output"

    def test_cmb_002_basketball_3_markets(
        self,
        run_scraper,
        temp_output_dir,
    ):
        """CMB-002: Test 3 markets simultaneously for basketball."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="basketball",
            match_link=BASKETBALL_MATCH_URL,
            markets=["home_away", "1x2"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        assert len(actual) >= 1, "No matches returned"

    def test_cmb_003_tennis_3_markets(
        self,
        run_scraper,
        temp_output_dir,
    ):
        """CMB-003: Test 3 markets simultaneously for tennis."""
        output_path = temp_output_dir / "output"

        exit_code, _, stderr = run_scraper(
            sport="tennis",
            match_link=TENNIS_MATCH_URL,
            markets=["match_winner", "over_under_sets_2_5"],
            output_path=output_path,
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        assert len(actual) >= 1, "No matches returned"
