"""Tests for the community CLI command."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from oddsharvester.cli.cli import cli

FAKE_RECORDS = [{"sport": "football", "market": "1X2", "match_url": "https://www.oddsportal.com/x"}]


def test_community_requires_sport():
    result = CliRunner().invoke(cli, ["community"])
    assert result.exit_code != 0
    assert "--sport" in result.output or "Missing option" in result.output


def test_community_rejects_unknown_sport():
    result = CliRunner().invoke(cli, ["community", "--sport", "quidditch"])
    assert result.exit_code != 0
    assert "Invalid sport" in result.output


@patch("oddsharvester.cli.commands.community.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_top_predictions", new_callable=AsyncMock, return_value=FAKE_RECORDS)
def test_community_happy_path(mock_run, mock_store):
    result = CliRunner().invoke(cli, ["community", "--sport", "football", "--headless"])
    assert result.exit_code == 0, result.output
    assert "Successfully scraped 1 community top predictions" in result.output
    assert mock_run.call_args.kwargs["sport"] == "football"
    assert mock_run.call_args.kwargs["headless"] is True
    assert mock_store.call_args.kwargs["data"] == FAKE_RECORDS


@patch("oddsharvester.cli.commands.community.run_top_predictions", new_callable=AsyncMock, return_value=[])
def test_community_exits_nonzero_on_empty_result(mock_run):
    result = CliRunner().invoke(cli, ["community", "--sport", "football"])
    assert result.exit_code == 1
