"""Integration tests for scrape-upcoming filters (league + date combination)."""

from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import subprocess

import pytest


def _run_upcoming(
    sport: str,
    league: str | None,
    target_date: str | None,
    output_path: Path,
    timeout: int = 300,
) -> tuple[int, str, str]:
    """Run `oddsharvester upcoming` with optional --league / --date."""
    cmd = [
        "uv",
        "run",
        "oddsharvester",
        "upcoming",
        "--sport",
        sport,
        "--format",
        "json",
        "--headless",
        "--output",
        str(output_path),
    ]
    if league:
        cmd.extend(["--league", league])
    if target_date:
        cmd.extend(["--date", target_date])

    result = subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def _next_saturday(today: date) -> date:
    """Return the next Saturday on or after `today` (helps hit match-dense days)."""
    days_ahead = (5 - today.weekday()) % 7
    return today + timedelta(days=days_ahead or 7)


def _empty_listing(exit_code: int, stderr: str) -> bool:
    """`upcoming` exits 1 on a league with no match; a listing failure or a crash also names itself on stderr."""
    return exit_code == 1 and "Failed URLs" not in stderr and "Traceback" not in stderr


def _premier_league_break(today: date) -> bool:
    """1 June to 10 August: the Premier League has no fixture to list."""
    return (6, 1) <= (today.month, today.day) <= (8, 10)


@pytest.mark.integration
@pytest.mark.live_only
class TestUpcomingLeagueDateFilter:
    """End-to-end tests for combining --league and --date on scrape-upcoming."""

    def test_upcoming_league_without_date_returns_all_dates(self, temp_output_dir):
        """Baseline: --league alone should succeed (regression guard)."""
        output_path = temp_output_dir / "upcoming_league_only"
        exit_code, _stdout, stderr = _run_upcoming(
            sport="football",
            league="england-premier-league",
            target_date=None,
            output_path=output_path,
        )
        if _empty_listing(exit_code, stderr) and _premier_league_break(datetime.now(UTC).date()):
            pytest.skip("Premier League summer break: no upcoming fixture to list.")
        assert exit_code == 0, f"Scraper failed: {stderr}"

        json_file = Path(f"{output_path}.json")
        # The command may succeed with zero matches; we don't fail in that case.
        if json_file.exists():
            data = json.loads(json_file.read_text())
            assert isinstance(data, list)

    def test_upcoming_league_with_date_filters_to_that_date(self, temp_output_dir):
        """Core regression test: --league + --date should keep only matches of that date.

        `upcoming` exits 1 when the league lists no match: that outcome skips, any other
        failure fails.
        """
        output_path = temp_output_dir / "upcoming_league_date"

        # Pick the next Saturday to maximize the odds of finding Premier League matches.
        target = _next_saturday(datetime.now(UTC).date())
        target_str = target.strftime("%Y%m%d")

        exit_code, _stdout, stderr = _run_upcoming(
            sport="football",
            league="england-premier-league",
            target_date=target_str,
            output_path=output_path,
        )

        json_file = Path(f"{output_path}.json")
        if _empty_listing(exit_code, stderr):
            pytest.skip(f"No Premier League match listed for {target_str} (upcoming exits 1 on an empty listing).")
        assert exit_code == 0, f"Scraper failed: {stderr}"
        assert json_file.exists(), f"exit 0 but no output written: {stderr[-2000:]}"

        data = json.loads(json_file.read_text())
        assert isinstance(data, list)
        assert data, "Expected at least one match in the result set"

        expected_prefix = target.strftime("%Y-%m-%d")
        for match in data:
            match_date = match.get("match_date")
            assert match_date is not None, f"Missing match_date in {match}"
            assert match_date.startswith(expected_prefix), (
                f"Date filter failed: expected match_date to start with {expected_prefix}, "
                f"got '{match_date}' for match {match.get('match_link')}"
            )

            league_name = (match.get("league_name") or "").lower()
            assert "premier league" in league_name, (
                f"League filter failed: expected 'Premier League', got '{league_name}' "
                f"for match {match.get('match_link')}"
            )
