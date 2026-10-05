"""HAR replays of two listings captured on 2026-10-05, the anti-bot trap row included (gotchas §28).

Recapture: uv run python scripts/capture_all_hars.py --only listing
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = [pytest.mark.integration]

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "football" / "premier-league" / "upcoming-listing"
HISTORIC_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "football" / "premier-league" / "historic-listing"


def _replay_listing(har: Path, args: list[str], output_path: Path) -> list[dict]:
    """Run the CLI on the HAR, offline, and return the rows it wrote."""
    cmd = ["uv", "run", "oddsharvester", *args, "--links-only", "--headless", "--timezone", "UTC"]
    env = {**os.environ, "ODDSHARVESTER_HAR_REPLAY": str(har)}
    result = subprocess.run(  # noqa: S603
        [*cmd, "--output", str(output_path)], capture_output=True, text=True, timeout=300, check=False, env=env
    )

    assert result.returncode == 0, f"listing replay failed\n{(result.stdout + result.stderr)[-2000:]}"
    return json.loads(output_path.read_text())


def test_upcoming_listing_replay_skips_the_anti_bot_trap_row(tmp_path, har_for_match):
    har = har_for_match("football", "premier-league", "upcoming-listing", "upcoming_listing.json")
    if har is None:
        pytest.skip("no listing HAR (or --live requested)")
    expected = json.loads((FIXTURE_DIR / "upcoming_listing.json").read_text())

    rows = _replay_listing(
        har, ["upcoming", "--sport", "football", "--league", "england-premier-league"], tmp_path / "listing.json"
    )

    # The trap can clone a group's first row with its date header, which used to re-date the rows after it.
    assert rows == expected
    assert all("/#" in row["match_link"] for row in rows), "a link without its event fragment is the trap's clone"


def test_historic_listing_replay_walks_two_pages(tmp_path, har_for_match):
    har = har_for_match("football", "premier-league", "historic-listing", "historic_listing.json")
    if har is None:
        pytest.skip("no listing HAR (or --live requested)")
    expected = json.loads((HISTORIC_FIXTURE_DIR / "historic_listing.json").read_text())

    args = ["historic", "--sport", "football", "--league", "england-premier-league", "--season", "2024-2025"]
    rows = _replay_listing(har, [*args, "--max-pages", "2"], tmp_path / "listing.json")

    # Two pages of 50 rows, each page's trap clone skipped.
    assert rows == expected
    assert len({row["match_link"] for row in rows}) == 100
    assert all("/#" in row["match_link"] for row in rows), "a link without its event fragment is the trap's clone"
