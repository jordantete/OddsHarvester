"""Comparison utilities for integration testing."""

from collections import Counter
import json
import re
from typing import Any

MARKET_SUFFIX = "_market"
IGNORED_FIELDS = frozenset({"scraped_date"})
_YEAR = re.compile(r"^\d{4}-")


class ComparisonResult:
    """Result of a fixture comparison."""

    def __init__(self):
        self.passed = True
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def add_error(self, message: str):
        """Add an error (causes test failure)."""
        self.passed = False
        self.errors.append(message)

    def add_warning(self, message: str):
        """Add a warning (logged but doesn't fail test)."""
        self.warnings.append(message)

    def __bool__(self):
        return self.passed

    def __str__(self):
        if self.passed:
            msg = "PASSED"
            if self.warnings:
                msg += f" (warnings: {len(self.warnings)})"
            return msg
        return f"FAILED: {len(self.errors)} error(s)\n" + "\n".join(f"  - {e}" for e in self.errors)


def compare_match_data(actual: dict[str, Any], expected: dict[str, Any]) -> ComparisonResult:
    """
    Compare a scraped match against its fixture.

    Every field must be equal except scraped_date. Market lists are compared entry by entry,
    keyed by (bookmaker_name, period, submarket_name), with odds compared as exact strings.
    """
    result = ComparisonResult()
    for key in sorted((actual.keys() | expected.keys()) - IGNORED_FIELDS):
        if key not in actual:
            result.add_error(f"'{key}' missing from actual")
        elif key not in expected:
            result.add_error(f"'{key}' not in fixture")
        elif key.endswith(MARKET_SUFFIX):
            for error in compare_market(key, actual[key], expected[key]).errors:
                result.add_error(error)
        elif actual[key] != expected[key]:
            result.add_error(f"Field '{key}' mismatch: actual={actual[key]!r} vs expected={expected[key]!r}")
    return result


def compare_market(market: str, actual: list[dict[str, Any]], expected: list[dict[str, Any]]) -> ComparisonResult:
    """Compare the bookmaker entries of one market."""
    result = ComparisonResult()
    actual_by_key = _index_entries(market, actual, "actual", result)
    expected_by_key = _index_entries(market, expected, "fixture", result)
    for key in sorted(actual_by_key.keys() | expected_by_key.keys(), key=repr):
        if key not in actual_by_key:
            result.add_error(f"{market}: entry {key} missing from actual")
        elif key not in expected_by_key:
            result.add_error(f"{market}: entry {key} not in fixture")
        else:
            actual_entry = _mask_history_years(actual_by_key[key])
            expected_entry = _mask_history_years(expected_by_key[key])
            if actual_entry != expected_entry:
                result.add_error(
                    f"{market}: entry {key} differs: actual={actual_entry!r} vs expected={expected_entry!r}"
                )
    return result


def _entry_key(entry: dict[str, Any]) -> tuple[Any, Any, Any]:
    return (entry.get("bookmaker_name"), entry.get("period"), entry.get("submarket_name"))


def _index_entries(
    market: str, entries: list[dict[str, Any]], side: str, result: ComparisonResult
) -> dict[tuple[Any, Any, Any], dict[str, Any]]:
    for key, count in Counter(_entry_key(entry) for entry in entries).items():
        if count > 1:
            result.add_error(f"{market}: entry {key} appears {count} times in {side}")
    return {_entry_key(entry): entry for entry in entries}


def _mask_history_years(entry: dict[str, Any]) -> dict[str, Any]:
    # The history parser stamps the run's year on every timestamp, so it varies with the replay date.
    blocks = entry.get("odds_history_data")
    if not blocks:
        return entry
    return {**entry, "odds_history_data": [_mask_block(block) for block in blocks]}


def _mask_block(block: Any) -> Any:
    if not isinstance(block, dict):
        return block
    masked = dict(block)
    if isinstance(block.get("odds_history"), list):
        masked["odds_history"] = [_mask_point(point) for point in block["odds_history"]]
    if isinstance(block.get("opening_odds"), dict):
        masked["opening_odds"] = _mask_point(block["opening_odds"])
    return masked


def _mask_point(point: Any) -> Any:
    if isinstance(point, dict) and isinstance(point.get("timestamp"), str):
        return {**point, "timestamp": _YEAR.sub("YYYY-", point["timestamp"])}
    return point


def compare_json_files(actual_path: str, expected_path: str) -> ComparisonResult:
    """Compare two JSON files containing match data."""
    with open(actual_path) as f:
        actual_data = json.load(f)

    with open(expected_path) as f:
        expected_data = json.load(f)

    # Handle both single match and list of matches
    if isinstance(actual_data, dict):
        actual_data = [actual_data]
    if isinstance(expected_data, dict):
        expected_data = [expected_data]

    result = ComparisonResult()

    if len(actual_data) != len(expected_data):
        result.add_error(f"Match count mismatch: actual={len(actual_data)}, expected={len(expected_data)}")
        return result

    # Compare each match
    for i, (actual_match, expected_match) in enumerate(zip(actual_data, expected_data, strict=False)):
        match_result = compare_match_data(actual_match, expected_match)
        if not match_result.passed:
            result.add_error(f"Match {i} comparison failed:")
            for error in match_result.errors:
                result.add_error(f"  {error}")
        result.warnings.extend(match_result.warnings)

    return result
