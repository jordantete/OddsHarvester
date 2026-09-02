"""Pure-HTML parser for the OddsPortal Community Top Predictions page.

The page (/community/predictions/#sport/<sport>/) renders, in document order,
repeating sections of: a sport/country/league breadcrumb, then one or more game
rows. Each row links to its match and carries one column per outcome (label,
odds, community percentage). The backing XHR is obfuscated, so this module
parses the rendered DOM only, keying on structure rather than localized text.
"""

import logging

from bs4 import BeautifulSoup

from oddsharvester.core.community.row_helpers import (
    extract_datetime_and_market,
    extract_teams,
    outcome_columns,
    row_of,
)
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL

logger = logging.getLogger(__name__)

# Breadcrumb links by path depth: /<sport>/ , /<sport>/<country>/ , /<sport>/<country>/<league>/
_BREADCRUMB_DEPTHS = {"country": 2, "league": 3}


def parse_top_predictions(html: str, tz_name: str | None = None) -> list[dict]:
    """Parse Top Predictions rows into records. Malformed rows are skipped with a warning."""
    soup = BeautifulSoup(html, "lxml")
    root = OddsPortalSelectors.content_root(soup)

    records: list[dict] = []
    for link in root.select(OddsPortalSelectors.LISTING_ROW_SELECTOR):
        row = row_of(link)
        if row is None:
            continue
        record = _parse_game_row(row, link, _parse_breadcrumb(row), tz_name)
        if record is not None:
            records.append(record)
    return records


def _parse_breadcrumb(row) -> dict | None:
    """Country and league of the row's section, read off the breadcrumb link depths."""
    node = row.parent
    for _ in range(4):
        if node is None:
            break
        found = {}
        for anchor in node.find_all("a", href=True):
            depth = len(anchor["href"].strip("/").split("/"))
            for name, expected in _BREADCRUMB_DEPTHS.items():
                if depth == expected and name not in found:
                    found[name] = anchor.get_text(strip=True)
        if len(found) == len(_BREADCRUMB_DEPTHS):
            return found
        node = node.parent
    return None


def _parse_game_row(row, link, breadcrumb: dict | None, tz_name: str | None) -> dict | None:
    columns = outcome_columns(row)
    if breadcrumb is None or not columns:
        logger.warning("Skipping top-predictions row: missing breadcrumb or outcome columns")
        return None

    home_team, away_team = extract_teams(link)
    kickoff_text, kickoff, market = extract_datetime_and_market(link, tz_name)

    if not home_team or not away_team:
        logger.warning("Skipping top-predictions row for %s: participants not found", link["href"])
        return None

    return {
        "country": breadcrumb["country"],
        "league": breadcrumb["league"],
        "home_team": home_team,
        "away_team": away_team,
        "kickoff": kickoff,
        "kickoff_text": kickoff_text,
        "market": market,
        "odds": [{"outcome": c["outcome"], "odds": c["odds"]} for c in columns],
        "community_votes_pct": [{"outcome": c["outcome"], "pct": c["pct"]} for c in columns],
        "match_url": ODDSPORTAL_BASE_URL + link["href"] if link["href"].startswith("/") else link["href"],
    }
