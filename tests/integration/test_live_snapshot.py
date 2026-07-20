"""Live-network integration test for the live (in-play) snapshot flow.

No HAR replay here: a live match is ephemeral, so a recorded fixture stops being
live the moment it is captured. The test instead self-discovers whatever is in
play right now and skips when nothing is.

Runs the CLI as a subprocess like the other integration tests, which also covers
the real user-facing path.

Run with: uv run pytest tests/integration/test_live_snapshot.py -q -m integration --live
"""

import json
from pathlib import Path
import subprocess

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.live_only]

# Ordered by how likely each sport is to have something in play at an arbitrary hour.
CANDIDATE_SPORTS = [("tennis", "match_winner"), ("basketball", "home_away"), ("football", "1x2")]


def _run_live(sport: str, market: str, output_path: Path) -> tuple[int, str]:
    cmd = [
        "uv",
        "run",
        "oddsharvester",
        "live",
        "--sport",
        sport,
        "--market",
        market,
        "--headless",
        "--output",
        str(output_path),
    ]
    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    return result.returncode, result.stdout + result.stderr


@pytest.mark.slow
def test_live_snapshot_self_discovering(tmp_path):
    """A live snapshot carries per-match live context and only genuinely live matches."""
    for sport, market in CANDIDATE_SPORTS:
        output_path = tmp_path / f"live_{sport}.json"
        exit_code, output = _run_live(sport, market, output_path)

        assert exit_code == 0, f"{sport}: live command failed\n{output[-2000:]}"

        if not output_path.exists():
            # "No live matches found right now" is a valid, successful outcome.
            assert "No live matches" in output, f"{sport}: no output file and no explanation\n{output[-2000:]}"
            continue

        records = json.loads(output_path.read_text())
        assert records, f"{sport}: an output file was written but holds no records"

        for match in records:
            assert str(match.get("scraped_at_utc", "")).endswith(
                "Z"
            ), f"{sport}: every live record needs a UTC scrape timestamp, got {match.get('scraped_at_utc')!r}"
            assert "live_period" in match, f"{sport}: live records must carry a period marker"
            assert "live_score_raw" in match, f"{sport}: live records must carry a raw score"
            assert "_live_ended" not in match, f"{sport}: the ended-match sentinel must never reach output"

        periods = {str(m.get("live_period", "")).casefold() for m in records}
        assert not any(
            "final" in p for p in periods
        ), f"{sport}: finished matches leaked into a live snapshot: {sorted(periods)}"
        return

    pytest.skip("No live matches with in-play odds found on any candidate sport right now.")
