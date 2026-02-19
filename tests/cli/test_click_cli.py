"""Tests for the Click-based CLI."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
import pytest

from oddsharvester.cli.cli import cli

# Use a far future date to avoid date validation issues
FUTURE_DATE = "20991231"


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_run_scraper():
    """Mock the run_scraper function to avoid launching the browser."""
    with (
        patch(
            "oddsharvester.cli.commands.historic.run_scraper",
            new_callable=AsyncMock,
            return_value=[{"match": "data"}],
        ) as historic_mock,
        patch(
            "oddsharvester.cli.commands.upcoming.run_scraper",
            new_callable=AsyncMock,
            return_value=[{"match": "data"}],
        ) as upcoming_mock,
    ):
        yield {"historic": historic_mock, "upcoming": upcoming_mock}


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_cli_help(self, runner):
        """Test that --help works."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "OddsHarvester" in result.output
        assert "upcoming" in result.output
        assert "historic" in result.output

    def test_cli_version(self, runner):
        """Test that --version works."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_upcoming_help(self, runner):
        """Test upcoming command help."""
        result = runner.invoke(cli, ["upcoming", "--help"])
        assert result.exit_code == 0
        assert "--sport" in result.output
        assert "--date" in result.output
        assert "--league" in result.output
        assert "--request-delay" in result.output

    def test_historic_help(self, runner):
        """Test historic command help."""
        result = runner.invoke(cli, ["historic", "--help"])
        assert result.exit_code == 0
        assert "--sport" in result.output
        assert "--season" in result.output
        assert "--max-pages" in result.output


class TestUpcomingCommand:
    """Test the upcoming command."""

    def test_upcoming_requires_sport(self, runner):
        """Test that sport is required."""
        result = runner.invoke(cli, ["upcoming", "--date", FUTURE_DATE])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_upcoming_requires_date_or_league(self, runner):
        """Test that date or league is required."""
        result = runner.invoke(cli, ["upcoming", "-s", "football"])
        assert result.exit_code != 0
        assert "must provide" in result.output.lower() or "error" in result.output.lower()

    def test_upcoming_invalid_date_format(self, runner):
        """Test invalid date format."""
        result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", "2026-02-01"])
        assert result.exit_code != 0
        assert "Invalid date format" in result.output

    def test_upcoming_past_date(self, runner):
        """Test past date validation."""
        result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", "20200101"])
        assert result.exit_code != 0
        assert "must be today or in the future" in result.output


class TestHistoricCommand:
    """Test the historic command."""

    def test_historic_requires_sport(self, runner):
        """Test that sport is required."""
        result = runner.invoke(cli, ["historic", "--season", "2024-2025"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_historic_requires_season(self, runner):
        """Test that season is required."""
        result = runner.invoke(cli, ["historic", "-s", "football"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_historic_invalid_season_format(self, runner):
        """Test invalid season format."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "invalid"])
        assert result.exit_code != 0
        assert "Invalid season format" in result.output

    def test_historic_invalid_season_range(self, runner):
        """Test invalid season range (years not consecutive)."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2020-2025"])
        assert result.exit_code != 0
        assert "Second year must be exactly one year after" in result.output

    def test_historic_valid_season_formats(self, runner, mock_run_scraper):
        """Test valid season formats are accepted (parsing only)."""
        # Single year format
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024"])
        assert "Invalid season format" not in result.output
        assert mock_run_scraper["historic"].called

        mock_run_scraper["historic"].reset_mock()

        # Range format
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024-2025"])
        assert "Invalid season format" not in result.output
        assert mock_run_scraper["historic"].called

        mock_run_scraper["historic"].reset_mock()

        # Current format
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "current"])
        assert "Invalid season format" not in result.output
        assert mock_run_scraper["historic"].called


class TestCommonOptions:
    """Test common options across commands."""

    def test_invalid_sport(self, runner):
        """Test invalid sport value."""
        result = runner.invoke(cli, ["upcoming", "-s", "invalid_sport", "-d", FUTURE_DATE])
        assert result.exit_code != 0
        assert "Invalid sport" in result.output

    def test_invalid_storage_type(self, runner, mock_run_scraper):
        """Test invalid storage type."""
        result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "--storage", "invalid"])
        assert result.exit_code != 0
        assert "Invalid storage type" in result.output

    def test_invalid_storage_format(self, runner, mock_run_scraper):
        """Test invalid storage format."""
        result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "-f", "xml"])
        assert result.exit_code != 0
        assert "Invalid storage format" in result.output

    def test_invalid_concurrency(self, runner, mock_run_scraper):
        """Test invalid concurrency value."""
        result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "-c", "0"])
        assert result.exit_code != 0
        assert "positive integer" in result.output.lower()

    def test_invalid_proxy_url_format(self, runner, mock_run_scraper):
        """Test invalid proxy URL format."""
        result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "--proxy-url", "invalid"])
        assert result.exit_code != 0
        assert "Invalid proxy URL" in result.output

    def test_valid_proxy_url(self, runner, mock_run_scraper):
        """Test valid proxy URL format is accepted."""
        result = runner.invoke(
            cli,
            ["upcoming", "-s", "football", "-d", FUTURE_DATE, "--proxy-url", "http://proxy:8080"],
        )
        # Validation should pass, scraper should be called
        assert "Invalid proxy URL" not in result.output
        assert mock_run_scraper["upcoming"].called

    def test_invalid_match_link(self, runner):
        """Test invalid match link format."""
        result = runner.invoke(cli, ["upcoming", "-s", "football", "--match-link", "https://example.com/match"])
        assert result.exit_code != 0
        assert "Invalid match link" in result.output


class TestShortOptions:
    """Test short option aliases."""

    def test_short_sport_option(self, runner):
        """Test -s for sport."""
        result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "--help"])
        assert result.exit_code == 0

    def test_short_league_option(self, runner, mock_run_scraper):
        """Test -l for league."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "-l", "england-premier-league"])
        # Validation should pass
        assert "Invalid value" not in result.output or "league" in result.output.lower()
        assert mock_run_scraper["historic"].called

    def test_short_market_option(self, runner, mock_run_scraper):
        """Test -m for market."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "-m", "1x2"])
        assert "Invalid value" not in result.output or "market" in result.output.lower()
        assert mock_run_scraper["historic"].called

    def test_short_format_option(self, runner, mock_run_scraper):
        """Test -f for format."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "-f", "csv"])
        assert "Invalid storage format" not in result.output
        assert mock_run_scraper["historic"].called

    def test_short_concurrency_option(self, runner, mock_run_scraper):
        """Test -c for concurrency."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "-c", "5"])
        assert "positive integer" not in result.output
        assert mock_run_scraper["historic"].called


class TestOutputPathValidation:
    """Test --output path validation."""

    def test_rejects_path_traversal(self, runner):
        """Test that paths with '..' segments are rejected."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "-o", "../../etc/passwd"])
        assert result.exit_code != 0
        assert "must not contain '..'" in result.output

    def test_rejects_absolute_path_with_traversal(self, runner):
        """Test that absolute paths with '..' segments are rejected."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "-o", "/tmp/../etc/passwd"])
        assert result.exit_code != 0
        assert "must not contain '..'" in result.output

    def test_accepts_valid_relative_path(self, runner, mock_run_scraper):
        """Test that a valid relative path is accepted."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "-o", "output/data.json"])
        assert "must not contain" not in result.output
        assert mock_run_scraper["historic"].called

    def test_accepts_absolute_path(self, runner, mock_run_scraper):
        """Test that a valid absolute path is accepted."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "-o", "/tmp/output.json"])
        assert "must not contain" not in result.output
        assert mock_run_scraper["historic"].called

    def test_rejects_existing_directory(self, runner, tmp_path):
        """Test that paths pointing to existing directories are rejected."""
        existing_dir = tmp_path / "existing_dir"
        existing_dir.mkdir()
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "-o", str(existing_dir)])
        assert result.exit_code != 0
        assert "must not be an existing directory" in result.output
