"""Tests for the community CLI command."""

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner
import pytest

from oddsharvester.cli.cli import cli
from oddsharvester.core.exceptions import H2HFragmentResolutionError

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


@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
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


@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
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


@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
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
def test_community_match_url_mode_exits_one_when_no_markets(mock_run, caplog):
    """The message names what the page shows, not a cause: a finished match can keep its votes (gotchas §13)."""
    empty_rec = {"mode": "match", "match_url": "u", "markets": []}
    mock_run.return_value = empty_rec

    result = CliRunner().invoke(
        cli, ["community", "--match-url", "https://www.oddsportal.com/football/h2h/a/b/", "--headless"]
    )

    assert result.exit_code == 1
    assert "No community vote data for this match: its page shows no vote row." in caplog.text


@patch("oddsharvester.cli.commands.community.run_match_community", new_callable=AsyncMock)
def test_community_match_url_mode_reports_a_page_that_never_rendered(mock_run, caplog):
    url = "https://www.oddsportal.com/football/h2h/a/b/#C2Nfvg77"
    mock_run.side_effect = H2HFragmentResolutionError(
        f"match view hydration failed: {url} never rendered match content", url=url
    )

    result = CliRunner().invoke(cli, ["community", "--match-url", url, "--headless"])

    assert result.exit_code == 1
    assert "never rendered match content" in caplog.text
    assert "No community vote data" not in caplog.text


@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_user_profile", new_callable=AsyncMock)
def test_oh_sport_does_not_block_user_mode(mock_run, mock_store):
    mock_run.return_value = {"mode": "user", "username": "z", "privacy": "public", "statistics": [], "predictions": []}

    result = CliRunner().invoke(cli, ["community", "--user", "z"], env={"OH_SPORT": "football"})

    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()


@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_match_community", new_callable=AsyncMock)
def test_oh_sport_does_not_block_match_url_mode(mock_run, mock_store):
    mock_run.return_value = {"markets": [{"market": "1X2"}]}

    result = CliRunner().invoke(
        cli,
        ["community", "--match-url", "https://www.oddsportal.com/football/h2h/a/b/"],
        env={"OH_SPORT": "football"},
    )

    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()


@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_top_predictions", new_callable=AsyncMock, return_value=FAKE_RECORDS)
def test_oh_sport_alone_still_selects_top_predictions(mock_run, mock_store):
    result = CliRunner().invoke(cli, ["community"], env={"OH_SPORT": "football"})

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["sport"] == "football"


@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_top_predictions", new_callable=AsyncMock)
@patch("oddsharvester.cli.commands.community.run_user_profile", new_callable=AsyncMock)
def test_oh_sport_and_oh_user_together_run_user_mode(mock_user, mock_top, mock_store):
    mock_user.return_value = {"mode": "user", "username": "z", "privacy": "public", "statistics": [], "predictions": []}

    result = CliRunner().invoke(cli, ["community"], env={"OH_SPORT": "football", "OH_USER": "z"})

    assert result.exit_code == 0, result.output
    assert mock_user.call_args.kwargs["username"] == "z"
    mock_top.assert_not_called()


MATCH_URL = "https://www.oddsportal.com/football/h2h/a/b/"
USER_RECORD = {"mode": "user", "username": "z", "privacy": "public", "statistics": [], "predictions": []}


@pytest.mark.parametrize("env", [{"OH_USER": "z"}, {"OH_MATCH_URL": MATCH_URL}], ids=["OH_USER", "OH_MATCH_URL"])
@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_top_predictions", new_callable=AsyncMock, return_value=FAKE_RECORDS)
def test_typed_sport_wins_over_an_exported_user_or_match_url(mock_run, mock_store, env):
    result = CliRunner().invoke(cli, ["community", "--sport", "football"], env=env)

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["sport"] == "football"


@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_user_profile", new_callable=AsyncMock, return_value=USER_RECORD)
def test_typed_user_wins_over_an_exported_match_url(mock_run, mock_store):
    result = CliRunner().invoke(cli, ["community", "--user", "z"], env={"OH_MATCH_URL": MATCH_URL})

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["username"] == "z"


@patch("oddsharvester.cli.commands._output.store_data", return_value=True)
@patch("oddsharvester.cli.commands.community.run_match_community", new_callable=AsyncMock)
def test_typed_match_url_wins_over_an_exported_user(mock_run, mock_store):
    mock_run.return_value = {"markets": [{"market": "1X2"}]}

    result = CliRunner().invoke(cli, ["community", "--match-url", MATCH_URL], env={"OH_USER": "z"})

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["match_url"] == MATCH_URL


def test_two_exported_modes_and_no_typed_one_are_still_refused():
    result = CliRunner().invoke(cli, ["community"], env={"OH_USER": "z", "OH_MATCH_URL": MATCH_URL})

    assert result.exit_code == 2
    assert "exactly one" in result.output.lower()


def test_explicit_sport_with_user_is_still_refused():
    result = CliRunner().invoke(cli, ["community", "--sport", "football", "--user", "z"])

    assert result.exit_code == 2
    assert "exactly one" in result.output.lower()


def test_community_user_mode_rate_limited_on_every_attempt_exits_1_and_writes_nothing(tmp_path, caplog):
    page = MagicMock()
    page.url = "about:blank"
    page.goto = AsyncMock(return_value=MagicMock(status=429))
    manager = MagicMock(page=page, timezone_id=None, initialize=AsyncMock(), cleanup=AsyncMock())
    output = tmp_path / "profile"
    with (
        patch("oddsharvester.core.browser.session.PlaywrightManager", return_value=manager),
        patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock),
    ):
        result = CliRunner().invoke(cli, ["community", "--user", "BLAPRO", "--headless", "--output", str(output)])

    assert result.exit_code == 1
    assert list(tmp_path.iterdir()) == []
    assert "rate limited by OddsPortal" in caplog.text
