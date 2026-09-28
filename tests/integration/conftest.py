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


def pytest_addoption(parser):
    """Register --live flag to bypass HAR replay and hit the real network."""
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run integration tests against live OddsPortal (bypass HAR replay).",
    )


def pytest_collection_modifyitems(config, items):
    """Skip live_only tests unless --live is passed."""
    if config.getoption("--live"):
        return
    skip_live_only = pytest.mark.skip(reason="live_only test, run with --live to enable")
    for item in items:
        if "live_only" in item.keywords:
            item.add_marker(skip_live_only)
