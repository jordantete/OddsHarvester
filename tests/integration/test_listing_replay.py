"""HAR replay of a league listing captured on 2026-10-05, the anti-bot trap row included (gotchas §28).

Recapture: uv run python scripts/capture_all_hars.py --only listing
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

pytestmark = [pytest.mark.integration]

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "football" / "premier-league" / "upcoming-listing"


def test_upcoming_listing_replay_skips_the_anti_bot_trap_row(tmp_path, har_for_match):
    har = har_for_match("football", "premier-league", "upcoming-listing", "upcoming_listing.json")
    if har is None:
        pytest.skip("no listing HAR (or --live requested)")
    expected = json.loads((FIXTURE_DIR / "upcoming_listing.json").read_text())

    output_path = tmp_path / "listing.json"
    cmd = [
        "uv",
        "run",
        "oddsharvester",
        "upcoming",
        "--sport",
        "football",
        "--league",
        "england-premier-league",
        "--links-only",
        "--headless",
        "--timezone",
        "UTC",
        "--output",
        str(output_path),
    ]
    env = {**os.environ, "ODDSHARVESTER_HAR_REPLAY": str(har)}
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False, env=env)  # noqa: S603

    assert result.returncode == 0, f"listing replay failed\n{(result.stdout + result.stderr)[-2000:]}"
    rows = json.loads(output_path.read_text())
    # The trap can clone a group's first row with its date header, which used to re-date the rows after it.
    assert rows == expected
    assert all("/#" in row["match_link"] for row in rows), "a link without its event fragment is the trap's clone"
