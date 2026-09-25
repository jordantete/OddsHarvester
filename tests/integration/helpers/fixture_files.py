"""Locate committed integration fixtures, failing loudly when one is missing."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def require_file(path: Path) -> Path:
    """Return path, or fail the test: a committed fixture that disappeared must not turn into a skip."""
    if not path.exists():
        pytest.fail(f"Committed fixture file missing: {path}")
    return path


def har_path_for(json_path: Path, live: bool) -> Path | None:
    """HAR paired with a JSON fixture, or None under --live. Without the HAR the run would hit the live site."""
    if live:
        return None
    return require_file(json_path.with_suffix(".har"))
