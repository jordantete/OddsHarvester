"""Tests for the Click-based CLI."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
import pytest

from oddsharvester import __version__
from oddsharvester.cli.cli import cli
from oddsharvester.cli.commands.historic import _format_combo_summary

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
        assert __version__ in result.output

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

    def test_historic_empty_season_rejected(self, runner, mock_run_scraper):
        """--season "" must fail validation, not silently fall back to the current season (issue #78 regression)."""
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", ""])
        assert result.exit_code != 0
        assert not mock_run_scraper["historic"].called

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

    def test_upcoming_concurrency_flag_forwarded_to_run_scraper(self, runner, mock_run_scraper):
        """`--concurrency N` on `upcoming` must reach run_scraper as concurrency_tasks=N (issue #64)."""
        runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "-c", "10"])
        assert mock_run_scraper["upcoming"].called
        assert mock_run_scraper["upcoming"].call_args.kwargs.get("concurrency_tasks") == 10

    def test_upcoming_kickoff_within_hours_forwarded_to_run_scraper(self, runner, mock_run_scraper):
        """`--kickoff-within-hours N` on `upcoming` must reach run_scraper (issue #77)."""
        runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "--kickoff-within-hours", "6"])
        assert mock_run_scraper["upcoming"].called
        assert mock_run_scraper["upcoming"].call_args.kwargs.get("kickoff_within_hours") == 6.0

    def test_upcoming_kickoff_within_hours_rejects_non_positive(self, runner, mock_run_scraper):
        """A zero or negative window is meaningless and must be rejected (issue #77)."""
        result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "--kickoff-within-hours", "0"])
        assert result.exit_code != 0
        assert not mock_run_scraper["upcoming"].called

    def test_historic_concurrency_flag_forwarded_to_run_scraper(self, runner, mock_run_scraper):
        """`--concurrency N` on `historic` must reach run_scraper as concurrency_tasks=N (issue #64)."""
        runner.invoke(
            cli, ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2024", "-c", "7"]
        )
        assert mock_run_scraper["historic"].called
        assert mock_run_scraper["historic"].call_args.kwargs.get("concurrency_tasks") == 7

    def test_historic_single_season_forwarded_as_list(self, runner, mock_run_scraper):
        """Backward compatibility: a single --season value still works, now as a one-element list."""
        runner.invoke(cli, ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2024"])
        assert mock_run_scraper["historic"].call_args.kwargs["seasons"] == ["2024"]

    def test_historic_season_list_forwarded(self, runner, mock_run_scraper):
        """--season accepts a comma-separated list (issue #78)."""
        runner.invoke(
            cli,
            ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2021-2022,2022-2023"],
        )
        assert mock_run_scraper["historic"].call_args.kwargs["seasons"] == ["2021-2022", "2022-2023"]

    def test_historic_season_list_deduplicated(self, runner, mock_run_scraper):
        """--season with repeated values is deduplicated, order preserved (issue #78)."""
        runner.invoke(cli, ["historic", "-s", "football", "--season", "2024,2024,2023"])
        assert mock_run_scraper["historic"].call_args.kwargs["seasons"] == ["2024", "2023"]

    def test_historic_season_list_rejects_invalid_element(self, runner, mock_run_scraper):
        result = runner.invoke(cli, ["historic", "-s", "football", "--season", "2024,invalid"])
        assert result.exit_code != 0
        assert "Invalid season format" in result.output

    def test_local_kickoff_flag_forwarded_historic(self, runner, mock_run_scraper):
        runner.invoke(cli, ["historic", "-s", "football", "--season", "2024", "--local-kickoff"])
        assert mock_run_scraper["historic"].call_args.kwargs["local_kickoff"] is True

    def test_local_kickoff_defaults_false(self, runner, mock_run_scraper):
        runner.invoke(cli, ["historic", "-s", "football", "--season", "2024"])
        assert mock_run_scraper["historic"].call_args.kwargs["local_kickoff"] is False

    def test_local_kickoff_conflicts_with_links_only(self, runner, mock_run_scraper):
        result = runner.invoke(
            cli,
            ["historic", "-s", "football", "--season", "2024", "--links-only", "--local-kickoff"],
        )
        assert result.exit_code != 0
        assert "local-kickoff" in result.output
        assert "links-only" in result.output

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


class TestLinksOnly:
    """Tests for the --links-only flag (issue #75)."""

    MATCH_URL = "https://www.oddsportal.com/football/england/premier-league/arsenal-chelsea-abc123/"

    def test_help_shows_links_only(self, runner):
        for command in ["historic", "upcoming"]:
            result = runner.invoke(cli, [command, "--help"])
            assert result.exit_code == 0
            assert "--links-only" in result.output

    def test_links_only_conflicts_with_match_link_historic(self, runner):
        result = runner.invoke(
            cli,
            ["historic", "-s", "football", "--season", "2024-2025", "--links-only", "--match-link", self.MATCH_URL],
        )
        assert result.exit_code != 0
        assert "--links-only cannot be combined with --match-link" in result.output

    def test_links_only_conflicts_with_match_link_upcoming(self, runner):
        result = runner.invoke(
            cli,
            ["upcoming", "-s", "football", "--links-only", "--match-link", self.MATCH_URL],
        )
        assert result.exit_code != 0
        assert "--links-only cannot be combined with --match-link" in result.output

    def _links_result(self):
        from oddsharvester.core.scrape_result import ScrapeResult, ScrapeStats

        return ScrapeResult(
            success=[
                {
                    "match_link": self.MATCH_URL,
                    "sport": "football",
                    "league": "england-premier-league",
                    "season": "2022-2023",
                }
            ],
            stats=ScrapeStats(total_urls=1, successful=1, failed=0),
        )

    def test_links_only_forwarded_and_message_historic(self, runner):
        with (
            patch(
                "oddsharvester.cli.commands.historic.run_scraper",
                new_callable=AsyncMock,
                return_value=self._links_result(),
            ) as scraper_mock,
            patch("oddsharvester.cli.commands.historic.store_data") as store_mock,
        ):
            result = runner.invoke(
                cli,
                ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2022-2023", "--links-only"],
            )
        assert result.exit_code == 0
        assert scraper_mock.call_args.kwargs["links_only"] is True
        assert "Collected 1 match links (0 listing pages failed)." in result.output
        store_mock.assert_called_once()

    def test_links_only_forwarded_and_message_upcoming(self, runner):
        with (
            patch(
                "oddsharvester.cli.commands.upcoming.run_scraper",
                new_callable=AsyncMock,
                return_value=self._links_result(),
            ) as scraper_mock,
            patch("oddsharvester.cli.commands.upcoming.store_data") as store_mock,
        ):
            result = runner.invoke(cli, ["upcoming", "-s", "football", "-d", FUTURE_DATE, "--links-only"])
        assert result.exit_code == 0
        assert scraper_mock.call_args.kwargs["links_only"] is True
        assert "Collected 1 match links (0 listing pages failed)." in result.output
        store_mock.assert_called_once()


class TestComboSummaryRendering:
    """Tests for the per-combo summary table gate in `historic` (findings 2 and 4)."""

    def _combo_result(self, combo_stats, success=None):
        from oddsharvester.core.scrape_result import ScrapeResult, ScrapeStats

        success = success if success is not None else []
        return ScrapeResult(
            success=success,
            stats=ScrapeStats(total_urls=len(success), successful=len(success), failed=0),
            combo_stats=combo_stats,
        )

    def test_all_combos_empty_still_prints_summary_and_exits_1(self, runner):
        """A run where every combo returns zero rows must still show the breakdown, and still exit 1 (finding 2)."""
        combo_stats = [
            {"league": "england-premier-league", "season": "2020", "successful": 0, "failed": 0, "errored": False},
            {"league": "england-premier-league", "season": "2021", "successful": 0, "failed": 0, "errored": False},
        ]
        with patch(
            "oddsharvester.cli.commands.historic.run_scraper",
            new_callable=AsyncMock,
            return_value=self._combo_result(combo_stats),
        ) as scraper_mock:
            result = runner.invoke(
                cli,
                ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2020,2021"],
            )
        assert scraper_mock.called
        assert result.exit_code == 1
        assert "Collected matches across 2 combos" in result.output
        assert "2 combo(s) returned nothing." in result.output

    @pytest.mark.parametrize("combo_count", [0, 1, 2])
    def test_summary_table_only_shown_for_more_than_one_combo(self, runner, combo_count):
        """The table must appear only when there is more than one combo (finding 4)."""
        combo_stats = [
            {
                "league": "england-premier-league",
                "season": str(2020 + i),
                "successful": 1,
                "failed": 0,
                "errored": False,
            }
            for i in range(combo_count)
        ]
        success = [{"match": "data"}] * max(combo_count, 1)
        with (
            patch(
                "oddsharvester.cli.commands.historic.run_scraper",
                new_callable=AsyncMock,
                return_value=self._combo_result(combo_stats, success=success),
            ),
            patch("oddsharvester.cli.commands.historic.store_data"),
        ):
            result = runner.invoke(
                cli,
                ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2020"],
            )
        if combo_count > 1:
            assert "combos:" in result.output
        else:
            assert "combos:" not in result.output


def test_all_registered_sport_periods_are_cli_selectable():
    """Every period of every registered sport must be a valid --period CLI choice.

    Regression guard: handball and volleyball periods (e.g. 3rd_set..5th_set)
    were missing from the CLI choice list because _get_all_periods() used a
    hardcoded enum list that omitted those sports. This test fails if a new
    sport's periods are added to the registry but not exposed via the CLI.
    """
    from oddsharvester.cli.options import _get_all_periods
    from oddsharvester.core.sport_period_registry import SportPeriodRegistry

    cli_periods = set(_get_all_periods())
    for sport, config in SportPeriodRegistry._registry.items():
        for period in config["enum"]:
            assert period.value in cli_periods, f"{sport} period {period.value!r} not selectable via --period CLI"


def test_combo_summary_lists_every_combo_with_counts():
    out = _format_combo_summary(
        [
            {"league": "russia-premier-league", "season": "2010", "successful": 380, "failed": 0, "errored": False},
            {"league": "russia-premier-league", "season": "2011", "successful": 0, "failed": 0, "errored": False},
        ],
        links_only=True,
    )
    assert "russia-premier-league 2010" in out
    assert "380" in out
    assert "1 combo(s) returned nothing." in out


def test_combo_summary_marks_errored_combos_separately():
    out = _format_combo_summary(
        [
            {"league": "epl", "season": "2020", "successful": 0, "failed": 0, "errored": False},
            {"league": "epl", "season": "2021", "successful": 0, "failed": 0, "errored": True},
        ],
        links_only=False,
    )
    assert "error" in out
    assert "1 combo(s) errored." in out
    assert "1 combo(s) returned nothing." in out
