"""Integration tests for the live (in-play) snapshot flow.

Two complementary tests:

- A deterministic HAR replay of a real live football match, captured while it was
  in play on 2026-07-20. A live page is ephemeral, so once a match ends its
  in-play view is gone for good: the HAR is the only way this flow can ever be
  replayed. Runs by default, no network.
- A self-discovering live-network test that scrapes whatever is in play right now
  and skips when nothing is. Marked live_only, run with --live.

Both drive the CLI as a subprocess, like the other integration tests, which also
covers the real user-facing path.
"""

import json
import os
from pathlib import Path
import re
import subprocess

import pytest

pytestmark = [pytest.mark.integration]

# Captured live on 2026-07-20 at half-time. "Club Friendly" is what OddsPortal
# reports as the league, and the only in-play book was a crypto one.
REPLAY_MATCH = {
    "league": "club-friendly",
    "match_id": "samgurali-spaeri-0nx5GXqB",
    "fixture": "live_1x2_all.json",
    "url": ("https://www.oddsportal.com/football/h2h/samgurali-UVbdPPp5/spaeri-lhbBhs66/inplay-odds/#0nx5GXqB"),
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


def test_live_snapshot_replays_captured_football_match(tmp_path, har_for_match):
    """A captured in-play football match replays: fixed identity, live-shaped context.

    The score and period are deliberately NOT asserted against captured values,
    see the comment on the live-context assertions below.
    """
    har = har_for_match("football", REPLAY_MATCH["league"], REPLAY_MATCH["match_id"], REPLAY_MATCH["fixture"])
    if har is None:
        pytest.skip("no HAR for the captured match (or --live requested)")

    expected_path = (
        Path(__file__).parent / "fixtures" / "football" / REPLAY_MATCH["league"] / REPLAY_MATCH["match_id"]
    ) / REPLAY_MATCH["fixture"]
    expected = json.loads(expected_path.read_text())[0]

    output_path = tmp_path / "replay.json"
    cmd = [
        "uv",
        "run",
        "oddsharvester",
        "live",
        "--sport",
        "football",
        "--match-link",
        REPLAY_MATCH["url"],
        "--market",
        "1x2",
        "--headless",
        "--output",
        str(output_path),
    ]
    env = {**os.environ, "ODDSHARVESTER_HAR_REPLAY": str(har)}
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False, env=env)  # noqa: S603

    assert result.returncode == 0, f"replay failed\n{(result.stdout + result.stderr)[-2000:]}"
    assert output_path.exists(), "replay produced no output"

    records = json.loads(output_path.read_text())
    assert len(records) == 1
    actual = records[0]

    # The in-play page self-refreshes via first-party .dat feeds, and the HAR was
    # recorded in "full" mode, so it holds several snapshots of the live state, not
    # one frozen instant. Replay timing picks one of them, which means live_period
    # and live_score are legitimately non-deterministic across replays (captured at
    # "Half-time", a later replay saw "49'"). Assert the SHAPE of the live context,
    # not the captured values.
    assert actual["live_period"], "a live record must carry a period marker"
    assert re.fullmatch(
        r"\d+:\d+.*", actual["live_score_raw"]
    ), f"live_score_raw should start with a numeric score, got {actual['live_score_raw']!r}"
    assert str(actual["scraped_at_utc"]).endswith("Z")

    # Match identity, on the other hand, is fixed: it must never drift on replay.
    for key in ("home_team", "away_team", "league_name", "match_date"):
        assert actual[key] == expected[key], f"{key} drifted from the capture"

    # The odds table comes from the same in-play tab as the capture.
    assert actual["1x2_market"], "the in-play odds table must be present"
    book = actual["1x2_market"][0]
    assert {"1", "X", "2", "bookmaker_name"} <= set(book)


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
    assert all(
        "/inplay-odds/#" in row["match_link"] for row in actual
    ), "listing hrefs must already carry the in-play path and fragment"


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
