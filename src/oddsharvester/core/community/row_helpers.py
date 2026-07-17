"""Shared leaf parsers for community DOM rows (top predictions + user profiles).

These helpers are pure: they take a BeautifulSoup node (or text) and return
primitives, so they are reused across the community parsers without pulling in
Playwright. Selectors live on OddsPortalSelectors; date normalization mirrors
the slash+comma community date shape (gotchas §13).
"""

import re

from oddsharvester.core.base_scraper import _parse_date_header
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors

_PCT_RE = re.compile(r"(\d+)\s*%")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def to_float(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def to_pct(text: str) -> int:
    match = _PCT_RE.search(text)
    return int(match.group(1)) if match else 0


def extract_teams(row) -> tuple[str | None, str | None]:
    # Primary: two participant-name elements (document order = home, away).
    names = row.select(OddsPortalSelectors.COMMUNITY_PARTICIPANT_NAME)
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


def extract_datetime_and_market(row, tz_name: str | None) -> tuple[str, str | None, str]:
    container = row.select_one(OddsPortalSelectors.COMMUNITY_DATE_TIME)
    if container is None:
        return "", None, ""
    texts = [t.strip() for t in container.stripped_strings if t.strip()]
    market = texts[-1] if texts else ""
    time_token = next((t for t in texts if _TIME_RE.match(t)), None)
    date_tokens = [t for t in texts if t != market and t != time_token]
    kickoff_text = " ".join(texts)
    kickoff = None
    # Community rows render future dates as "19/Jul," (slash-separated, trailing comma),
    # a shape _parse_date_header does not accept. Normalize locally to "19 Jul" (gotchas §13).
    date_header = " ".join(date_tokens).replace("/", " ").rstrip(",").strip()
    parsed_date = _parse_date_header(date_header, tz_name) if date_header else None
    if parsed_date and time_token:
        kickoff = f"{parsed_date.isoformat()}T{time_token.zfill(5)}"
    return kickoff_text, kickoff, market
