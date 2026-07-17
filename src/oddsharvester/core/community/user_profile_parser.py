"""Pure parser for an OddsPortal user profile page (/profile/<username>/).

Header (username, ROI, member-since, country, privacy) renders even when the
profile is private; the monthly statistics table and the predictions list render
only for public profiles. Prediction rows reuse the community row selectors but,
unlike top predictions, carry NO betting-tip-header — so outcomes are positional
(odds + community % + which one the user picked), with no 1/X/2 labels. The
picked outcome is located by document order: it is the outcome index equal to the
number of odd cells seen before the prediction-pick-item marker.
"""

import logging
import re

from bs4 import BeautifulSoup

from oddsharvester.core.base_scraper import _parse_date_header
from oddsharvester.core.community.row_helpers import extract_datetime_and_market, extract_teams, to_float, to_pct
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL

logger = logging.getLogger(__name__)

_ROI_RE = re.compile(r"(-?[\d.]+)\s*%")
_MEMBER_SINCE_RE = re.compile(r"Member since:\s*(.+?)\s*(?:Country:|Profile Privacy:|$)")
_COUNTRY_RE = re.compile(r"Country:\s*(.+?)\s*(?:Profile Privacy:|$)")
_PRIVACY_RE = re.compile(r"Profile Privacy:\s*(Public|Private)", re.IGNORECASE)
_SCORE_RE = re.compile(r"\d+\s*[-–]\s*\d+")  # noqa: RUF001


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
    el = soup.select_one(OddsPortalSelectors.COMMUNITY_PROFILE_MEMBER_INFO)
    return el.get_text(" ", strip=True) if el else ""


def _privacy(soup) -> str:
    match = _PRIVACY_RE.search(_member_info_text(soup))
    return match.group(1).lower() if match else "public"


def _roi(soup) -> float | None:
    el = soup.select_one(OddsPortalSelectors.COMMUNITY_PROFILE_ROI)
    if el is None:
        return None
    match = _ROI_RE.search(el.get_text(" ", strip=True))
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
    header = soup.select_one(OddsPortalSelectors.COMMUNITY_PROFILE_STATS_HEADER)
    if header is None or header.parent is None:
        return []
    rows: list[dict] = []
    for sibling in header.find_next_siblings():
        cells = [c.get_text(strip=True) for c in sibling.find_all(recursive=False)]
        if len(cells) < 6:
            continue
        rows.append(
            {
                "month": cells[0],
                "total_predictions": _to_int(cells[1]),
                "won": to_float(cells[2]),
                "lost": _to_int(cells[3]),
                "plus_minus": to_float(cells[4]),
                "roi_pct": _pct_float(cells[5]),
            }
        )
    return rows


def _parse_predictions(soup, tz_name: str | None) -> list[dict]:
    predictions: list[dict] = []
    for row in soup.select(OddsPortalSelectors.COMMUNITY_GAME_ROW):
        record = _parse_prediction_row(row, tz_name)
        if record is not None:
            predictions.append(record)
    return predictions


def _parse_prediction_row(row, tz_name: str | None) -> dict | None:
    link = row.find("a", href=True)
    home_team, away_team = extract_teams(row)
    if home_team is None or away_team is None:
        logger.warning("Skipping profile prediction row: missing participants")
        return None
    kickoff_text, kickoff, market = extract_datetime_and_market(row, tz_name)
    odds_cells = row.select(OddsPortalSelectors.COMMUNITY_ODD_CELL)
    pct_cells = row.select(OddsPortalSelectors.COMMUNITY_PREDICTION_CELL)
    picked_index = _picked_index(row)
    outcomes = [
        {
            "odds": to_float(odds_cells[i].get_text(strip=True)),
            "community_pct": to_pct(pct_cells[i].get_text(strip=True)) if i < len(pct_cells) else 0,
            "picked": i == picked_index,
        }
        for i in range(len(odds_cells))
    ]
    pick_odds = outcomes[picked_index]["odds"] if picked_index is not None and picked_index < len(outcomes) else None
    return {
        "kickoff": kickoff,
        "kickoff_text": kickoff_text,
        "market": market,
        "home_team": home_team,
        "away_team": away_team,
        "score": _score(row),
        "pick_odds": pick_odds,
        "outcomes": outcomes,
        "match_url": (ODDSPORTAL_BASE_URL + link["href"])
        if link and link["href"].startswith("/")
        else (link["href"] if link else None),
    }


def _picked_index(row) -> int | None:
    """Index of the picked outcome = number of odd cells before the pick marker (document order)."""
    idx = -1
    picked = None
    for el in row.descendants:
        get = getattr(el, "get", None)
        if get is None:
            continue
        testid = el.get("data-testid")
        if testid == "odd-container-default":
            idx += 1
        elif testid == "prediction-pick-item":
            picked = idx
    return picked if picked is not None and picked >= 0 else None


def _score(row) -> str | None:
    participants = row.select_one(OddsPortalSelectors.COMMUNITY_PARTICIPANTS)
    if participants is None:
        return None
    match = _SCORE_RE.search(participants.get_text(" ", strip=True))
    return match.group(0).replace("–", "-") if match else None  # noqa: RUF001


def _to_int(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def _pct_float(text: str) -> float | None:
    match = _ROI_RE.search(text)
    return float(match.group(1)) if match else None
