"""Run the oddsharvester CLI for integration tests."""

import os
from pathlib import Path
import subprocess


def run_historic(
    sport: str,
    match_link: str,
    markets: list[str],
    output_path: Path,
    period: str | None = None,
    bookies_filter: str = "all",
    output_format: str = "json",
    season: str = "current",
    timeout: int = 300,
    har_path: Path | None = None,
    local_kickoff: bool = False,
    extra_args: list[str] | None = None,
) -> tuple[int, str, str]:
    """Run `oddsharvester historic --match-link` and return (exit_code, stdout, stderr)."""
    cmd = [
        "uv",
        "run",
        "oddsharvester",
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
        "--season",
        season,
        "--headless",
        "--output",
        str(output_path),
    ]

    if local_kickoff:
        cmd.append("--local-kickoff")

    if period:
        cmd.extend(["--period", period])

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
