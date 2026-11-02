"""Run the oddsharvester CLI for integration tests."""

import json
import os
from pathlib import Path
import subprocess


def har_capture_moment(har_path: Path) -> str:
    """The instant the HAR's first request was recorded, as ISO 8601."""
    return json.loads(har_path.read_text())["log"]["entries"][0]["startedDateTime"]


def run_historic(
    sport: str,
    match_link: str,
    markets: list[str],
    output_path: Path,
    period: str | None = None,
    bookies_filter: str = "all",
    output_format: str = "json",
    season: str | None = None,
    timeout: int = 600,
    har_path: Path | None = None,
    local_kickoff: bool = False,
    extra_args: list[str] | None = None,
) -> tuple[int, str, str]:
    """Run `oddsharvester historic --match-link` and return (exit_code, stdout, stderr)."""
    # The parser reads the page's offset from the clock, and a replay shows times at the capture moment's offset.
    if har_path is not None:
        launcher = ["uv", "run", "python", "-m", "tests.integration.helpers.frozen_cli", har_capture_moment(har_path)]
    else:
        launcher = ["uv", "run", "oddsharvester"]
    cmd = [
        *launcher,
        "historic",
        "--sport",
        sport,
        "--match-link",
        match_link,
        "--market",
        ",".join(markets),
        "--format",
        output_format,
        "--bookies-filter",
        bookies_filter,
        "--headless",
        "--output",
        str(output_path),
    ]

    if season:
        cmd.extend(["--season", season])

    if local_kickoff:
        cmd.append("--local-kickoff")

    if period:
        cmd.extend(["--period", period])

    # The page renders times at the browser's current UTC offset: a DST host zone would shift match_date.
    if "--timezone" not in (extra_args or []):
        cmd.extend(["--timezone", "UTC"])

    cmd.extend(extra_args or [])

    env = os.environ.copy()
    if har_path is not None:
        env["ODDSHARVESTER_HAR_REPLAY"] = str(har_path)

    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )

    return result.returncode, result.stdout, result.stderr
