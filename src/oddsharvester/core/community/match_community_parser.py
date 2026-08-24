"""Pure parser for a match page's community vote data (2026-08 redesign).

The old implementation decoded `window.pageVar.predictionData.communityData`
(absolute vote counts, all markets at once). The redesigned page embeds no such
object: community votes surface only as the "User Predictions" percentage row
of the market view currently displayed. Input is therefore the hydrated match
page HTML; output carries per-outcome vote percentages for that one market
(labels from the betting-tip-header column cells). Absolute counts and
all-markets-at-once coverage are gone with the pageVar (gotchas §19).
"""

import logging
import re

from bs4 import BeautifulSoup

from oddsharvester.core.community.row_helpers import to_pct

logger = logging.getLogger(__name__)

_KNOWN_SCOPES = ("Full Time", "1st Half", "2nd Half")


def parse_match_community_dom(html: str, match_url: str, event_id: str | None = None) -> dict:
    soup = BeautifulSoup(html, "lxml")

    home_team = _participant(soup, "game-host")
    away_team = _participant(soup, "game-guest")
    market = _text(soup, "sports-nav-active-tab")
    scope = _active_scope(soup)

    up_row = soup.find(attrs={"data-testid": "user-predictions-row"})
    pcts = (
        [to_pct(c.get_text(strip=True)) for c in up_row.find_all(attrs={"data-testid": "prediction-container"})]
        if up_row
        else []
    )
    labels = [t.get_text(strip=True) for t in soup.find_all(attrs={"data-testid": "betting-tip-header"})]

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
        "kickoff": _kickoff_text(soup),
        "is_prematch": not _has_started(soup),
        "markets": markets,
    }


def _text(soup, testid: str) -> str | None:
    el = soup.find(attrs={"data-testid": testid})
    text = el.get_text(strip=True) if el else None
    return text or None


def _participant(soup, testid: str) -> str | None:
    box = soup.find(attrs={"data-testid": testid})
    if box is None:
        return None
    name = box.find(attrs={"data-testid": "participant-name"})
    text = name.get_text(strip=True) if name else box.get_text(strip=True)
    return text or None


def _active_scope(soup) -> str:
    for tab in soup.find_all(attrs={"data-testid": "sub-nav-active-tab"}):
        text = tab.get_text(strip=True)
        if text in _KNOWN_SCOPES:
            return text
    return "Full Time"


def _kickoff_text(soup) -> str | None:
    el = soup.find(attrs={"data-testid": "game-time-item"})
    if el is None:
        return None
    return " ".join(p.get_text(strip=True) for p in el.find_all("p")) or None


def _has_started(soup) -> bool:
    """Started = a live red score in the header, or a terminal live-info text."""
    live_info = soup.find(attrs={"data-testid": "live-info"})
    if live_info is not None and live_info.get_text(strip=True):
        return True
    participants = soup.find(attrs={"data-testid": "game-participants"})
    if participants is None:
        return False
    return any(el.get_text(strip=True).isdigit() for el in participants.find_all(class_=re.compile(r"text-red")))
