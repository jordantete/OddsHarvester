"""Comparison utilities for integration testing."""

from collections import Counter
from typing import Any

MARKET_SUFFIX = "_market"
IGNORED_FIELDS = frozenset({"scraped_date"})
VALUE_WIDTH = 120
_MISSING = "<missing>"


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
        elif key.endswith(MARKET_SUFFIX) and isinstance(actual[key], list) and isinstance(expected[key], list):
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
        elif actual_by_key[key] != expected_by_key[key]:
            result.add_error(_entry_difference(market, key, actual_by_key[key], expected_by_key[key]))
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


def _entry_difference(market: str, key: tuple[Any, Any, Any], actual: dict[str, Any], expected: dict[str, Any]) -> str:
    """One line naming the differing fields, each with actual/expected windowed around their first difference."""
    union = actual.keys() | expected.keys()
    fields = sorted((f for f in union if actual.get(f, _MISSING) != expected.get(f, _MISSING)), key=str)
    details = "; ".join(
        f"{f!r}: actual={a} vs expected={e}"
        for f in fields
        for a, e in (_clip_pair(actual.get(f, _MISSING), expected.get(f, _MISSING)),)
    )
    return f"{market}: entry {key} differs in {fields}; {details}"


def _clip_pair(actual_value: Any, expected_value: Any) -> tuple[str, str]:
    """Cut each repr to VALUE_WIDTH, windowed around where the two reprs first diverge.

    A cut starting from the string's own start (like the old flat clip) can leave both sides
    showing the same unchanged prefix, hiding a difference that sits past the cut.
    """
    actual_text, expected_text = repr(actual_value), repr(expected_value)
    if len(actual_text) <= VALUE_WIDTH and len(expected_text) <= VALUE_WIDTH:
        return actual_text, expected_text
    diff_at = _first_diff_index(actual_text, expected_text)
    start = max(0, diff_at - 20)
    return _window(actual_text, start), _window(expected_text, start)


def _first_diff_index(a: str, b: str) -> int:
    for i, (ca, cb) in enumerate(zip(a, b, strict=False)):
        if ca != cb:
            return i
    return min(len(a), len(b))


def _window(text: str, start: int) -> str:
    if len(text) <= VALUE_WIDTH:
        return text
    end = start + VALUE_WIDTH
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix
