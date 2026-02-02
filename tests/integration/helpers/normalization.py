"""Normalization utilities for consistent comparison."""

import re
from typing import Any


def normalize_team_name(name: str) -> str:
    """
    Normalize team name for comparison.

    Removes common suffixes/prefixes and normalizes whitespace.
    """
    if not name:
        return ""

    # Remove common suffixes/prefixes
    name = name.strip()
    name = re.sub(r"\s+(FC|CF|SC|AC|AS|US|SS|RC|CD|SD|CA|Club|United|City)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^(FC|CF|SC|AC|AS|US|SS|RC|CD|SD|CA)\s+", "", name, flags=re.IGNORECASE)

    # Normalize whitespace
    name = " ".join(name.split())

    return name.lower()


def normalize_score(score: str | int | None) -> str:
    """Normalize score to string format."""
    if score is None:
        return ""
    return str(score).strip()


def normalize_odds_value(odds: str | float | None) -> str:
    """Normalize odds value to 2 decimal places."""
    if odds is None or odds == "-" or odds == "":
        return "-"

    try:
        value = float(odds)
        return f"{value:.2f}"
    except (ValueError, TypeError):
        return str(odds)


def normalize_match_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize match data for consistent comparison.

    Returns a new dict with normalized values.
    """
    normalized = data.copy()

    # Normalize team names
    if "home_team" in normalized:
        normalized["home_team_normalized"] = normalize_team_name(normalized["home_team"])
    if "away_team" in normalized:
        normalized["away_team_normalized"] = normalize_team_name(normalized["away_team"])

    # Normalize scores
    if "home_score" in normalized:
        normalized["home_score"] = normalize_score(normalized["home_score"])
    if "away_score" in normalized:
        normalized["away_score"] = normalize_score(normalized["away_score"])

    # Normalize odds
    if "odds" in normalized:
        normalized["odds"] = normalize_odds_structure(normalized["odds"])

    return normalized


def normalize_odds_structure(odds: dict[str, Any]) -> dict[str, Any]:
    """Recursively normalize odds values in the odds structure."""
    if not isinstance(odds, dict):
        return odds

    normalized = {}
    for key, value in odds.items():
        if isinstance(value, dict):
            normalized[key] = normalize_odds_structure(value)
        elif isinstance(value, list):
            normalized[key] = [normalize_odds_value(v) for v in value]
        elif key in ("opening_odds", "closing_odds"):
            normalized[key] = normalize_odds_value(value)
        else:
            normalized[key] = value

    return normalized


def normalize_url(url: str) -> str:
    """Normalize URL by removing trailing slashes and query params."""
    if not url:
        return ""

    # Remove trailing slash
    url = url.rstrip("/")

    # Remove query parameters
    if "?" in url:
        url = url.split("?")[0]

    return url


def extract_match_id(url: str) -> str:
    """Extract match ID from OddsPortal URL."""
    if not url:
        return ""

    # URL format: .../team1-team2-MATCHID or .../team1-team2-MATCHID/
    path = url.rstrip("/").split("/")[-1]

    # Match ID is typically the last part after the last hyphen
    # But team names can also have hyphens, so we look for the pattern
    parts = path.rsplit("-", 1)
    if len(parts) == 2 and len(parts[1]) >= 6:  # Match IDs are typically 8+ chars
        return parts[1]

    return path
