"""Fixtures for integration tests."""

import json
from pathlib import Path
import tempfile
from typing import Any

import pytest

from tests.integration.helpers.cli_runner import run_historic
from tests.integration.helpers.fixture_files import FIXTURES_DIR, har_path_for, require_file


@pytest.fixture
def temp_output_dir():
    """Provides a temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def run_scraper():
    """Factory fixture returning run_historic, which runs the CLI and returns (exit_code, stdout, stderr)."""
    return run_historic


@pytest.fixture
def load_fixture():
    """
    Factory fixture to load expected fixtures.

    Returns a function that loads a fixture JSON file.
    """

    def _load(sport: str, league: str, match_id: str, fixture_name: str) -> list[dict[str, Any]]:
        fixture_path = require_file(FIXTURES_DIR / sport / league / match_id / fixture_name)
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
        metadata_path = require_file(FIXTURES_DIR / sport / league / match_id / "metadata.json")
        return json.loads(metadata_path.read_text())

    return _load


@pytest.fixture
def fixture_exists():
    """
    Factory fixture that fails the test when a committed fixture is missing.

    Returns True otherwise, so the existing `if not fixture_exists(...)` guards keep working.
    """

    def _exists(sport: str, league: str, match_id: str, fixture_name: str) -> bool:
        require_file(FIXTURES_DIR / sport / league / match_id / fixture_name)
        return True

    return _exists


@pytest.fixture
def har_for_match(request):
    """
    Returns the HAR paired with a JSON fixture (same stem, .har suffix).

    Returns None under --live. Fails the test when the HAR is missing, instead of letting the
    run fall through to the live site.
    """
    live_mode = request.config.getoption("--live")

    def _har(sport: str, league: str, match_id: str, fixture_name: str) -> Path | None:
        return har_path_for(FIXTURES_DIR / sport / league / match_id / fixture_name, live_mode)

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
