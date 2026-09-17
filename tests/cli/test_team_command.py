"""Tests for the team CLI command."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from oddsharvester.cli.cli import cli
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats

_RECORD = {"team_id": "lId4TMwf", "name": "Liverpool", "list_name": "Liverpool"}


def _result(success=None, failed=None):
    success = success if success is not None else [_RECORD]
    failed = failed or []
    return ScrapeResult(
        success=success,
        failed=failed,
        stats=ScrapeStats(total_urls=len(success) + len(failed), successful=len(success), failed=len(failed)),
    )


def _patches():
    return (
        patch("oddsharvester.cli.commands.team.store_data", return_value=True),
        patch("oddsharvester.cli.commands.team.run_teams", new_callable=AsyncMock, return_value=_result()),
    )


def test_team_requires_at_least_one_team():
    result = CliRunner().invoke(cli, ["team"])

    assert result.exit_code == 2
    assert "--team" in result.output


def test_team_accepts_a_bare_id():
    store, run = _patches()
    with store, run as mock_run:
        result = CliRunner().invoke(cli, ["team", "--team", "lId4TMwf", "--headless"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["team_ids"] == ["lId4TMwf"]


def test_team_extracts_the_id_from_a_pasted_url():
    store, run = _patches()
    with store, run as mock_run:
        result = CliRunner().invoke(
            cli, ["team", "--team", "https://www.oddsportal.com/football/team/liverpool/lId4TMwf/"]
        )

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["team_ids"] == ["lId4TMwf"]


def test_team_accepts_repeated_and_comma_separated_values():
    store, run = _patches()
    with store, run as mock_run:
        result = CliRunner().invoke(cli, ["team", "--team", "lId4TMwf,WGt8En5I", "--team", "hA1Zm19f"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["team_ids"] == ["lId4TMwf", "WGt8En5I", "hA1Zm19f"]


def test_team_deduplicates_ids():
    store, run = _patches()
    with store, run as mock_run:
        result = CliRunner().invoke(cli, ["team", "--team", "lId4TMwf", "--team", "lId4TMwf"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["team_ids"] == ["lId4TMwf"]


def test_team_reads_ids_from_a_file(tmp_path):
    teams_file = tmp_path / "teams.txt"
    teams_file.write_text(
        "lId4TMwf\n\nhttps://www.oddsportal.com/football/team/barcelona-fc/WGt8En5I/\n", encoding="utf-8"
    )

    store, run = _patches()
    with store, run as mock_run:
        result = CliRunner().invoke(cli, ["team", "--teams-file", str(teams_file)])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["team_ids"] == ["lId4TMwf", "WGt8En5I"]


def test_team_rejects_a_value_that_is_neither_id_nor_team_url():
    result = CliRunner().invoke(cli, ["team", "--team", "https://www.oddsportal.com/football/england/premier-league/"])

    assert result.exit_code == 2
    assert "team id" in result.output.lower()


def test_team_stores_the_records_and_reports_the_count():
    store, run = _patches()
    with store as mock_store, run:
        result = CliRunner().invoke(cli, ["team", "--team", "lId4TMwf", "-o", "teams.json"])

    assert result.exit_code == 0, result.output
    assert "Successfully scraped 1 team" in result.output
    assert mock_store.call_args.kwargs["data"] == [_RECORD]
    assert mock_store.call_args.kwargs["file_path"] == "teams.json"


def test_team_reports_failures_without_failing_the_run():
    failure = FailedUrl(url="zzzzzzzz", error_type=ErrorType.PARSING, error_message="no payload", is_retryable=False)
    with (
        patch("oddsharvester.cli.commands.team.store_data", return_value=True),
        patch(
            "oddsharvester.cli.commands.team.run_teams",
            new_callable=AsyncMock,
            return_value=_result(failed=[failure]),
        ),
    ):
        result = CliRunner().invoke(cli, ["team", "--team", "lId4TMwf", "--team", "zzzzzzzz"])

    assert result.exit_code == 0, result.output
    assert "zzzzzzzz" in result.output


def test_team_exits_nonzero_when_no_team_resolved():
    failure = FailedUrl(url="zzzzzzzz", error_type=ErrorType.PARSING, error_message="no payload", is_retryable=False)
    with (
        patch("oddsharvester.cli.commands.team.store_data", return_value=True),
        patch(
            "oddsharvester.cli.commands.team.run_teams",
            new_callable=AsyncMock,
            return_value=_result(success=[], failed=[failure]),
        ),
    ):
        result = CliRunner().invoke(cli, ["team", "--team", "zzzzzzzz"])

    assert result.exit_code == 1


def test_team_forwards_browser_options():
    store, run = _patches()
    with store, run as mock_run:
        result = CliRunner().invoke(
            cli,
            ["team", "--team", "lId4TMwf", "--headless", "--base-url", "https://www.centroquote.it"],
        )

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["headless"] is True
    assert mock_run.call_args.kwargs["base_url"] == "https://www.centroquote.it"


def test_team_rejects_a_word_that_is_not_an_eight_character_id():
    """Every OddsPortal team id is 8 characters, so a slug typed by hand is caught here."""
    result = CliRunner().invoke(cli, ["team", "--team", "liverpool"])

    assert result.exit_code == 2
    assert "8 characters" in result.output
