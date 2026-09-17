"""Integration test for the team command (HAR replay).

Re-capture the fixture with:
    ODDSHARVESTER_HAR_RECORD=tests/integration/fixtures/team/teams.har \\
        uv run oddsharvester team --team lId4TMwf,WGt8En5I --headless \\
        -o tests/integration/fixtures/team/teams.json
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "team"
TEAMS_HAR = FIXTURES / "teams.har"
TEAMS_SNAPSHOT = FIXTURES / "teams.json"


@pytest.mark.integration
def test_team_command_har_replay(temp_output_dir):
    """Liverpool carries every field; Barcelona FC carries none of the venue ones."""
    output = temp_output_dir / "out.json"
    env = os.environ.copy()
    env["ODDSHARVESTER_HAR_REPLAY"] = str(TEAMS_HAR)

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "oddsharvester",
            "team",
            "--team",
            "lId4TMwf,WGt8En5I",
            "--headless",
            "-o",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )

    assert result.returncode == 0, f"stderr: {result.stderr[-2000:]}"

    records = json.loads(output.read_text())
    expected = json.loads(TEAMS_SNAPSHOT.read_text())
    assert [_without_timestamp(r) for r in records] == [_without_timestamp(r) for r in expected]

    liverpool, barcelona = records
    assert liverpool["list_name"] == "Liverpool"
    assert liverpool["venue"] == "Anfield"
    assert barcelona["list_name"] == "Barcelona", "resolved although the page shows no odds rows"
    assert barcelona["venue"] is None


def _without_timestamp(record: dict) -> dict:
    return {key: value for key, value in record.items() if key != "scraped_at"}
