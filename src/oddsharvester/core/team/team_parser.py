"""Pure parser for an OddsPortal team page.

The page ships its data in the Next flight payload rather than in the rendered
DOM, so the parser anchors on the ``basicInfo`` key instead of on classes or
attributes, which the 2026-09 redesign moves around (gotchas §20). Identity
(name, full name, logo) still comes from the header, because the payload does
not carry it.
"""

import json
import logging
import re
import unicodedata
from urllib.parse import unquote

from bs4 import BeautifulSoup

from oddsharvester.core.exceptions import ParsingError
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.url_builder import rebase_url
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL

logger = logging.getLogger(__name__)

_PAYLOAD_KEY = '"basicInfo"'
_LOGO_RE = re.compile(r"/proxy/serve/images/team-logo/[^\"'\s\\]+?\.(?:png|jpe?g|svg|webp)")
_FORM_EVENT_TEXT_RE = re.compile(r"\(([^()]+?)\s+-\s+([^()]+?)\)")
_H2H_SIDE_RE = re.compile(r"/([a-z]+)/h2h/([^/]+)/([^/]+)/")
_LEAGUE_HREF_RE = re.compile(r"^/[a-z-]+/[a-z0-9-]+/[a-z0-9-]+/$")


def parse_team_page(html: str, team_id: str, team_url: str, base_url: str | None = None) -> dict:
    """Build one team record from a team page.

    Args:
        html (str): The team page HTML.
        team_id (str): The OddsPortal team id the page was requested with.
        team_url (str): The URL the page was requested with, kept when no
            canonical slug can be recovered.
        base_url (str | None): Regional domain the run scrapes, for absolute URLs.

    Raises:
        ParsingError: The page carries no team payload, which is what a wrong
            team id returns. Its heading and breadcrumb are built from the URL
            slug, so it cannot be told apart from a real team by its text alone.
    """
    flat = html.replace('\\"', '"')
    payload = _team_payload(flat, team_url)
    basic_info = payload.get("basicInfo") or {}
    performance = payload.get("lastPerformance") or {}
    form_events = performance.get("formEvents") or []

    soup = BeautifulSoup(html, "lxml")
    sport, slug = _sport_and_slug(form_events, team_id)

    return {
        "team_id": team_id,
        "name": _breadcrumb_name(soup),
        "full_name": _full_name(soup),
        "list_name": _list_name(form_events, team_id),
        "sport": sport,
        "country": basic_info.get("venueCountry"),
        "town": basic_info.get("venueTown"),
        "venue": basic_info.get("venue"),
        "coach": basic_info.get("coach"),
        "tournament": _tournament(soup),
        "logo_url": _logo_url(soup, base_url),
        "form": ",".join(performance.get("form") or []) or None,
        "over_2_5_pct": _to_number(performance.get("scoredOverPercent")),
        "btts_pct": _to_number(performance.get("scoredBtsPercent")),
        "avg_goals_scored": _to_number(performance.get("avgGoalsScored")),
        "avg_goals_conceded": _to_number(performance.get("avgGoalsConceded")),
        "team_url": _canonical_url(sport, slug, team_id, base_url) or team_url,
    }


def _team_payload(flat: str, team_url: str) -> dict:
    start = flat.find(_PAYLOAD_KEY)
    if start == -1:
        raise ParsingError("Team page carries no data payload (wrong team id?)", team_url)

    opening = flat.rfind("{", 0, start)
    depth = 0
    for index in range(opening, len(flat)):
        if flat[index] == "{":
            depth += 1
        elif flat[index] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(flat[opening : index + 1])
                except json.JSONDecodeError as e:
                    raise ParsingError(f"Team payload is not valid JSON: {e}", team_url) from e

    raise ParsingError("Team payload is truncated", team_url)


def _breadcrumb_name(soup) -> str | None:
    """The breadcrumb's last item.

    The nav menus share the breadcrumb's markup down to a trailing item with no
    link, so it is found by position instead: it is the list that sits closest
    above the page heading.
    """
    heading = soup.find("h1")
    if heading is None:
        return None

    for unordered_list in heading.find_all_previous("ul"):
        items = unordered_list.find_all("li", recursive=False)
        if items:
            return items[-1].get_text(strip=True) or None
    return None


def _header_logo(soup):
    return soup.select_one('img[alt][width="47"]')


def _full_name(soup) -> str | None:
    logo = _header_logo(soup)
    return logo.get("alt") if logo is not None else None


def _list_name(form_events: list[dict], team_id: str) -> str | None:
    """Read the team's list-form name out of each form entry, by elimination.

    The tooltip names the pair in home-away order while the URL does not, so the
    side an id sits on says nothing about the side its name sits on. What the id
    does give is the opponent's slug, and the name that is not the opponent's is
    the team's own.
    """
    names: list[str] = []
    for event in form_events:
        pair = _FORM_EVENT_TEXT_RE.search(event.get("text") or "")
        sides = _H2H_SIDE_RE.search(event.get("url") or "")
        if pair is None or sides is None:
            continue

        opponent = _opponent_slug(sides, team_id)
        first, second = pair.group(1).strip(), pair.group(2).strip()
        if opponent is None or _slugify(first) == _slugify(second):
            continue

        if _slugify(first) == opponent:
            names.append(second)
        elif _slugify(second) == opponent:
            names.append(first)

    return max(set(names), key=names.count) if names else None


def _opponent_slug(sides, team_id: str) -> str | None:
    first, second = sides.group(2), sides.group(3)
    if first.endswith(f"-{team_id}"):
        return second.rsplit("-", 1)[0]
    if second.endswith(f"-{team_id}"):
        return first.rsplit("-", 1)[0]
    return None


def _slugify(name: str) -> str:
    ascii_only = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")


def _sport_and_slug(form_events: list[dict], team_id: str) -> tuple[str | None, str | None]:
    for event in form_events:
        sides = _H2H_SIDE_RE.search(event.get("url") or "")
        if sides is None:
            continue
        for side in (sides.group(2), sides.group(3)):
            if side.endswith(f"-{team_id}"):
                return sides.group(1), side[: -len(team_id) - 1]
    return None, None


def _canonical_url(sport: str | None, slug: str | None, team_id: str, base_url: str | None) -> str | None:
    if not sport or not slug:
        return None
    return rebase_url(f"{ODDSPORTAL_BASE_URL}/{sport}/team/{slug}/{team_id}/", base_url)


def _tournament(soup) -> str | None:
    """Best effort: the league only shows on fixture rows, which an IP whose
    selected bookmakers price nothing renders empty."""
    for anchor in OddsPortalSelectors.content_root(soup).select("a[href]"):
        # The sidebar's league links share this href shape but carry a match count.
        if _LEAGUE_HREF_RE.match(anchor.get("href") or "") and not anchor.find("span"):
            return anchor.get_text(strip=True) or None
    return None


def _logo_url(soup, base_url: str | None) -> str | None:
    """The header logo, read off the header image rather than off the document.

    Fixture rows carry their own teams' logos, so the first team-logo path in the
    page is usually an opponent's. The header image points at it URL-encoded,
    behind the image proxy, with a global asset stamp that changes over time.
    """
    logo = _header_logo(soup)
    if logo is None:
        return None

    source = unquote(logo.get("srcset") or logo.get("src") or "")
    match = _LOGO_RE.search(source)
    return rebase_url(f"{ODDSPORTAL_BASE_URL}{match.group(0)}", base_url) if match else None


def _to_number(value) -> float | None:
    if value is None:
        return None
    text = str(value).strip().rstrip("%").strip()
    try:
        return float(text)
    except ValueError:
        return None
