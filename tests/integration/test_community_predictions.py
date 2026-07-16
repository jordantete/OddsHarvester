"""Integration test for the community command (HAR replay).

Re-capture fixtures with:
    ODDSHARVESTER_HAR_RECORD=tests/integration/fixtures/community/top_predictions_football.har \\
        uv run oddsharvester community -s football --headless \\
        -o tests/integration/fixtures/community/top_predictions_football.json
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "community"
HAR = FIXTURES / "top_predictions_football.har"
SNAPSHOT = FIXTURES / "top_predictions_football.json"

# Kickoff fields depend on the date the test runs (relative "Today" labels resolve
# against the current date, not the capture date), so they are excluded from comparison.
VOLATILE_FIELDS = {"kickoff", "kickoff_text", "scraped_at"}


@pytest.mark.integration
def test_community_command_har_replay(temp_output_dir):
    output = temp_output_dir / "out.json"
    env = os.environ.copy()
    env["ODDSHARVESTER_HAR_REPLAY"] = str(HAR)

    result = subprocess.run(  # noqa: S603
        ["uv", "run", "oddsharvester", "community", "-s", "football", "--headless", "-o", str(output)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )

    assert result.returncode == 0, f"stderr: {result.stderr[-2000:]}"
    scraped = json.loads(output.read_text())
    expected = json.loads(SNAPSHOT.read_text())
    assert len(scraped) == len(expected)
    assert len(scraped) > 0

    def stable(records):
        return [{k: v for k, v in r.items() if k not in VOLATILE_FIELDS} for r in records]

    assert stable(scraped) == stable(expected)
