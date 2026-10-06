"""Integration tests for the community --user and --match-url modes (HAR replay; the live site under --live).

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

PREMATCH_HAR = FIXTURES / "match_community_prematch.har"
PREMATCH_SNAPSHOT = FIXTURES / "match_community_prematch.json"


def _env(har: Path | None) -> dict[str, str]:
    """The environment of a run: replayed from `har`, or live when it is None (--live)."""
    env = os.environ.copy()
    if har is not None:
        env["ODDSHARVESTER_HAR_REPLAY"] = str(har)
    return env


@pytest.mark.integration
def test_user_profile_command_har_replay(temp_output_dir, pytestconfig):
    live = pytestconfig.getoption("--live")
    output = temp_output_dir / "out.json"
    env = _env(None if live else PROFILE_HAR)

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
    if not live:
        assert record["statistics"] == expected["statistics"]

    # The Feed tab's predictions come from a cache-busted AJAX call
    # (/proxy/ajax-communityFeed/profile/<id>/<timestamp>/) that HAR replay
    # cannot serve (not_found=abort), so predictions are only checked when the
    # run produced them; run with --live for that coverage.
    if record["predictions"] and live:
        assert all(sum(outcome["picked"] for outcome in p["outcomes"]) == 1 for p in record["predictions"])
    elif record["predictions"]:
        assert len(record["predictions"]) == len(expected["predictions"])

        # The parser infers a row's year from the day the test runs, so kickoff follows the run date.
        def stable(predictions):
            return [{k: v for k, v in p.items() if k != "kickoff"} for p in predictions]

        assert stable(record["predictions"]) == stable(expected["predictions"])
        assert record["predictions"][0]["pick_odds"] is not None
        for prediction in record["predictions"]:
            picked_count = sum(1 for outcome in prediction["outcomes"] if outcome["picked"])
            assert picked_count == 1


def _replay_match_community(har: Path | None, golden: Path, output: Path) -> tuple[dict, dict]:
    """Run `community --match-url` for a golden's match_url under UTC, from `har` (live when None).

    Returns (record, golden record).
    """
    expected = json.loads(golden.read_text())[0]
    env = _env(har)

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
def test_match_community_command_har_replay(temp_output_dir, pytestconfig):
    live = pytestconfig.getoption("--live")
    record, expected = _replay_match_community(
        None if live else MATCH_HAR, MATCH_SNAPSHOT, temp_output_dir / "out.json"
    )

    assert record["markets"], "expected at least one community market"
    if live:
        # Votes still move after the match; the match and the market shown on load do not.
        identity = ("match_url", "event_id", "home_team", "away_team", "kickoff", "is_prematch")
        assert {key: record[key] for key in identity} == {key: expected[key] for key in identity}
        assert [market["market"] for market in record["markets"]] == [m["market"] for m in expected["markets"]]
        return
    assert _without_scraped_at(record) == _without_scraped_at(expected)


@pytest.mark.integration
def test_prematch_community_command_har_replay(temp_output_dir, pytestconfig):
    """Before kickoff: the header reads Today or Tomorrow around the replay day, the stored kickoff must not."""
    if pytestconfig.getoption("--live"):
        pytest.skip("its match has kicked off since the capture: the golden describes the recorded page")
    record, expected = _replay_match_community(PREMATCH_HAR, PREMATCH_SNAPSHOT, temp_output_dir / "out.json")

    assert record["is_prematch"] is True
    assert record["markets"], "expected at least one community market on replay"
    assert _without_scraped_at(record) == _without_scraped_at(expected)
