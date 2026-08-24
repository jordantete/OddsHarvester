"""Integration tests for the community --user and --match-url modes (HAR replay).

Re-capture fixtures with:
    ODDSHARVESTER_HAR_RECORD=tests/integration/fixtures/community/user_profile_blapro.har \\
        uv run oddsharvester community --user BLAPRO --headless \\
        -o tests/integration/fixtures/community/user_profile_blapro.json

    ODDSHARVESTER_HAR_RECORD=tests/integration/fixtures/community/match_community_fulham_chelsea.har \\
        uv run oddsharvester community --match-url "<pre-match h2h url>" --headless \\
        -o tests/integration/fixtures/community/match_community_fulham_chelsea.json
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
        ["uv", "run", "oddsharvester", "community", "--user", "BLAPRO", "--headless", "-o", str(output)],  # noqa: S607
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

        # kickoff / kickoff_text render in the browser timezone (differs by host/CI),
        # so exclude them from the deep comparison (same pattern as test_community_predictions).
        def stable(predictions):
            return [{k: v for k, v in p.items() if k not in {"kickoff", "kickoff_text"}} for p in predictions]

        assert stable(record["predictions"]) == stable(expected["predictions"])
        assert record["predictions"][0]["pick_odds"] is not None
        for prediction in record["predictions"]:
            picked_count = sum(1 for outcome in prediction["outcomes"] if outcome["picked"])
            assert picked_count == 1


# Redesign note: the hash-hydrated match view replays cleanly from HAR (the SPA
# fetches by event id with stable URLs), so this stays in default replay mode.
@pytest.mark.integration
def test_match_community_command_har_replay(temp_output_dir):
    expected = json.loads(MATCH_SNAPSHOT.read_text())[0]
    output = temp_output_dir / "out.json"
    env = os.environ.copy()
    env["ODDSHARVESTER_HAR_REPLAY"] = str(MATCH_HAR)

    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "uv",
            "run",
            "oddsharvester",
            "community",
            "--match-url",
            expected["match_url"],
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

    assert record["markets"], "expected at least one community market on replay"
    assert record["markets"][0]["market"] == expected["markets"][0]["market"]
    assert record["markets"] == expected["markets"]
    for outcome in record["markets"][0]["outcomes"]:
        assert 0 <= outcome["votes_pct"] <= 100
