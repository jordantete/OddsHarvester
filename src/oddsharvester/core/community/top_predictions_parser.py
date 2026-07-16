"""Pure-HTML parser for the OddsPortal Community Top Predictions page.

The page (/predictions/#sport/<sport>/) renders, in document order, repeating
sections of: a sport/country/league breadcrumb, one row of outcome-label header
cells, then one game row. The backing XHR is obfuscated, so this module parses
the rendered DOM only (data-testid selectors, never localized text).
"""

import logging
import re

from bs4 import BeautifulSoup

from oddsharvester.core.base_scraper import _parse_date_header
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL

logger = logging.getLogger(__name__)

# Raw data-testid values for the document-order section scan (find_all(attrs=)),
# not CSS selectors — the CSS forms live on OddsPortalSelectors.
_SECTION_TESTIDS = ("sport-country-league-item", "betting-tip-header", "game-row")
# Team names: two separate <p class="participant-name"> per row (home, away).
_PARTICIPANT_NAME = "p.participant-name"
_PCT_RE = re.compile(r"(\d+)\s*%")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


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

    home_team, away_team = _extract_teams(row)
    kickoff_text, kickoff, market = _extract_datetime_and_market(row, tz_name)
    odds_values = [_to_float(cell.get_text(strip=True)) for cell in row.select(OddsPortalSelectors.COMMUNITY_ODD_CELL)]
    pct_values = [
        _to_pct(cell.get_text(strip=True)) for cell in row.select(OddsPortalSelectors.COMMUNITY_PREDICTION_CELL)
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


def _extract_teams(row) -> tuple[str | None, str | None]:
    # Primary: two separate participant-name elements (document order = home, away).
    names = row.select(_PARTICIPANT_NAME)
    if len(names) >= 2:
        return names[0].get_text(strip=True), names[-1].get_text(strip=True)
    # Fallback: a single dash-separated text node inside the participants container.
    participants = row.select_one(OddsPortalSelectors.COMMUNITY_PARTICIPANTS)
    if participants is None:
        return None, None
    texts = [t.strip() for t in participants.stripped_strings if t.strip() and t.strip() not in {"-", "–"}]  # noqa: RUF001
    if len(texts) >= 2:
        return texts[0], texts[-1]
    if len(texts) == 1:
        parts = re.split(r"\s[-–]\s", texts[0], maxsplit=1)  # noqa: RUF001
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return None, None


def _extract_datetime_and_market(row, tz_name: str | None) -> tuple[str, str | None, str]:
    container = row.select_one(OddsPortalSelectors.COMMUNITY_DATE_TIME)
    if container is None:
        return "", None, ""
    texts = [t.strip() for t in container.stripped_strings if t.strip()]
    market = texts[-1] if texts else ""
    time_token = next((t for t in texts if _TIME_RE.match(t)), None)
    date_tokens = [t for t in texts if t != market and t != time_token]
    kickoff_text = " ".join(texts)
    kickoff = None
    # Community rows render future dates as "19/Jul," (slash-separated, trailing
    # comma), a shape _parse_date_header (listing-page owned) doesn't accept.
    # Normalize locally to "19 Jul" before handing it off.
    date_header = " ".join(date_tokens).replace("/", " ").rstrip(",").strip()
    parsed_date = _parse_date_header(date_header, tz_name) if date_header else None
    if parsed_date and time_token:
        kickoff = f"{parsed_date.isoformat()}T{time_token.zfill(5)}"
    return kickoff_text, kickoff, market


def _to_float(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def _to_pct(text: str) -> int:
    match = _PCT_RE.search(text)
    return int(match.group(1)) if match else 0
