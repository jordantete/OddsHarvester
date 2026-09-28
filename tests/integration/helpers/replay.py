"""Replay one captured match page through the CLI and compare the output with its golden."""

import json
from pathlib import Path
from typing import Any

from tests.integration.helpers.cli_runner import run_historic
from tests.integration.helpers.comparison import compare_match_data
from tests.integration.helpers.fixture_files import FIXTURES_DIR, require_file


def load_golden(match: dict[str, str], fixture_name: str) -> list[dict[str, Any]]:
    """The committed golden of a match, always as a list; fails the test when it is missing."""
    path = require_file(FIXTURES_DIR / match["sport"] / match["league"] / match["match_id"] / fixture_name)
    data = json.loads(path.read_text())
    return data if isinstance(data, list) else [data]


def run_replay(
    har_for_match, tmp_path: Path, match: dict[str, str], fixture_name: str, **scraper_args: Any
) -> list[dict[str, Any]]:
    """Run `historic --match-link` on the HAR paired with the golden (the live site under --live).

    Asserts exit code 0 and returns the parsed JSON output.
    """
    output_path = tmp_path / "output"
    exit_code, _stdout, stderr = run_historic(
        sport=match["sport"],
        match_link=match["url"],
        output_path=output_path,
        har_path=har_for_match(match["sport"], match["league"], match["match_id"], fixture_name),
        **scraper_args,
    )
    assert exit_code == 0, f"Scraper failed: {stderr}"
    return json.loads(Path(f"{output_path}.json").read_text())


def replay_and_compare(
    har_for_match, tmp_path: Path, match: dict[str, str], fixture_name: str, **scraper_args: Any
) -> list[dict[str, Any]]:
    """run_replay, then compare the first match with the golden; returns the parsed output for further checks."""
    actual = run_replay(har_for_match, tmp_path, match, fixture_name, **scraper_args)
    result = compare_match_data(actual[0], load_golden(match, fixture_name)[0])
    assert result.passed, str(result)
    return actual
