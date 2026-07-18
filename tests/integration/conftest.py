"""Fixtures for integration tests."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any

import pytest

# Path to fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_output_dir():
    """Provides a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def run_scraper():
    """
    Factory fixture to run oddsharvester commands.

    Returns a function that runs the scraper and returns (exit_code, stdout, stderr).
    """

    def _run(
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
    ) -> tuple[int, str, str]:
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

    return _run


@pytest.fixture
def load_fixture():
    """
    Factory fixture to load expected fixtures.

    Returns a function that loads a fixture JSON file.
    """

    def _load(sport: str, league: str, match_id: str, fixture_name: str) -> list[dict[str, Any]]:
        fixture_path = FIXTURES_DIR / sport / league / match_id / fixture_name

        if not fixture_path.exists():
            pytest.skip(f"Fixture not found: {fixture_path}")

        data = json.loads(fixture_path.read_text())

        # Ensure we always return a list
        if isinstance(data, dict):
            return [data]
        return data

    return _load


@pytest.fixture
def load_metadata():
    """
    Factory fixture to load match metadata.

    Returns a function that loads metadata.json for a match.
    """

    def _load(sport: str, league: str, match_id: str) -> dict[str, Any]:
        metadata_path = FIXTURES_DIR / sport / league / match_id / "metadata.json"

        if not metadata_path.exists():
            pytest.skip(f"Metadata not found: {metadata_path}")

        return json.loads(metadata_path.read_text())

    return _load


@pytest.fixture
def fixture_exists():
    """
    Factory fixture to check if a fixture exists.

    Returns a function that returns True if the fixture exists.
    """

    def _exists(sport: str, league: str, match_id: str, fixture_name: str) -> bool:
        fixture_path = FIXTURES_DIR / sport / league / match_id / fixture_name
        return fixture_path.exists()

    return _exists


@pytest.fixture
def har_for_match(request):
    """
    Returns the path to the HAR file paired with a JSON fixture, if it exists.

    Each JSON fixture has a sibling .har with the same stem (e.g. 1x2_full_time_all.har
    next to 1x2_full_time_all.json). Returns None when no HAR exists or when --live is set,
    in which case run_scraper falls through to live mode.
    """
    live_mode = request.config.getoption("--live")

    def _har(sport: str, league: str, match_id: str, fixture_name: str) -> Path | None:
        if live_mode:
            return None
        json_path = FIXTURES_DIR / sport / league / match_id / fixture_name
        har_path = json_path.with_suffix(".har")
        return har_path if har_path.exists() else None

    return _har


def get_all_fixtures() -> list[tuple[str, str, str, str]]:
    """
    Discovers all fixture files for parameterized tests.

    Returns list of (sport, league, match_id, fixture_name) tuples.
    """
    fixtures = []

    if not FIXTURES_DIR.exists():
        return fixtures

    for sport_dir in FIXTURES_DIR.iterdir():
        if not sport_dir.is_dir() or sport_dir.name.startswith("."):
            continue

        for league_dir in sport_dir.iterdir():
            if not league_dir.is_dir():
                continue

            for match_dir in league_dir.iterdir():
                if not match_dir.is_dir():
                    continue

                for fixture_file in match_dir.glob("*.json"):
                    if fixture_file.name == "metadata.json":
                        continue

                    fixtures.append((sport_dir.name, league_dir.name, match_dir.name, fixture_file.name))

    return fixtures


def pytest_addoption(parser):
    """Register --live flag to bypass HAR replay and hit the real network."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run integration tests against live OddsPortal (bypass HAR replay).",
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test (requires network)")
    config.addinivalue_line("markers", "slow: mark test as slow (>30 seconds)")
    config.addinivalue_line(
        "markers",
        "live_only: test cannot be replayed from HAR; runs only when --live is passed",
    )


def pytest_collection_modifyitems(config, items):
    """Skip live_only tests unless --live is passed."""
    if config.getoption("--live"):
        return
    skip_live_only = pytest.mark.skip(reason="live_only test, run with --live to enable")
    for item in items:
        if "live_only" in item.keywords:
            item.add_marker(skip_live_only)
