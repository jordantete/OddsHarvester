"""Integration tests for the community --user and --match-url modes (HAR replay).

Re-capture fixtures with:
    ODDSHARVESTER_HAR_RECORD=tests/integration/fixtures/community/user_profile_blapro.har \\
        uv run oddsharvester community --user BLAPRO --headless \\
        -o tests/integration/fixtures/community/user_profile_blapro.json

    ODDSHARVESTER_HAR_RECORD=tests/integration/fixtures/community/match_community_fenerbahce_gornik.har \\
        uv run oddsharvester community --match-url "<pre-match h2h url>" --headless \\
        -o tests/integration/fixtures/community/match_community_fenerbahce_gornik.json
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "community"

PROFILE_HAR = FIXTURES / "user_profile_blapro.har"
PROFILE_SNAPSHOT = FIXTURES / "user_profile_blapro.json"

MATCH_HAR = FIXTURES / "match_community_fenerbahce_gornik.har"
MATCH_SNAPSHOT = FIXTURES / "match_community_fenerbahce_gornik.json"


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


# The pre-match H2H page is subject to the "Known limit" in CLAUDE.md (runtime
# cache-busted AJAX on H2H pages between teams that play each other repeatedly,
# e.g. NBA/real-madrid-barcelona/djokovic-sinner), which HAR replay can't reproduce.
# Verified deterministic across repeated replays for this one-off fixture (no
# repeat-matchup ambiguity), so it is NOT marked live_only.
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
    assert record["markets"][0]["total_votes"] == expected["markets"][0]["total_votes"]
    assert record["markets"] == expected["markets"]
