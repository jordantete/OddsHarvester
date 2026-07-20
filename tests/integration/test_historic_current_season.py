"""Integration regression tests for `historic --season current` across sports (issue #59).

These tests exercise the league + season flow end-to-end (URL builder + scraper),
which the match-link based tests in `test_cli_options.py` do not cover. They guard
against the regression where `--season current` raised `ValueError` for sports
missing from the historic command's allowlist (basketball, american-football).

The bug manifested as an immediate `ValueError: Invalid season format: current`
during URL building, *before* any browser activity. So the test deliberately does
not wait for the full per-match scraping to complete: it lets the scraper start,
checks that it gets past URL building, then terminates the subprocess. A complete
scrape of the current season can take 5+ minutes per sport on busy leagues,
which is far longer than what this regression check requires.
"""

import subprocess
import time

import pytest


def _spawn_historic_league(
    sport: str,
    league: str,
    market: str,
    output_path,
    season: str = "current",
) -> subprocess.Popen:
    """Start `oddsharvester historic` as a subprocess (no --match-link, no wait)."""
    cmd = [
        "uv",
        "run",
        "oddsharvester",
        "historic",
        "--sport",
        sport,
        "--league",
        league,
        "--season",
        season,
        "--market",
        market,
        "--max-pages",
        "1",
        "--format",
        "json",
        "--headless",
        "--output",
        str(output_path),
    ]
    return subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_past_url_building(process: subprocess.Popen, deadline_seconds: float = 60.0) -> tuple[str, str]:
    """Wait until the process either exits (URL build failed/scrape finished) or the deadline elapses.

    Returns the captured (stdout, stderr) so callers can assert on the actual error path.
    The bug under test is a fail-fast `ValueError` raised in the URL builder layer,
    so a process still alive after 60s is conclusive evidence URL building succeeded.
    """
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            break
        time.sleep(1.0)

    if process.poll() is None:
        process.terminate()
        try:
            return process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.communicate()

    return process.communicate()


@pytest.mark.integration
@pytest.mark.live_only
class TestHistoricCurrentSeason:
    """End-to-end regression coverage for `--season current` (issue #59)."""

    @pytest.mark.parametrize(
        ("sport", "league", "market"),
        [
            # Previously broken — these sports were missing from CURRENT_SEASON_SPORTS allowlist:
            ("basketball", "nba", "home_away"),
            ("american-football", "nfl", "home_away"),
            # Regression guards — sports that previously worked must still work after the
            # allowlist removal (the CLI used to normalize 'current' -> None for these only):
            ("football", "england-premier-league", "1x2"),
            ("tennis", "atp-australian-open", "match_winner"),
        ],
    )
    def test_current_season_passes_url_building(self, sport, league, market, temp_output_dir):
        """`--season current` must reach the scraping stage (no ValueError at URL build)."""
        output_path = temp_output_dir / f"historic_current_{sport}_{league}"

        process = _spawn_historic_league(sport=sport, league=league, market=market, output_path=output_path)
        _stdout, stderr = _wait_past_url_building(process)

        assert "Invalid season format" not in stderr, (
            f"`--season current` was rejected for {sport}/{league} — issue #59 regressed:\n{stderr}"
        )

        scraping_started_markers = (
            "Successfully navigated",
            "match links",
            "Scraping market",
            "Successfully scraped",
        )
        assert any(marker in stderr for marker in scraping_started_markers), (
            f"No evidence the scraper progressed past URL building for {sport}/{league}.\n"
            f"Process exit code: {process.returncode}\nstderr:\n{stderr}"
        )
