"""Tests for the integration CLI runner and capture helpers."""

import subprocess

import pytest

from tests.integration.helpers import cli_runner
from tests.integration.helpers.capture import build_fixture_filename

pytestmark = pytest.mark.integration


def test_fixture_filename_without_odds_history():
    assert (
        build_fixture_filename(["over_under_2_5", "1x2"], "full_time", "all") == "1x2_over_under_2_5_full_time_all.json"
    )


def test_fixture_filename_with_odds_history():
    name = build_fixture_filename(["1x2", "over_under_2_5"], "full_time", "all", odds_history=True)
    assert name == "1x2_over_under_2_5_full_time_all_odds_history.json"


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
    assert "1x2,over_under_2_5" in calls["cmd"]
    assert calls["env"]["ODDSHARVESTER_HAR_REPLAY"] == str(tmp_path / "match.har")
