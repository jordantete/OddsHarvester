"""Match page parsing: the header's date, teams, league, scores and live state, and the JSON-LD venue."""

from datetime import UTC, datetime
import json
import logging
import re
from typing import Any
import unicodedata

from bs4 import BeautifulSoup

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.datetime_format import format_utc
from oddsharvester.utils.local_kickoff import compute_local_kickoff
from oddsharvester.utils.page_time import shown_to_utc, timezone_or_utc

# Separator is a colon on the live header, but OddsPortal renders scores with an
# en-dash (U+2013) elsewhere; accept both rather than silently dropping the score.
_LIVE_MAIN_SCORE_RE = re.compile(r"^(\d+)\s*[:\u2013-]\s*(\d+)$")


# A match that ended either loses its live-info container or keeps it with a terminal
# state in place of the period marker (gotchas §16). "Final result" verified live
# 2026-07-20; the rest mirror the listing-page states in docs/agentic-gotchas.md §9.
_LIVE_ENDED_PERIOD_MARKERS = frozenset(
    {
        "final result",
        "finished",
        "postponed",
        "canceled",
        "cancelled",
        "abandoned",
        "retired",
        "walkover",
    }
)


_LIVE_PARTIAL_RESULT_RE = re.compile(r"^\(.+\)$")


