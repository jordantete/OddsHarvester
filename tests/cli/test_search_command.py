"""Tests for the search CLI command."""

import json
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
import pytest

from oddsharvester.cli.cli import cli

_RUN = "oddsharvester.cli.commands.search.run_search"
_CANDIDATE = {
    "team_id": "hUyau0Vc",
    "name": "Nacional Potosi",
    "country": "Bolivia",
    "sport": "football",
    "team_url": "https://www.oddsportal.com/football/team/nacional-potosi/hUyau0Vc/",
}


def _invoke(args: list[str], out, env: dict | None = None):
    return CliRunner().invoke(cli, ["search", *args, "--headless", "-o", str(out)], env=env)


def test_a_query_reaches_the_runner_with_its_sport(tmp_path):
    out = tmp_path / "out.json"
    with patch(_RUN, new_callable=AsyncMock, return_value=[_CANDIDATE]) as run:
        result = _invoke(["--query", " Nacional Potosi ", "-s", "football"], out)

    assert result.exit_code == 0, result.output
    assert {key: run.await_args.kwargs[key] for key in ("query", "sport", "team_id")} == {
        "query": "Nacional Potosi",
        "sport": "football",
        "team_id": None,
    }
    assert json.loads(out.read_text()) == [_CANDIDATE]
    assert "Found 1 team(s) matching 'Nacional Potosi' in football." in result.stdout


def test_a_team_id_reads_one_results_page_by_default(tmp_path):
    with patch(_RUN, new_callable=AsyncMock, return_value=[]) as run:
        result = _invoke(["--team-id", "hUyau0Vc"], tmp_path / "out.json")

    assert result.exit_code == 0, result.output
    assert (run.await_args.kwargs["team_id"], run.await_args.kwargs["max_pages"]) == ("hUyau0Vc", 1)
    assert run.await_args.kwargs["sport"] is None


def test_a_team_page_url_is_reduced_to_its_id(tmp_path):
    url = "https://www.oddsportal.com/football/team/nacional-potosi/hUyau0Vc/"
    with patch(_RUN, new_callable=AsyncMock, return_value=[]) as run:
        result = _invoke(["--team-id", url, "--max-pages", "3"], tmp_path / "out.json")

    assert result.exit_code == 0, result.output
    assert (run.await_args.kwargs["team_id"], run.await_args.kwargs["max_pages"]) == ("hUyau0Vc", 3)


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ([], "Provide exactly one of --query or --team-id."),
        (["--query", "Nacional", "--team-id", "hUyau0Vc"], "Provide exactly one of --query or --team-id."),
        (["--query", "Nacional"], "--query needs --sport"),
        (["--query", "   ", "-s", "football"], "--query must not be empty."),
        (["--query", "Nacional", "-s", "football", "--max-pages", "2"], "--max-pages applies to --team-id only."),
        (["--team-id", "hUyau0Vc", "-s", "football"], "--sport does not apply to --team-id"),
        (["--team-id", "nope"], "Not a team id"),
        (["--team-id", "hUyau0Vc", "--max-pages", "0"], "Max pages must be a positive integer."),
    ],
)
def test_a_wrong_option_set_exits_2_before_the_browser_starts(tmp_path, args, message):
    with patch(_RUN, new_callable=AsyncMock) as run:
        result = _invoke(args, tmp_path / "out.json")

    assert result.exit_code == 2, result.output
    assert message in result.output
    run.assert_not_awaited()


def test_an_exported_sport_does_not_refuse_a_team_id(tmp_path):
    """OH_SPORT is exported for the other commands; search's --sport reads no variable."""
    with patch(_RUN, new_callable=AsyncMock, return_value=[]):
        result = _invoke(["--team-id", "hUyau0Vc"], tmp_path / "out.json", env={"OH_SPORT": "football"})

    assert result.exit_code == 0, result.output


def test_nothing_found_writes_an_empty_list_and_exits_0(tmp_path):
    out = tmp_path / "out.json"
    with patch(_RUN, new_callable=AsyncMock, return_value=[]):
        result = _invoke(["--query", "Zzzz", "-s", "football"], out)

    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text()) == []


def test_an_unexpected_error_exits_1_with_its_traceback(tmp_path, caplog):
    with patch(_RUN, new_callable=AsyncMock, side_effect=RuntimeError("browser crashed")):
        result = _invoke(["--team-id", "hUyau0Vc"], tmp_path / "out.json")

    assert result.exit_code == 1, result.output
    assert "browser crashed" in caplog.text
    assert "Traceback" in caplog.text


def test_an_output_that_cannot_be_written_exits_1(tmp_path):
    with (
        patch(_RUN, new_callable=AsyncMock, return_value=[_CANDIDATE]),
        patch("oddsharvester.cli.commands._output.store_data", return_value=False),
    ):
        result = _invoke(["--query", "Nacional", "-s", "football"], tmp_path / "out.json")

    assert result.exit_code == 1, result.output
