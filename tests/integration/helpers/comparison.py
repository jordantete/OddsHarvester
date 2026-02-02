"""Comparison utilities for integration testing."""

import json
from typing import Any


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


def compare_match_data(
    actual: dict[str, Any],
    expected: dict[str, Any],
    strict_odds: bool = False,
    odds_tolerance: float = 0.02,
) -> ComparisonResult:
    """
    Compare actual scraped data against expected fixture.

    Args:
        actual: The scraped match data
        expected: The expected data from fixture
        strict_odds: If True, odds must match exactly; if False, allows tolerance
        odds_tolerance: Tolerance for odds comparison (default 0.02 = 2 cents)

    Returns:
        ComparisonResult with pass/fail status and details
    """
    result = ComparisonResult()

    # 1. Compare fixed fields (exact match required)
    fixed_fields = ["home_team", "away_team", "sport"]
    for field in fixed_fields:
        actual_val = actual.get(field)
        expected_val = expected.get(field)
        if actual_val != expected_val:
            result.add_error(f"Field '{field}' mismatch: actual='{actual_val}' vs expected='{expected_val}'")

    # 2. Compare scores (may be in different formats)
    for score_field in ["home_score", "away_score"]:
        actual_score = str(actual.get(score_field, "")).strip()
        expected_score = str(expected.get(score_field, "")).strip()
        if actual_score and expected_score and actual_score != expected_score:
            result.add_error(f"Field '{score_field}' mismatch: actual='{actual_score}' vs expected='{expected_score}'")

    # 3. Compare league (partial match allowed - formatting may vary)
    actual_league = actual.get("league", "").lower()
    expected_league = expected.get("league", "").lower()
    if (
        actual_league
        and expected_league
        and expected_league not in actual_league
        and actual_league not in expected_league
    ):
        result.add_warning(f"League mismatch: '{actual.get('league')}' vs '{expected.get('league')}'")

    # 4. Compare URL if present
    actual_url = actual.get("url", "")
    expected_url = expected.get("url", "")
    if actual_url and expected_url:
        # Compare just the match ID part (last segment)
        actual_id = actual_url.rstrip("/").split("/")[-1]
        expected_id = expected_url.rstrip("/").split("/")[-1]
        if actual_id != expected_id:
            result.add_error(f"URL mismatch: {actual_url} vs {expected_url}")

    # 5. Compare odds structure
    actual_odds = actual.get("odds", {})
    expected_odds = expected.get("odds", {})

    if expected_odds:
        odds_result = compare_odds(actual_odds, expected_odds, strict_odds, odds_tolerance)
        result.errors.extend(odds_result.errors)
        result.warnings.extend(odds_result.warnings)
        if not odds_result.passed:
            result.passed = False

    return result


def compare_odds(
    actual: dict[str, Any],
    expected: dict[str, Any],
    strict: bool,
    tolerance: float,
) -> ComparisonResult:
    """Compare odds data between actual and expected."""
    result = ComparisonResult()

    if not expected:
        return result

    # Check that all expected markets exist in actual
    for market_name, market_data in expected.items():
        if market_name not in actual:
            result.add_error(f"Missing market in actual: '{market_name}'")
            continue

        actual_market = actual[market_name]

        if not isinstance(market_data, dict):
            continue

        # Compare submarkets
        for submarket_name, submarket_data in market_data.items():
            if not isinstance(submarket_data, dict):
                continue

            if submarket_name not in actual_market:
                result.add_warning(f"Missing submarket '{submarket_name}' in market '{market_name}'")
                continue

            actual_submarket = actual_market[submarket_name]

            # Compare bookmakers
            for bookmaker, odds_data in submarket_data.items():
                if not isinstance(odds_data, dict):
                    continue

                if bookmaker not in actual_submarket:
                    # Bookmakers can disappear from OddsPortal - warning only
                    result.add_warning(f"Bookmaker '{bookmaker}' not found in actual data")
                    continue

                actual_bookie = actual_submarket[bookmaker]

                # Compare closing odds if present
                if "closing_odds" in odds_data and "closing_odds" in actual_bookie:
                    expected_closing = odds_data["closing_odds"]
                    actual_closing = actual_bookie["closing_odds"]

                    if not _compare_odds_values(actual_closing, expected_closing, strict, tolerance):
                        result.add_error(
                            f"Closing odds mismatch for {bookmaker} in {market_name}/{submarket_name}: "
                            f"actual={actual_closing} vs expected={expected_closing}"
                        )

    return result


def _compare_odds_values(
    actual: list[str] | str,
    expected: list[str] | str,
    strict: bool,
    tolerance: float,
) -> bool:
    """Compare two odds values or lists of odds values."""
    # Normalize to lists
    if isinstance(actual, str):
        actual = [actual]
    if isinstance(expected, str):
        expected = [expected]

    if len(actual) != len(expected):
        return False

    for a, e in zip(actual, expected, strict=False):
        try:
            actual_val = float(a)
            expected_val = float(e)

            if strict:
                if actual_val != expected_val:
                    return False
            else:
                if abs(actual_val - expected_val) > tolerance:
                    return False
        except (ValueError, TypeError):
            # Non-numeric odds (e.g., "-") - compare as strings
            if str(a).strip() != str(e).strip():
                return False

    return True


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
