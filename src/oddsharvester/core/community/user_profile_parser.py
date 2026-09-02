"""Pure parser for an OddsPortal user profile page (/profile/<username>/).

Header (username, ROI, member-since, country, privacy) renders even when the
profile is private; the monthly statistics table and the predictions list render
only for public profiles. Prediction rows reuse the community row structure and
add a pick marker on the outcome column the user bet on.
"""

import logging
import re

from bs4 import BeautifulSoup

from oddsharvester.core.base_scraper import _parse_date_header
from oddsharvester.core.community.row_helpers import (
    extract_datetime_and_market,
    extract_teams,
    outcome_columns,
    row_of,
    to_float,
)
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL

logger = logging.getLogger(__name__)

_ROI_RE = re.compile(r"(-?[\d.]+)\s*%")
_PROFILE_ROI_RE = re.compile(r"ROI\s*(-?[\d.]+)\s*%")
_MEMBER_SINCE_RE = re.compile(r"Member since:\s*(.+?)\s*(?:Country:|Profile Privacy:|$)")
_COUNTRY_RE = re.compile(r"Country:\s*(.+?)\s*(?:Profile Privacy:|$)")
_PRIVACY_RE = re.compile(r"Profile Privacy:\s*(Public|Private)", re.IGNORECASE)


def parse_user_profile(html: str, tz_name: str | None = None) -> dict:
    soup = BeautifulSoup(html, "lxml")
    privacy = _privacy(soup)
    record = {
        "mode": "user",
        "username": _text(soup, OddsPortalSelectors.COMMUNITY_PROFILE_USERNAME),
        "roi_pct": _roi(soup),
        "member_since": _member_since(soup, tz_name),
        "country": _country(soup),
        "privacy": privacy,
        "statistics": [],
        "predictions": [],
    }
    if privacy == "private":
        return record
    record["statistics"] = _parse_statistics(soup)
    record["predictions"] = _parse_predictions(soup, tz_name)
    return record


def _text(soup, selector: str) -> str | None:
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else None


def _member_info_text(soup) -> str:
    """Header text carrying the member-since / country / privacy labels."""
    return OddsPortalSelectors.content_root(soup).get_text(" ", strip=True)


def _privacy(soup) -> str:
    match = _PRIVACY_RE.search(_member_info_text(soup))
    return match.group(1).lower() if match else "public"


def _roi(soup) -> float | None:
    match = _PROFILE_ROI_RE.search(_member_info_text(soup))
    return float(match.group(1)) if match else None


def _member_since(soup, tz_name: str | None) -> str | None:
    match = _MEMBER_SINCE_RE.search(_member_info_text(soup))
    if not match:
        return None
    parsed = _parse_date_header(match.group(1).strip(), tz_name)
    return parsed.isoformat() if parsed else match.group(1).strip()


def _country(soup) -> str | None:
    match = _COUNTRY_RE.search(_member_info_text(soup))
    return match.group(1).strip() if match else None


def _parse_statistics(soup) -> list[dict]:
    # The monthly statistics are the profile page's only table.
    table = soup.select_one(OddsPortalSelectors.COMMUNITY_PROFILE_STATS_TABLE)
    if table is None:
        return []
    rows: list[dict] = []
    for sibling in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in sibling.find_all("td")]
        if len(cells) < 6:
            continue
        rows.append(
            {
                "month": cells[0],
                "total_predictions": _to_int(cells[1]),
                "won": to_float(cells[2]),
                "lost": to_float(cells[3]),
                "plus_minus": to_float(cells[4]),
                "roi_pct": _pct_float(cells[5]),
            }
        )
    return rows


def parse_profile_feed_predictions(html: str, tz_name: str | None = None) -> list[dict]:
    """Parse prediction rows from the profile's Feed tab HTML.

    The predictions list lives under the Feed tab (clicked by the scraper) and
    reuses the community row structure, so this reuses the same row parser.
    """
    return _parse_predictions(BeautifulSoup(html, "lxml"), tz_name)


def _parse_predictions(soup, tz_name: str | None) -> list[dict]:
    root = OddsPortalSelectors.content_root(soup)
    predictions: list[dict] = []
    for link in root.select(OddsPortalSelectors.LISTING_ROW_SELECTOR):
        row = row_of(link)
        if row is None:
            continue
        record = _parse_prediction_row(row, link, tz_name)
        if record is not None:
            predictions.append(record)
    return predictions


def _parse_prediction_row(row, link, tz_name: str | None) -> dict | None:
    home_team, away_team = extract_teams(link)
    if home_team is None or away_team is None:
        logger.warning("Skipping profile prediction row: missing participants")
        return None
    kickoff_text, kickoff, market = extract_datetime_and_market(link, tz_name)
    outcomes = [
        {"odds": column["odds"], "community_pct": column["pct"], "picked": column["picked"]}
        for column in outcome_columns(row)
    ]
    pick_odds = next((o["odds"] for o in outcomes if o["picked"]), None)
    return {
        "kickoff": kickoff,
        "kickoff_text": kickoff_text,
        "market": market,
        "home_team": home_team,
        "away_team": away_team,
        "score": _score(link),
        "pick_odds": pick_odds,
        "outcomes": outcomes,
        "match_url": (ODDSPORTAL_BASE_URL + link["href"]) if link["href"].startswith("/") else link["href"],
    }


def _score(link) -> str | None:
    """Final score of a played match: the bold digits flanking the participants."""
    digits = [
        el.get_text(strip=True) for el in link.find_all("span", class_="font-bold") if el.get_text(strip=True).isdigit()
    ]
    return f"{digits[0]}-{digits[-1]}" if len(digits) >= 2 else None


def _to_int(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def _pct_float(text: str) -> float | None:
    match = _ROI_RE.search(text)
    return float(match.group(1)) if match else None
