"""Tests for the integration CLI runner and capture helpers."""

import json
from pathlib import Path
import re
import subprocess

import pytest
from scripts import capture_all_hars

from oddsharvester.cli.options import _get_all_periods
from tests.integration.helpers import cli_runner
from tests.integration.helpers.capture import build_fixture_filename

pytestmark = pytest.mark.integration

DRY_RUN_HAR = re.compile(rf"^(?:{'|'.join(capture_all_hars.KINDS)}) +(\S+\.har)$", re.MULTILINE)


def test_fixture_filename_without_odds_history():
    assert (
        build_fixture_filename(["over_under_2_5", "1x2"], "full_time", "all") == "1x2_over_under_2_5_full_time_all.json"
    )


def test_fixture_filename_with_odds_history():
    name = build_fixture_filename(["1x2", "over_under_2_5"], "full_time", "all", odds_history=True)
    assert name == "1x2_over_under_2_5_full_time_all_odds_history.json"


def test_fixture_filename_with_preview_only():
    name = build_fixture_filename(["over_under_2_5", "1x2"], "full_time", "all", preview_only=True)
    assert name == "1x2_over_under_2_5_full_time_all_preview.json"


def test_run_historic_forwards_extra_args_and_replay_env(monkeypatch, tmp_path):
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["env"] = kwargs["env"]
        return subprocess.CompletedProcess(cmd, 0, "out", "err")

    monkeypatch.setattr(cli_runner.subprocess, "run", fake_run)
    result = cli_runner.run_historic(
        sport="football",
        match_link="https://www.oddsportal.com/football/h2h/a-AAAAAAAA/b-BBBBBBBB/#CCCCCCCC",
        markets=["1x2", "over_under_2_5"],
        output_path=tmp_path / "output",
        season="2025-2026",
        har_path=tmp_path / "match.har",
        extra_args=["--odds-history", "--timezone", "Europe/London"],
    )
    assert result == (0, "out", "err")
    assert calls["cmd"][-3:] == ["--odds-history", "--timezone", "Europe/London"]
    assert calls["cmd"].count("--timezone") == 1
    assert "1x2,over_under_2_5" in calls["cmd"]
    assert calls["env"]["ODDSHARVESTER_HAR_REPLAY"] == str(tmp_path / "match.har")


def test_run_historic_pins_the_browser_to_utc_without_a_timezone(monkeypatch, tmp_path):
    """The page renders times at the browser's current UTC offset, so a DST host zone shifts match_date."""
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(cli_runner.subprocess, "run", fake_run)
    cli_runner.run_historic(
        sport="tennis",
        match_link="https://www.oddsportal.com/tennis/h2h/a-AAAAAAAA/b-BBBBBBBB/#CCCCCCCC",
        markets=["match_winner"],
        output_path=tmp_path / "output",
    )
    index = calls["cmd"].index("--timezone")
    assert calls["cmd"][index + 1] == "UTC"


def _committed_hars(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(capture_all_hars.PROJECT_ROOT)) for p in folder.rglob("*.har"))


def test_dry_run_lists_every_committed_har(capsys):
    assert capture_all_hars.main(["--dry-run"]) == 0
    listed = DRY_RUN_HAR.findall(capsys.readouterr().out)
    assert sorted(listed) == _committed_hars(capture_all_hars.FIXTURES_DIR)


def test_dry_run_only_community_lists_the_community_hars(capsys):
    assert capture_all_hars.main(["--dry-run", "--only", "community"]) == 0
    listed = DRY_RUN_HAR.findall(capsys.readouterr().out)
    assert sorted(listed) == _committed_hars(capture_all_hars.FIXTURES_DIR / "community")


def test_capture_periods_are_the_cli_periods():
    assert sorted(capture_all_hars._KNOWN_PERIODS) == _get_all_periods()


def _community_special(tmp_path, monkeypatch):
    monkeypatch.setattr(capture_all_hars, "FIXTURES_DIR", tmp_path)
    (tmp_path / "community").mkdir()
    (tmp_path / "community" / "x.har").write_text("old har")
    (tmp_path / "community" / "x.json").write_text("old golden")
    return capture_all_hars.SpecialFixture(
        kind="community", har="community/x.har", argv=("community", "-s", "football")
    )


def _fake_cli(monkeypatch, returncode, golden):
    def fake_run(cmd, **kwargs):
        Path(kwargs["env"]["ODDSHARVESTER_HAR_RECORD"]).write_text("new har")
        if golden is not None:
            Path(cmd[cmd.index("-o") + 1]).write_text(golden)
        return subprocess.CompletedProcess(cmd, returncode)

    monkeypatch.setattr(capture_all_hars.subprocess, "run", fake_run)


@pytest.mark.parametrize(
    ("returncode", "golden"),
    [(1, None), (0, None), (0, "[]"), (0, '[{"username": "BL')],
    ids=["command-failed", "no-output", "no-records", "truncated-json"],
)
def test_a_failed_special_capture_leaves_the_committed_files(tmp_path, monkeypatch, returncode, golden):
    special = _community_special(tmp_path, monkeypatch)
    _fake_cli(monkeypatch, returncode, golden)

    assert capture_all_hars.capture_special(special) is False
    assert (tmp_path / "community" / "x.har").read_text() == "old har"
    assert (tmp_path / "community" / "x.json").read_text() == "old golden"


def test_a_successful_special_capture_replaces_both_files(tmp_path, monkeypatch):
    special = _community_special(tmp_path, monkeypatch)
    _fake_cli(monkeypatch, 0, '[{"username": "BLAPRO"}]')

    assert capture_all_hars.capture_special(special) is True
    assert (tmp_path / "community" / "x.har").read_text() == "new har"
    assert json.loads((tmp_path / "community" / "x.json").read_text()) == [{"username": "BLAPRO"}]
