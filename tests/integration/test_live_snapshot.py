"""Integration tests for the live (in-play) flow.

Two complementary tests:

- A deterministic HAR replay of the live-now listing captured on 2026-07-20. Runs
  by default, no network. The in-play match page captured with it does not replay
  (agentic-gotchas §16), so the match snapshot itself has no replay test.
- A self-discovering live-network test that scrapes whatever is in play right now
  and skips when nothing is. Marked live_only, run with --live.

Both drive the CLI as a subprocess, like the other integration tests, which also
covers the real user-facing path.
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = [pytest.mark.integration]

# Captured live on 2026-07-20 at half-time. "Club Friendly" is what OddsPortal
# reports as the league, and the only in-play book was a crypto one.
REPLAY_MATCH = {
    "league": "club-friendly",
    "match_id": "samgurali-spaeri-0nx5GXqB",
}

# Wall-clock fields: they legitimately differ on every run.
VOLATILE_FIELDS = {"scraped_at_utc", "scraped_date"}

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


def test_live_listing_replays_captured_live_now_page(tmp_path, har_for_match):
    """Parse the real live-now listing DOM, not the hand-written HTML the unit tests use."""
    har = har_for_match("football", REPLAY_MATCH["league"], REPLAY_MATCH["match_id"], "live_listing.json")
    if har is None:
        pytest.skip("no listing HAR (or --live requested)")

    expected_path = (
        Path(__file__).parent / "fixtures" / "football" / REPLAY_MATCH["league"] / REPLAY_MATCH["match_id"]
    ) / "live_listing.json"
    expected = json.loads(expected_path.read_text())

    output_path = tmp_path / "listing.json"
    cmd = [
        "uv",
        "run",
        "oddsharvester",
        "live",
        "--sport",
        "football",
        "--links-only",
        "--headless",
        "--output",
        str(output_path),
    ]
    env = {**os.environ, "ODDSHARVESTER_HAR_REPLAY": str(har)}
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False, env=env)  # noqa: S603

    assert result.returncode == 0, f"listing replay failed\n{(result.stdout + result.stderr)[-2000:]}"
    actual = json.loads(output_path.read_text())

    assert actual == expected, "the live-now listing no longer parses to the captured links"
    assert all(
        row["match_link"].endswith(tuple("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        for row in actual
    )
    assert all("/inplay-odds/#" in row["match_link"] for row in actual), (
        "listing hrefs must already carry the in-play path and fragment"
    )


@pytest.mark.live_only
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
            assert str(match.get("scraped_at_utc", "")).endswith("Z"), (
                f"{sport}: every live record needs a UTC scrape timestamp, got {match.get('scraped_at_utc')!r}"
            )
            assert "live_period" in match, f"{sport}: live records must carry a period marker"
            assert "live_score_raw" in match, f"{sport}: live records must carry a raw score"
            assert "_live_ended" not in match, f"{sport}: the ended-match sentinel must never reach output"

        periods = {str(m.get("live_period", "")).casefold() for m in records}
        assert not any("final" in p for p in periods), (
            f"{sport}: finished matches leaked into a live snapshot: {sorted(periods)}"
        )
        return

    pytest.skip("No live matches with in-play odds found on any candidate sport right now.")
