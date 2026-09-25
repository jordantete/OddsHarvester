"""A failed write must be visible and must not lose the scraped batch."""

import json
import re
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
import pytest

from oddsharvester.cli.cli import cli
from oddsharvester.cli.commands._output import _fallback_path
from oddsharvester.core.scrape_result import ScrapeResult, ScrapeStats

FUTURE_DATE = "20991231"
RECORDS = [{"match_link": "https://x/a", "home_team": "A"}]


def _result():
    return ScrapeResult(success=list(RECORDS), stats=ScrapeStats(total_urls=1, successful=1))


CASES = {
    "upcoming": (["upcoming", "-s", "football", "-d", FUTURE_DATE], "upcoming.run_scraper", _result),
    "historic": (
        ["historic", "-s", "football", "-l", "england-premier-league", "--season", "2022-2023"],
        "historic.run_scraper",
        _result,
    ),
    "live": (["live", "-s", "football"], "live.run_scraper", _result),
    "team": (["team", "--team", "lId4TMwf"], "team.run_teams", _result),
    "community": (["community", "--sport", "football"], "community.run_top_predictions", lambda: list(RECORDS)),
}


def _invoke(command, extra, store_ok=False):
    args, target, value = CASES[command]
    with (
        patch(f"oddsharvester.cli.commands.{target}", new_callable=AsyncMock, return_value=value()),
        patch("oddsharvester.cli.commands._output.store_data", return_value=store_ok),
    ):
        return CliRunner().invoke(cli, [*args, *extra])


@pytest.mark.parametrize("command", list(CASES))
def test_failed_write_saves_a_fallback_and_exits_1(command, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = _invoke(command, ["-o", "out.json"])

    assert result.exit_code == 1, result.output
    [fallback] = tmp_path.glob("out.unsaved-*.json")
    assert json.loads(fallback.read_text(encoding="utf-8")) == RECORDS
    assert "Could not write the output to out.json" in result.stderr
    assert fallback.name in result.stderr


@pytest.mark.parametrize("command", list(CASES))
def test_successful_write_exits_0_without_fallback(command, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = _invoke(command, ["-o", "out.json"], store_ok=True)

    assert result.exit_code == 0, result.output
    assert not list(tmp_path.glob("*.unsaved-*"))


def test_failed_fallback_is_reported(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with patch("oddsharvester.cli.commands._output.LocalDataStorage.save_data", side_effect=OSError("disk full")):
        result = _invoke("historic", ["-o", "out.json"])

    assert result.exit_code == 1
    assert "failed too: disk full" in result.stderr


def test_failed_write_keeps_the_ndjson_stream_clean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = _invoke("upcoming", ["--stream-ndjson", "-o", "out.json"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Could not write the output" in result.stderr


@pytest.mark.parametrize("extra", [["-f", "csv", "-o", "out.csv"], ["--storage", "remote", "-o", "out.json"]])
def test_fallback_is_json_next_to_the_requested_output(extra, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = _invoke("historic", extra)

    assert result.exit_code == 1
    [fallback] = tmp_path.glob("out.unsaved-*.json")
    assert json.loads(fallback.read_text(encoding="utf-8")) == RECORDS


def test_append_to_an_unreadable_json_keeps_it_and_saves_the_batch_aside(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out.json").write_text("not json", encoding="utf-8")

    args, target, value = CASES["historic"]
    with patch(f"oddsharvester.cli.commands.{target}", new_callable=AsyncMock, return_value=value()):
        result = CliRunner().invoke(cli, [*args, "-o", "out.json", "--append"])

    assert result.exit_code == 1
    assert (tmp_path / "out.json").read_text(encoding="utf-8") == "not json"
    [fallback] = tmp_path.glob("out.unsaved-*.json")
    assert json.loads(fallback.read_text(encoding="utf-8")) == RECORDS


@pytest.mark.parametrize(
    ("file_path", "prefix"),
    [(None, "scraped_data"), ("out.csv", "out"), ("data/out.json", "data/out"), ("out", "out")],
)
def test_fallback_path_sits_next_to_the_output(file_path, prefix):
    assert re.fullmatch(rf"{re.escape(prefix)}\.unsaved-\d{{8}}T\d{{6}}Z\.json", _fallback_path(file_path))
