"""Pure parser for a match page's community vote data.

Community votes surface only as the "User Predictions" percentage row rendered
under the odds table of the market view currently displayed, so the input is the
match page HTML and the output carries per-outcome vote percentages for that one
market (labels from the odds table's outcome columns). Absolute counts and
all-markets-at-once coverage are gone with the pageVar (gotchas §19).
"""

from datetime import datetime
import logging
import re

from bs4 import BeautifulSoup

from oddsharvester.core.community.row_helpers import to_pct
from oddsharvester.core.listing import _parse_date_header
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.page_time import shown_to_local

logger = logging.getLogger(__name__)

_KNOWN_SCOPES = ("Full Time", "1st Half", "2nd Half")
_PCT_RE = re.compile(r"^\d+\s*%$")
# "Sunday, 04 Jan 2026, 17:30", or "Today, 04 Jan 2026, 17:30" on the day itself.
_KICKOFF_RE = re.compile(r"^[^,]+, (\d{1,2} \S+ \d{4}), ((?:[01]?\d|2[0-3]):[0-5]\d)$")
_KICKOFF_FORMAT = "%A, %d %b %Y, %H:%M"


def parse_match_community_dom(
    html: str, match_url: str, event_id: str | None = None, tz_name: str | None = None
) -> dict:
    soup = BeautifulSoup(html, "lxml")
    root = OddsPortalSelectors.content_root(soup)

    home_team, away_team = _participants(soup)
    market = _active_market(root)
    scope = _active_scope(root)
    pcts = _vote_percentages(root)
    labels = _outcome_labels(root)

    markets: list[dict] = []
    if pcts and market:
        outcomes = [{"outcome": labels[i] if i < len(labels) else None, "votes_pct": pct} for i, pct in enumerate(pcts)]
        markets.append({"market": market, "scope": scope, "outcomes": outcomes})

    return {
        "mode": "match",
        "match_url": match_url,
        "event_id": event_id,
        "home_team": home_team,
        "away_team": away_team,
        "kickoff": _kickoff(soup, tz_name),
        "is_prematch": not _has_started(soup),
        "markets": markets,
    }


def _participants(soup) -> tuple[str | None, str | None]:
    title = OddsPortalSelectors.match_title_block(soup)
    names = title.select(OddsPortalSelectors.PARTICIPANT_NAME_CSS) if title is not None else []
    if len(names) < 2:
        return None, None
    return names[0].get_text(strip=True) or None, names[-1].get_text(strip=True) or None


def _active_market(root) -> str | None:
    tab = root.select_one(OddsPortalSelectors.MARKET_TAB_ACTIVE)
    return (tab.get_text(strip=True) or None) if tab is not None else None


def _active_scope(root) -> str:
    for button in root.select(OddsPortalSelectors.SUB_NAV_TAB_ANY):
        style = (button.get("style") or "").replace(" ", "")
        if OddsPortalSelectors.SUB_NAV_ACTIVE_STYLE_MARKER.replace(" ", "") not in style:
            continue
        text = button.get_text(strip=True)
        if text in _KNOWN_SCOPES:
            return text
    return "Full Time"


def _vote_percentages(root) -> list[int]:
    """Percentages of the User Predictions row, the only all-percentage row of the view."""
    table = root.select_one(OddsPortalSelectors.ODDS_TABLE)
    block = table.parent if table is not None else root
    for row in block.find_all("div", recursive=False):
        cells = [t.strip() for t in row.stripped_strings if _PCT_RE.match(t.strip())]
        if len(cells) >= 2:
            return [to_pct(c) for c in cells]
    return []


def _outcome_labels(root) -> list[str]:
    """Outcome labels of the displayed market: the odds table's middle headers."""
    headers = [th.get_text(strip=True) for th in root.select(f"{OddsPortalSelectors.ODDS_TABLE} thead th")]
    return headers[1:-1]


def _kickoff_text(soup) -> str | None:
    cell = OddsPortalSelectors.match_date_cell(soup)
    if cell is None:
        return None
    return " ".join(p.get_text(strip=True) for p in cell.find_all("p")) or None


def _kickoff(soup, tz_name: str | None) -> str | None:
    """The header's kickoff, shown at the browser's current UTC offset, as the zone's local time (gotchas §10).

    Written back in the header's shape with the weekday first: the header says Today, Tomorrow or
    Yesterday instead around the day it is read.
    """
    text = _kickoff_text(soup)
    match = _KICKOFF_RE.match(text or "")
    shown_date = _parse_date_header(match.group(1)) if match else None
    if shown_date is None:
        if text:
            logger.debug("Kickoff %r is not 'Weekday, DD Mon YYYY, HH:MM'; kept as shown.", text)
        return text
    shown = datetime.strptime(f"{shown_date.isoformat()} {match.group(2)}", "%Y-%m-%d %H:%M")
    return shown_to_local(shown, tz_name).strftime(_KICKOFF_FORMAT)


def _has_started(soup) -> bool:
    """Started = the header carries the live pulse, or the participants show scores."""
    root = OddsPortalSelectors.content_root(soup)
    if root.select_one(OddsPortalSelectors.LIVE_INFO_MARKER) is not None:
        return True
    title = OddsPortalSelectors.match_title_block(soup)
    if title is None:
        return False
    return any(el.get_text(strip=True).isdigit() for el in title.find_all("div"))
