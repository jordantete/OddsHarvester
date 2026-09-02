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
    # Primary: the two participant labels (document order = home, away).
    names = row.select(OddsPortalSelectors.PARTICIPANT_NAME_CSS)
    if len(names) >= 2:
        return names[0].get_text(strip=True), names[-1].get_text(strip=True)
    # Fallback: a single dash-separated text node.
    texts = [t.strip() for t in row.stripped_strings if t.strip() and t.strip() not in {"-", "–"}]  # noqa: RUF001
    if len(texts) == 1:
        parts = re.split(r"\s[-–]\s", texts[0], maxsplit=1)  # noqa: RUF001
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return None, None


def outcome_columns(row) -> list[dict]:
    """Per-outcome columns of a community row: label, odds and community percentage.

    A column is a block holding a header label, an odds value and a percentage;
    rows without all three (e.g. the section header) yield an empty list.
    """
    columns = []
    for label in row.select(OddsPortalSelectors.COMMUNITY_OUTCOME_LABEL):
        column = label.parent
        odds = column.select_one(OddsPortalSelectors.COMMUNITY_ODD_CELL) if column else None
        pct = next((t for t in column.stripped_strings if _PCT_RE.fullmatch(t.strip())), None)
        if odds is None or pct is None:
            continue
        columns.append(
            {
                "outcome": label.get_text(strip=True),
                "odds": to_float(odds.get_text(strip=True)),
                "pct": to_pct(pct),
                "picked": column.select_one(OddsPortalSelectors.COMMUNITY_PICK_MARKER) is not None,
            }
        )
    return columns


def row_of(link):
    """The row block of a community match link: the ancestor holding the outcome columns."""
    node = link.parent
    for _ in range(6):
        if node is None:
            return None
        if outcome_columns(node):
            return node
        node = node.parent
    return None


def extract_datetime_and_market(row, tz_name: str | None) -> tuple[str, str | None, str]:
    container = _date_time_cell(row)
    if container is None:
        return "", None, ""
    texts = [t.strip() for t in container.stripped_strings if t.strip()]
    market = texts[-1] if texts else ""
    time_token = next((t for t in texts if _TIME_RE.match(t)), None)
    kickoff_text = " ".join(texts)
    kickoff = None
    # Community rows render dates as "19/Jul," (slash-separated, trailing comma),
    # a shape _parse_date_header does not accept — and since the 2026-08 redesign
    # the date renders twice (mobile + desktop variants), so only the first
    # date-looking token is used. Normalize locally to "19 Jul" (gotchas §13).
    date_token = next((t for t in texts if t != market and t != time_token), None)
    date_header = (date_token or "").replace("/", " ").rstrip(",").strip()
    parsed_date = _parse_date_header(date_header, tz_name) if date_header else None
    if parsed_date and time_token:
        kickoff = f"{parsed_date.isoformat()}T{time_token.zfill(5)}"
    return kickoff_text, kickoff, market


def _date_time_cell(row):
    """The row's date / time / market cell: the first block of stacked paragraphs."""
    for div in row.find_all("div"):
        if len(div.find_all("p", recursive=False)) >= 2:
            return div
    return None