def _parse_live_info(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Parse the in-play match header into live context fields.

    The live block sits in the header's date row, marked by the `result-live`
    pulse: a period chunk, a main-score chunk, and an optional partial result in
    parentheses. Match on text shape, not classes.

    Returns None when the match is not live, which covers two cases: the block
    is absent, or it carries a terminal marker such as "Final result".
    """
    marker = OddsPortalSelectors.content_root(soup).select_one(OddsPortalSelectors.LIVE_INFO_MARKER)
    container = marker.parent if marker is not None else None
    if container is None:
        return None

    partial_text = None
    partial_el = next(
        (el for el in container.find_all("div") if _LIVE_PARTIAL_RESULT_RE.match(el.get_text("", strip=True))), None
    )
    if partial_el is not None:
        partial_text = partial_el.get_text("", strip=True).strip("()") or None
        partial_el.extract()

    period = None
    score_raw = None
    score_home = None
    score_away = None
    for raw_chunk in container.stripped_strings:
        # OddsPortal separates words with non-breaking spaces in these chunks.
        chunk = raw_chunk.replace("\u00a0", " ").strip()
        match = _LIVE_MAIN_SCORE_RE.match(chunk)
        if match and score_raw is None:
            score_raw = chunk
            score_home, score_away = int(match.group(1)), int(match.group(2))
        elif period is None and not match:
            period = chunk

    # Prefix match: the redesigned page can serve the terminal text as a single
    # chunk ("Final result 1:2 (0:1, 1:1)"), not a standalone marker element.
    if period and any(period.casefold().startswith(marker) for marker in _LIVE_ENDED_PERIOD_MARKERS):
        return None

    live_score_raw = score_raw
    if score_raw and partial_text:
        live_score_raw = f"{score_raw} ({partial_text})"

    return {
        "live_period": period,
        "live_score_home": score_home,
        "live_score_away": score_away,
        "live_score_raw": live_score_raw,
    }


def _history_reference(match_date: str | None, tz_name: str | None) -> datetime | None:
    """True local kickoff, naive, in the browser timezone; `_history_timestamp` moves it to the page's offset."""
    if not match_date:
        return None
    try:
        kickoff = datetime.strptime(match_date, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=UTC)
    except ValueError:
        return None
    tz = timezone_or_utc(tz_name)
    return kickoff.astimezone(tz).replace(tzinfo=None)


def _normalize_month_name(value: str) -> str:
    """Normalize a browser-rendered month label for locale-independent matching."""
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()

    # Intl short month forms commonly carry trailing punctuation (for example
    # a locale-specific abbreviation marker). The visible site may omit it.
    while normalized and (normalized[-1].isspace() or unicodedata.category(normalized[-1]).startswith("P")):
        normalized = normalized[:-1]

    return normalized


def _parse_match_date_from_dom(
    soup: BeautifulSoup, tz_name: str | None, month_names: dict[str, int], logger: logging.Logger
) -> str | None:
    """
    Extract the match date from the header's date cell and return it
    formatted as "YYYY-MM-DD HH:MM:SS UTC".

    Returns None if the cell or its child paragraphs are missing, or if
    the text doesn't match the expected "DD MMM YYYY" + "HH:MM" shape.
    """
    try:
        game_time_div = OddsPortalSelectors.match_date_cell(soup)
        if not game_time_div:
            return None

        paragraphs = game_time_div.find_all("p")
        if len(paragraphs) < 3:
            return None

        date_part = paragraphs[1].get_text(strip=True).rstrip(",")
        time_part = paragraphs[2].get_text(strip=True)
        try:
            local_dt = datetime.strptime(
                f"{date_part} {time_part}",
                "%d %b %Y %H:%M",
            )
        except ValueError as original_error:
            date_parts = date_part.split()

            if len(date_parts) != 3:
                raise original_error

            day_str, month_token, year_str = date_parts
            normalized_month = _normalize_month_name(month_token)

            browser_aliases = month_names or {}

            matching_months = {
                month_num
                for alias, month_num in browser_aliases.items()
                if isinstance(alias, str)
                and isinstance(month_num, int)
                and not isinstance(month_num, bool)
                and 1 <= month_num <= 12
                and _normalize_month_name(alias) == normalized_month
            }

            if len(matching_months) != 1:
                raise ValueError(
                    f"Unrecognized or ambiguous browser-localized month token: {month_token!r}"
                ) from original_error

            month_num = matching_months.pop()

            local_dt = datetime.strptime(
                f"{day_str} {month_num:02d} {year_str} {time_part}",
                "%d %m %Y %H:%M",
            )

        return format_utc(shown_to_utc(local_dt, tz_name))
    except Exception as e:
        logger.warning(f"DOM parse failed for match_date: {e}")
        return None


def _parse_teams_from_dom(soup: BeautifulSoup, logger: logging.Logger) -> tuple[str | None, str | None]:
    """
    Extract (home_team, away_team) from the header's participants row: its
    first and last blocks, each naming its side in a link (team page) or a
    paragraph (sports with no team pages, e.g. tennis). Returns (None, None)
    if either side is missing.
    """

    def _name(container):
        if container is None:
            return None
        el = container.find(["a", "p"])
        text = el.get_text(strip=True) if el else None
        return text or None

    try:
        title = OddsPortalSelectors.match_title_block(soup)
        if title is None:
            return None, None
        sides = title.find_all("div", recursive=False)
        host_name = _name(sides[0]) if sides else None
        guest_name = _name(sides[-1]) if len(sides) > 1 else None
        if not host_name or not guest_name:
            return None, None
        return host_name, guest_name
    except Exception as e:
        logger.warning(f"DOM parse failed for teams: {e}")
        return None, None


_SEASON_SUFFIX_RE = re.compile(r"\s+\d{4}/\d{4}$")


def _parse_league_from_dom(soup: BeautifulSoup, logger: logging.Logger) -> str | None:
    """
    Extract the league name from the breadcrumb navigation, stripping
    the trailing season suffix when present (e.g. "Premier League 2024/2025"
    -> "Premier League"). Returns None if the breadcrumb or league link is
    missing.
    """
    try:
        breadcrumbs = OddsPortalSelectors.content_root(soup).find("ul")
        if not breadcrumbs:
            return None
        # The breadcrumb is Home > Sport > Country > League > <match>; only the
        # trail is linked, so the league is its last anchor.
        links = breadcrumbs.find_all("a", href=True)
        if not links:
            return None
        raw = links[-1].get_text(strip=True)
        return _SEASON_SUFFIX_RE.sub("", raw) or None
    except Exception as e:
        logger.warning(f"DOM parse failed for league_name: {e}")
        return None


_RESULT_TEXT_RE = re.compile(r"(\d+)\s*:\s*(\d+)(?:\s*\(([\d:,\s ]+)\))?")


def _parse_results_from_dom(soup: BeautifulSoup, logger: logging.Logger) -> tuple[str | None, str | None, str | None]:
    """
    Extract (home_score, away_score, partial_results) from the page DOM.

    Scoped to the header's date row (the date cell's parent) to avoid false
    positives elsewhere in the page. Returns (None, None, None) if the score
    pattern isn't found.
    """
    try:
        game_time_div = OddsPortalSelectors.match_date_cell(soup)
        if not game_time_div:
            return None, None, None
        scope = game_time_div.find_parent() or soup
        excluded = {id(game_time_div), *(id(d) for d in game_time_div.find_all("div"))}
        for div in scope.find_all("div"):
            if id(div) in excluded:
                continue
            text = div.get_text(separator=" ", strip=True)
            m = _RESULT_TEXT_RE.search(text)
            if m:
                home, away, partial = m.group(1), m.group(2), m.group(3)
                formatted_partial = (
                    f"({re.sub(r' +', ' ', partial.replace(chr(0xA0), ' ')).strip()})" if partial else None
                )
                return home, away, formatted_partial
        return None, None, None
    except Exception as e:
        logger.warning(f"DOM parse failed for results: {e}")
        return None, None, None


def _parse_venue_from_ld_json(
    soup: BeautifulSoup, dom_match_date: str | None, logger: logging.Logger
) -> tuple[str | None, str | None, str | None]:
    """Venue trio from the SSR JSON-LD SportsEvent, staleness-guarded.

    The SSR JSON-LD describes the *next upcoming* meeting of the two teams
    (gotchas §1b), so it is trusted only when its startDate calendar date
    equals the DOM-extracted match date. Returns (venue, town, country),
    all None when absent or stale.
    """
    if not dom_match_date:
        return None, None, None
    try:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
            except (TypeError, json.JSONDecodeError):
                continue
            types = data.get("@type") or []
            if isinstance(types, str):
                types = [types]
            if "SportsEvent" not in types:
                continue
            try:
                ld_date = datetime.fromisoformat(data.get("startDate") or "").astimezone(UTC).date()
            except ValueError:
                continue
            if ld_date.isoformat() != dom_match_date[:10]:
                return None, None, None
            location = data.get("location") or {}
            address = location.get("address") or {}
            if not isinstance(address, dict):
                address = {}
            country = address.get("addressCountry")
            if isinstance(country, dict):
                country = country.get("name")
            return location.get("name") or None, address.get("addressLocality") or None, country or None
    except Exception as e:
        logger.debug(f"JSON-LD venue parse failed: {e}")
    return None, None, None


def _parse_match_details(
    html_content: str,
    match_link: str,
    tz_name: str | None,
    month_names: dict[str, int],
    local_kickoff: bool,
    logger: logging.Logger,
) -> dict[str, Any] | None:
    """
    Extract match details (date, teams, league, scores, venue) from the
    hydrated match page DOM.

    The redesigned page embeds no per-match JSON: content renders only after
    the SPA fetches the fragment match (see `_hydrate_match_view`), so the
    DOM *is* the requested match. Venue comes from the SSR JSON-LD only when
    it describes the same match.

    Returns None when the DOM lacks the minimum landmarks to identify the
    match (no kickoff and no team pair). Other errors propagate: `BaseScraper._extract_match_details` logs them.
    """
    soup = BeautifulSoup(html_content, "html.parser")

    match_date = _parse_match_date_from_dom(soup, tz_name, month_names, logger)
    home_team, away_team = _parse_teams_from_dom(soup, logger)
    league_name = _parse_league_from_dom(soup, logger)
    home_score_raw, away_score_raw, partial_results = _parse_results_from_dom(soup, logger)

    if match_date is None and (home_team is None or away_team is None):
        logger.warning(f"No match landmarks found for {match_link} - page may be unavailable or structure changed")
        return None

    venue, venue_town, venue_country = _parse_venue_from_ld_json(soup, match_date, logger)

    details = {
        "scraped_date": format_utc(datetime.now(UTC)),
        "match_date": match_date,
        "season": None,
        "match_link": match_link,
        "home_team": home_team,
        "away_team": away_team,
        "league_name": league_name,
        "home_score": str(home_score_raw) if home_score_raw is not None else None,
        "away_score": str(away_score_raw) if away_score_raw is not None else None,
        "partial_results": partial_results,
        "venue": venue.encode("ascii", "ignore").decode("ascii") if venue else None,
        "venue_town": venue_town.encode("ascii", "ignore").decode("ascii") if venue_town else None,
        "venue_country": venue_country,
        "match_info": None,
    }

    if local_kickoff:
        venue_timezone, match_date_venue_local = compute_local_kickoff(
            match_date_utc=details["match_date"],
            country=details["venue_country"],
            town=details["venue_town"],
        )
        details["venue_timezone"] = venue_timezone
        details["match_date_venue_local"] = match_date_venue_local

        if venue_timezone is None and details["venue_country"]:
            logger.debug(
                f"Unresolved venue timezone for country={details['venue_country']!r} "
                f"town={details['venue_town']!r}; match_date_venue_local left null"
            )

    return details
