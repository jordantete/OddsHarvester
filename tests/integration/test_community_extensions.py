"""Integration tests for the community --user and --match-url modes (HAR replay).

Re-capture fixtures with:
    uv run python scripts/capture_all_hars.py --only community
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "community"

PROFILE_HAR = FIXTURES / "user_profile_blapro.har"
PROFILE_SNAPSHOT = FIXTURES / "user_profile_blapro.json"

MATCH_HAR = FIXTURES / "match_community_fulham_chelsea.har"
MATCH_SNAPSHOT = FIXTURES / "match_community_fulham_chelsea.json"


@pytest.mark.integration
def test_user_profile_command_har_replay(temp_output_dir):
    output = temp_output_dir / "out.json"
    env = os.environ.copy()
    env["ODDSHARVESTER_HAR_REPLAY"] = str(PROFILE_HAR)

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "oddsharvester",
            "community",
            "--user",
            "BLAPRO",
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
    record = json.loads(output.read_text())[0]
    expected = json.loads(PROFILE_SNAPSHOT.read_text())[0]

    assert record["username"] == expected["username"]
    assert record["privacy"] == expected["privacy"]
    assert len(record["statistics"]) == len(expected["statistics"])
    assert record["statistics"] == expected["statistics"]

    # The Feed tab's predictions come from a cache-busted AJAX call
    # (/proxy/ajax-communityFeed/profile/<id>/<timestamp>/) that HAR replay
    # cannot serve (not_found=abort), so predictions are only compared when the
    # replay produced them; run with --live for full coverage.
    if record["predictions"]:
        assert len(record["predictions"]) == len(expected["predictions"])

        # The parser infers a row's year from the day the test runs, so kickoff follows the run date.
        def stable(predictions):
            return [{k: v for k, v in p.items() if k != "kickoff"} for p in predictions]

        assert stable(record["predictions"]) == stable(expected["predictions"])
        assert record["predictions"][0]["pick_odds"] is not None
        for prediction in record["predictions"]:
            picked_count = sum(1 for outcome in prediction["outcomes"] if outcome["picked"])
            assert picked_count == 1


def _replay_match_community(har: Path, golden: Path, output: Path) -> tuple[dict, dict]:
    """Replay `community --match-url` for a golden's match_url under UTC; returns (record, golden record)."""
    expected = json.loads(golden.read_text())[0]
    env = os.environ.copy()
    env["ODDSHARVESTER_HAR_REPLAY"] = str(har)

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "oddsharvester",
            "community",
            "--match-url",
            expected["match_url"],
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
    return json.loads(output.read_text())[0], expected


def _without_scraped_at(record: dict) -> dict:
    return {k: v for k, v in record.items() if k != "scraped_at"}


# Redesign note: the hash-hydrated match view replays cleanly from HAR (the SPA
# fetches by event id with stable URLs), so this stays in default replay mode.
@pytest.mark.integration
def test_match_community_command_har_replay(temp_output_dir):
    record, expected = _replay_match_community(MATCH_HAR, MATCH_SNAPSHOT, temp_output_dir / "out.json")

    assert record["markets"], "expected at least one community market on replay"
    assert _without_scraped_at(record) == _without_scraped_at(expected)
