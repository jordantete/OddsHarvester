"""A failed write must be visible and must not lose the scraped batch."""

import csv
import importlib.util
import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

from botocore.exceptions import NoCredentialsError
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
    monkeypatch.setenv("OH_S3_BUCKET", "test-bucket")

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
    assert re.fullmatch(rf"{re.escape(prefix)}\.unsaved-\d{{8}}T\d{{12}}Z\.json", _fallback_path(file_path))


def _invoke_with_runner_mock(command, extra):
    """Run a command with only its scraper mocked, so the real storage path runs."""
    args, target, value = CASES[command]
    with patch(f"oddsharvester.cli.commands.{target}", new_callable=AsyncMock, return_value=value()) as run_mock:
        result = CliRunner().invoke(cli, [*args, *extra])
    return result, run_mock


@pytest.mark.parametrize("command", list(CASES))
@pytest.mark.parametrize("bucket", [None, "", "   "])
def test_remote_without_a_bucket_exits_2_before_scraping(command, bucket, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    if bucket is None:
        monkeypatch.delenv("OH_S3_BUCKET", raising=False)
    else:
        monkeypatch.setenv("OH_S3_BUCKET", bucket)

    result, run_mock = _invoke_with_runner_mock(command, ["--storage", "remote"])

    assert result.exit_code == 2, result.output
    assert "export OH_S3_BUCKET=<bucket>" in result.output
    run_mock.assert_not_awaited()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(("bucket", "state"), [(None, "is not set"), ("", "is empty"), ("   ", "is empty")])
def test_remote_says_whether_the_bucket_is_unset_or_blank(bucket, state, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    if bucket is None:
        monkeypatch.delenv("OH_S3_BUCKET", raising=False)
    else:
        monkeypatch.setenv("OH_S3_BUCKET", bucket)

    result, run_mock = _invoke_with_runner_mock("upcoming", ["--storage", "remote"])

    assert result.exit_code == 2, result.output
    assert f"OH_S3_BUCKET {state}." in result.output
    run_mock.assert_not_awaited()


def test_remote_reports_a_missing_bucket_and_a_missing_boto3_together(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OH_S3_BUCKET", raising=False)
    real_find_spec = importlib.util.find_spec

    def find_spec_without_boto3(name, *args, **kwargs):
        return None if name == "boto3" else real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", find_spec_without_boto3)

    result, run_mock = _invoke_with_runner_mock("upcoming", ["--storage", "remote"])

    assert result.exit_code == 2, result.output
    assert "OH_S3_BUCKET is not set." in result.output
    assert "pip install 'oddsharvester[s3]'" in result.output
    run_mock.assert_not_awaited()


@pytest.mark.parametrize("command", list(CASES))
def test_oh_storage_remote_without_a_bucket_exits_2_before_scraping(command, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OH_S3_BUCKET", raising=False)
    monkeypatch.setenv("OH_STORAGE", "remote")

    result, run_mock = _invoke_with_runner_mock(command, [])

    assert result.exit_code == 2, result.output
    assert "export OH_S3_BUCKET=<bucket>" in result.output
    run_mock.assert_not_awaited()


@pytest.mark.parametrize("command", list(CASES))
def test_remote_without_boto3_exits_2_with_the_install_command(command, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OH_S3_BUCKET", "test-bucket")
    real_find_spec = importlib.util.find_spec

    def find_spec_without_boto3(name, *args, **kwargs):
        return None if name == "boto3" else real_find_spec(name, *args, **kwargs)

    monkeypatch.setattr(importlib.util, "find_spec", find_spec_without_boto3)

    result, run_mock = _invoke_with_runner_mock(command, ["--storage", "remote"])

    assert result.exit_code == 2, result.output
    assert "pip install 'oddsharvester[s3]'" in result.output
    run_mock.assert_not_awaited()


def test_remote_csv_append_appends_to_the_local_file_and_uploads_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OH_S3_BUCKET", "test-bucket")
    monkeypatch.delenv("OH_AWS_REGION", raising=False)
    (tmp_path / "out.csv").write_text("match_link,home_team\r\nhttps://x/old,Old\r\n", encoding="utf-8")
    client = MagicMock()

    with patch("boto3.client", return_value=client) as client_factory:
        result, _ = _invoke_with_runner_mock(
            "historic", ["--storage", "remote", "-f", "csv", "-o", "out.csv", "--append"]
        )

    assert result.exit_code == 0, result.output
    with open(tmp_path / "out.csv", newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == [
            {"match_link": "https://x/old", "home_team": "Old"},
            {"match_link": "https://x/a", "home_team": "A"},
        ]
    client_factory.assert_called_once_with("s3", region_name="eu-west-3")
    client.upload_file.assert_called_once_with("out.csv", "test-bucket", "out.csv")
    assert not list(tmp_path.glob("*.unsaved-*"))


def test_remote_without_output_writes_and_uploads_the_default_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OH_S3_BUCKET", "test-bucket")
    client = MagicMock()

    with patch("boto3.client", return_value=client):
        result, _ = _invoke_with_runner_mock("upcoming", ["--storage", "remote", "-f", "csv"])

    assert result.exit_code == 0, result.output
    with open(tmp_path / "scraped_data.csv", newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == RECORDS
    client.upload_file.assert_called_once_with("scraped_data.csv", "test-bucket", "scraped_data.csv")


@pytest.mark.parametrize("command", list(CASES))
def test_failed_upload_exits_1_and_names_both_locations(command, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OH_S3_BUCKET", "test-bucket")
    client = MagicMock()
    client.upload_file.side_effect = NoCredentialsError()

    with patch("boto3.client", return_value=client):
        result, _ = _invoke_with_runner_mock(command, ["--storage", "remote", "-o", "out.json"])

    assert result.exit_code == 1, result.output
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8")) == RECORDS
    assert "written to out.json" in result.stderr
    assert "s3://test-bucket/out.json" in result.stderr
    assert "Unable to locate credentials" in result.stderr
    assert not list(tmp_path.glob("*.unsaved-*"))


@pytest.mark.parametrize("command", ["upcoming", "historic", "live"])
def test_remote_stream_without_output_exits_2_before_scraping(command, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OH_S3_BUCKET", "test-bucket")

    result, run_mock = _invoke_with_runner_mock(command, ["--storage", "remote", "--stream-ndjson"])

    assert result.exit_code == 2, result.output
    assert "--stream-ndjson needs --output" in result.output
    run_mock.assert_not_awaited()
