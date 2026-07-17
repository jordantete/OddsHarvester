"""Pure-HTML parser for the OddsPortal Community Top Predictions page.

The page (/predictions/#sport/<sport>/) renders, in document order, repeating
sections of: a sport/country/league breadcrumb, one row of outcome-label header
cells, then one game row. The backing XHR is obfuscated, so this module parses
the rendered DOM only (data-testid selectors, never localized text).
"""

import logging

from bs4 import BeautifulSoup

from oddsharvester.core.community.row_helpers import (
    extract_datetime_and_market,
    extract_teams,
    to_float,
    to_pct,
)
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL

logger = logging.getLogger(__name__)

# Raw data-testid values for the document-order section scan (find_all(attrs=)),
# not CSS selectors — the CSS forms live on OddsPortalSelectors.
_SECTION_TESTIDS = ("sport-country-league-item", "betting-tip-header", "game-row")


def parse_top_predictions(html: str, tz_name: str | None = None) -> list[dict]:
    """Parse Top Predictions rows into records. Malformed rows are skipped with a warning."""
    soup = BeautifulSoup(html, "lxml")
    records: list[dict] = []
    breadcrumb: dict | None = None
    outcome_labels: list[str] = []

    for node in soup.find_all(attrs={"data-testid": _SECTION_TESTIDS}):
        testid = node.get("data-testid")
        if testid == "sport-country-league-item":
            breadcrumb = _parse_breadcrumb(node)
            outcome_labels = []
        elif testid == "betting-tip-header":
            outcome_labels.append(node.get_text(strip=True))
        elif testid == "game-row":
            record = _parse_game_row(node, breadcrumb, outcome_labels, tz_name)
            if record is not None:
                records.append(record)
    return records


def _parse_breadcrumb(node) -> dict | None:
    country = node.select_one(OddsPortalSelectors.COMMUNITY_BREADCRUMB_COUNTRY)
    league = node.select_one(OddsPortalSelectors.COMMUNITY_BREADCRUMB_LEAGUE)
    if country is None or league is None:
        return None
    return {"country": country.get_text(strip=True), "league": league.get_text(strip=True)}


def _parse_game_row(row, breadcrumb: dict | None, outcome_labels: list[str], tz_name: str | None) -> dict | None:
    link = row.find("a", href=True)
    if link is None or breadcrumb is None or not outcome_labels:
        logger.warning("Skipping top-predictions row: missing link, breadcrumb or outcome headers")
        return None

    home_team, away_team = extract_teams(row)
    kickoff_text, kickoff, market = extract_datetime_and_market(row, tz_name)
    odds_values = [to_float(cell.get_text(strip=True)) for cell in row.select(OddsPortalSelectors.COMMUNITY_ODD_CELL)]
    pct_values = [
        to_pct(cell.get_text(strip=True)) for cell in row.select(OddsPortalSelectors.COMMUNITY_PREDICTION_CELL)
    ]

    if (
        not home_team
        or not away_team
        or len(odds_values) != len(outcome_labels)
        or len(pct_values) != len(outcome_labels)
    ):
        logger.warning("Skipping top-predictions row for %s: cell/label count mismatch", link["href"])
        return None

    return {
        "country": breadcrumb["country"],
        "league": breadcrumb["league"],
        "home_team": home_team,
        "away_team": away_team,
        "kickoff": kickoff,
        "kickoff_text": kickoff_text,
        "market": market,
        "odds": [{"outcome": o, "odds": v} for o, v in zip(outcome_labels, odds_values, strict=True)],
        "community_votes_pct": [{"outcome": o, "pct": p} for o, p in zip(outcome_labels, pct_values, strict=True)],
        "match_url": ODDSPORTAL_BASE_URL + link["href"] if link["href"].startswith("/") else link["href"],
    }
