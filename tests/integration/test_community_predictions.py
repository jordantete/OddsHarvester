"""Integration test for the community command (HAR replay; the live site under --live).

Re-capture fixtures with:
    uv run python scripts/capture_all_hars.py --only community
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "community"
HAR = FIXTURES / "top_predictions_football.har"
SNAPSHOT = FIXTURES / "top_predictions_football.json"

# The parser infers a row's year from the day the test runs, so the parsed kickoff follows the run date. The page's
# own label (kickoff_text) is absolute for a row dated more than a day from that day: every row of the capture is,
# from 2026-10-03 on.
VOLATILE_FIELDS = {"kickoff", "scraped_at"}


@pytest.mark.integration
def test_community_command_har_replay(temp_output_dir, pytestconfig):
    live = pytestconfig.getoption("--live")
    output = temp_output_dir / "out.json"
    env = os.environ.copy()
    if not live:
        env["ODDSHARVESTER_HAR_REPLAY"] = str(HAR)

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "oddsharvester",
            "community",
            "-s",
            "football",
            "--timezone",
            "UTC",
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
    scraped = json.loads(output.read_text())
    expected = json.loads(SNAPSHOT.read_text())
    assert len(scraped) > 0
    if live:
        # Today's picks are other matches: only the record shape can match the golden.
        assert {tuple(record) for record in scraped} == {tuple(expected[0])}
        return
    assert len(scraped) == len(expected)

    def stable(records):
        return [{k: v for k, v in r.items() if k not in VOLATILE_FIELDS} for r in records]

    assert stable(scraped) == stable(expected)
