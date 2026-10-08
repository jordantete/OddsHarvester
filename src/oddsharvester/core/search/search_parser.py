"""Pure parser for OddsPortal's search pages.

Search pages ship their data in the Next flight payload under a ``searchData``
key, as team pages do (gotchas §21). The rendered rows also hold the anti-bot
trap row of §28, which the payload never carries, so nothing is read from the
DOM (gotchas §29).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
import html as html_lib
import json
import re

from oddsharvester.core.exceptions import PageNotFoundError, ParsingError
from oddsharvester.core.url_builder import rebase_url, sport_from_site_slug
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL
from oddsharvester.utils.datetime_format import format_utc

_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("[^"\\]*(?:\\.[^"\\]*)*")\]\)')
_DATA_KEY = '"searchData":'
_NAME_KEY = '"searchStringUrl":'
_TAG_RE = re.compile(r"<[^>]+>")
_TEAM_ID_RE = re.compile(r"/team/[^/]+/([A-Za-z0-9]{8})/")
_DECODER = json.JSONDecoder()


@dataclass(frozen=True)
class MatchPage:
    """One page of a team's search tab."""

    rows: list[dict]
    total: int
    page_count: int


def parse_candidates(html: str, url: str, base_url: str | None = None) -> list[dict]:
    """The teams a name search returns, most relevant first.

    Raises:
        ParsingError: The page carries no searchData payload.
    """
    data, _rest = _payload(html, url)
    participants = data.get("participants") or {}
    # An empty collection arrives as a JSON list, a filled one as an object keyed by participant id.
    entries = participants.values() if isinstance(participants, dict) else participants
    ranked = sorted(entries, key=lambda entry: entry.get("score") or 0, reverse=True)
    return [
        {
            "team_id": entry.get("encoded-id"),
            "name": _plain(entry.get("name")),
            "country": entry.get("country-name"),
            "sport": sport_from_site_slug(entry.get("sport-url-name")),
            "team_url": _absolute(entry.get("participant-url"), base_url),
        }
        for entry in ranked
    ]


def parse_matches(html: str, url: str, team_id: str, tab: str, base_url: str | None = None) -> MatchPage:
    """One page of a team's matches, from its upcoming (``next``) or its ``results`` tab.

    Raises:
        PageNotFoundError: The site does not know ``team_id``: the page names no team.
        ParsingError: The page carries no searchData payload.
    """
    data, rest = _payload(html, url)
    if _team_name(rest) == "":
        raise PageNotFoundError(f"Team id {team_id} does not exist on OddsPortal: its search page names no team.", url)
    pagination = data.get("pagination")
    page_count = pagination.get("pageCount") if isinstance(pagination, dict) else None
    return MatchPage(
        rows=[_match_row(row, tab, base_url) for row in data.get("rows") or []],
        total=data.get("total") or 0,
        page_count=page_count or 1,
    )


def _payload(html: str, url: str) -> tuple[dict, str]:
    """The searchData object, and the rest of its chunk, where the page's other props follow it."""
    for match in _PUSH_RE.finditer(html):
        try:
            chunk = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        start = chunk.find(_DATA_KEY)
        if start == -1:
            continue
        try:
            data, end = _DECODER.raw_decode(chunk, start + len(_DATA_KEY))
        except json.JSONDecodeError as e:
            raise ParsingError(f"Search payload is not valid JSON: {e}", url) from e
        if isinstance(data, dict):
            return data, chunk[end:]
    raise ParsingError("Search page carries no searchData payload", url)


def _team_name(rest: str) -> str | None:
    """None when the key is gone, so a renamed prop never turns every team into an unknown one."""
    start = rest.find(_NAME_KEY)
    if start == -1:
        return None
    value, _ = _DECODER.raw_decode(rest, start + len(_NAME_KEY))
    return value


def _match_row(row: dict, tab: str, base_url: str | None) -> dict:
    tournament = (row.get("breadcrumbs") or {}).get("tournament") or {}
    return {
        "match_link": _absolute(row.get("url"), base_url),
        "kickoff_utc": _kickoff(row.get("date-start-timestamp")),
        "tab": tab,
        "home_team": row.get("home-name"),
        "home_team_id": _team_id(row.get("homeParticipantUrl")),
        "away_team": row.get("away-name"),
        "away_team_id": _team_id(row.get("awayParticipantUrl")),
        "home_score": _score(row.get("homeResult")),
        "away_score": _score(row.get("awayResult")),
        "tournament": row.get("tournament-name"),
        "league_url": _absolute(tournament.get("url"), base_url),
        "country": row.get("country-name"),
        "sport": sport_from_site_slug(row.get("sport-url-name")),
    }


def _kickoff(timestamp) -> str | None:
    return format_utc(datetime.fromtimestamp(int(timestamp), UTC)) if timestamp else None


def _score(value) -> str | None:
    return None if value in (None, "") else str(value)


def _team_id(participant_url: str | None) -> str | None:
    match = _TEAM_ID_RE.search(participant_url or "")
    return match.group(1) if match else None


def _plain(text: str | None) -> str | None:
    """Drop the <strong> the site wraps the matched part in, and its &nbsp; spaces."""
    if text is None:
        return None
    return html_lib.unescape(_TAG_RE.sub("", text)).replace("\xa0", " ").strip()


def _absolute(path: str | None, base_url: str | None) -> str | None:
    return rebase_url(f"{ODDSPORTAL_BASE_URL}{path}", base_url) if path else None
