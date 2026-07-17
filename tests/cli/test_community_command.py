"""Tests for the community CLI command."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from oddsharvester.cli.cli import cli

FAKE_RECORDS = [{"sport": "football", "market": "1X2", "match_url": "https://www.oddsportal.com/x"}]


def test_community_requires_exactly_one_mode():
    result = CliRunner().invoke(cli, ["community"])
    assert result.exit_code == 2
    assert "exactly one" in result.output.lower()


def test_community_rejects_two_modes():
    result = CliRunner().invoke(
        cli, ["community", "--user", "BLAPRO", "--match-url", "https://www.oddsportal.com/football/h2h/a/b/"]
    )
    assert result.exit_code == 2
    assert "exactly one" in result.output.lower()


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


@patch("oddsharvester.cli.commands.community.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_user_profile", new_callable=AsyncMock)
def test_community_user_mode_dispatches_and_exits_zero_when_private(mock_run, mock_store):
    private_rec = {"mode": "user", "username": "z", "privacy": "private", "statistics": [], "predictions": []}
    mock_run.return_value = private_rec

    result = CliRunner().invoke(cli, ["community", "--user", "z", "--headless"])

    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["username"] == "z"
    assert mock_store.call_args.kwargs["data"] == [private_rec]


@patch("oddsharvester.cli.commands.community.run_user_profile", new_callable=AsyncMock)
def test_community_user_mode_exits_one_when_no_username_at_all(mock_run):
    empty_rec = {"mode": "user", "username": None, "privacy": None, "statistics": [], "predictions": []}
    mock_run.return_value = empty_rec

    result = CliRunner().invoke(cli, ["community", "--user", "z", "--headless"])

    assert result.exit_code == 1


@patch("oddsharvester.cli.commands.community.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_match_community", new_callable=AsyncMock)
def test_community_match_url_mode_dispatches_and_exits_zero(mock_run, mock_store):
    rec = {"mode": "match", "match_url": "u", "markets": [{"market": "1x2"}]}
    mock_run.return_value = rec

    result = CliRunner().invoke(
        cli, ["community", "--match-url", "https://www.oddsportal.com/football/h2h/a/b/", "--headless"]
    )

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["match_url"] == "https://www.oddsportal.com/football/h2h/a/b/"
    assert mock_store.call_args.kwargs["data"] == [rec]


@patch("oddsharvester.cli.commands.community.run_match_community", new_callable=AsyncMock)
def test_community_match_url_mode_exits_one_when_no_markets(mock_run):
    empty_rec = {"mode": "match", "match_url": "u", "markets": []}
    mock_run.return_value = empty_rec

    result = CliRunner().invoke(
        cli, ["community", "--match-url", "https://www.oddsportal.com/football/h2h/a/b/", "--headless"]
    )

    assert result.exit_code == 1
