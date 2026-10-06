"""Listing page parsing: date headers, a row's status and kickoff, and the row steps the listing walks share."""

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
import logging
import re
import unicodedata

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.url_builder import site_slug
from oddsharvester.utils.page_time import shown_to_utc, timezone_or_utc

_MONTH_ABBREV_TO_NUM = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _normalize_month_name(value: str) -> str:
    """Normalize a browser-rendered month label for locale-independent matching."""
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()

    # Intl short month forms commonly carry trailing punctuation (for example
    # a locale-specific abbreviation marker). The visible site may omit it.
    while normalized and (normalized[-1].isspace() or unicodedata.category(normalized[-1]).startswith("P")):
        normalized = normalized[:-1]

    return normalized


def _parse_date_header(header_text: str, tz_name: str | None = None) -> date | None:
    """
    Parse an OddsPortal date-header string into a date object.

    Handles the formats observed on oddsportal.com listing pages:
        - "Today, 14 Apr"          -> today in the reference timezone
        - "Tomorrow, 15 Apr"       -> tomorrow in the reference timezone
        - "Yesterday, 13 Apr"      -> yesterday in the reference timezone
        - "18 Apr 2026"            -> explicit date
        - "Today, 14 Apr  - Apertura" -> tournament suffix is stripped

    When "Today"/"Tomorrow" is present it is trusted over the day/month tokens,
    since OddsPortal resolves them based on the browser timezone.

    Args:
        header_text: Raw text of the listing's date-header element.
        tz_name: IANA timezone name used to resolve "Today"/"Tomorrow" and to
            infer missing years. Defaults to UTC.

    Returns:
        A date object, or None if the input cannot be parsed (fail-safe: callers
        should treat None as "do not filter").
    """
    if not header_text:
        return None

    text = header_text.strip()
    if " - " in text:
        text = text.split(" - ", 1)[0].strip()

    tz = timezone_or_utc(tz_name)

    now_date = datetime.now(tz).date()

    lower = text.lower()
    if lower.startswith("today"):
        return now_date
    if lower.startswith("tomorrow"):
        return now_date + timedelta(days=1)
    if lower.startswith("yesterday"):
        return now_date - timedelta(days=1)

    parts = text.split()

    if len(parts) == 3:
        day_str, month_str, year_str = parts
        try:
            day = int(day_str)
            month = _MONTH_ABBREV_TO_NUM.get(month_str[:3].lower())
            year = int(year_str)
            if month is None:
                return None
            return date(year, month, day)
        except (ValueError, TypeError):
            return None

    if len(parts) == 2:
        day_str, month_str = parts
        try:
            day = int(day_str)
            month = _MONTH_ABBREV_TO_NUM.get(month_str[:3].lower())
            if month is None:
                return None
            candidate = date(now_date.year, month, day)
            if (now_date - candidate).days > 180:
                candidate = date(now_date.year + 1, month, day)
            return candidate
        except (ValueError, TypeError):
            return None

    return None


_KICKOFF_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def _row_status_cell_text(row) -> str:
    """Text of a listing row's first column: kickoff time, or a status/period marker.

    A row is the match <a>, whose two direct <div> children are the
    kickoff/status cell and the participants (gotchas §20).
    """
    cell = row.find("div", recursive=False)
    return cell.get_text(" ", strip=True) if cell else ""


def _row_has_started(row) -> bool:
    """Return True if a listing-page event row is live or finished.

    The first column shows HH:MM while the match is pending and a status or
    period marker once it starts ("Finished", "5S"). See
    `docs/agentic-gotchas.md` §9. Fail-safe: no marker → False so DOM drift
    degrades open.
    """
    text = _row_status_cell_text(row)
    if not text:
        return False
    return not _KICKOFF_TIME_RE.match(text)


def _row_kickoff_datetime(row, row_date: date | None, tz_name: str | None) -> datetime | None:
    """Best-effort kickoff datetime, aware in UTC, for a listing-page event row.

    Combines the group's `row_date` (from the surrounding date-header) with the
    HH:MM shown in the row's first column. Returns None when the kickoff cannot
    be determined (no date, or a non-clock value such as a live period marker),
    so callers keep the row (fail-safe against DOM drift).

    Args:
        row: A BeautifulSoup event-row node.
        row_date: The date of the row's group, or None if unknown.
        tz_name: The browser timezone; the row's time is read at its UTC offset
            of the scrape moment (see `docs/agentic-gotchas.md` §10).
    """
    if row_date is None:
        return None
    text = _row_status_cell_text(row)
    if not text or not _KICKOFF_TIME_RE.match(text):
        return None
    hour_str, minute_str = text.split(":")
    try:
        kickoff_time = time(int(hour_str), int(minute_str))
    except ValueError:
        return None
    return shown_to_utc(datetime.combine(row_date, kickoff_time), tz_name)


def _is_league_link(el) -> bool:
    """True for a section-header league link ('/<sport>/<country>/<league>/')."""
    href = el.get("href") or ""
    return "?" not in href and "/h2h/" not in href and len(href.strip("/").split("/")) == 3


async def _listing_elements(page: Page, keep: Callable[[Tag], bool]) -> list[Tag]:
    """The elements of the page's content root that `keep` accepts, in document order.

    Scoped to the content root so sidebar widgets never register as rows or headers.
    """
    soup = BeautifulSoup(await page.content(), "lxml")
    return [el for el in OddsPortalSelectors.content_root(soup).find_all(True) if keep(el)]


class _ListingRows:
    """The row steps both listing walks share, with a counter for each kind of row they drop."""

    def __init__(self, sport: str | None, base_url: str) -> None:
        self.sport = sport
        self.sport_prefix = f"/{site_slug(sport)}/" if sport else None
        self.base_url = base_url
        self.hidden = 0
        self.visible = 0
        self.foreign = 0
        self.short = 0
        self._kept: set[str] = set()

    def href(self, row: Tag) -> str | None:
        """The row's href, or None for a hidden copy of a row or a row under another sport's path."""
        if OddsPortalSelectors.is_hidden(row):
            self.hidden += 1
            return None
        self.visible += 1
        href = row["href"]
        if self.sport_prefix and not href.startswith(self.sport_prefix):
            self.foreign += 1
            return None
        return href

    def link(self, href: str) -> str | None:
        """The match URL of a row the walk keeps, or None for an href too short to be a match or a link already kept."""
        if len(href.strip("/").split("/")) <= 3:
            self.short += 1
            return None
        url = f"{self.base_url}{href}"
        if url in self._kept:
            return None
        self._kept.add(url)
        return url

    def counts(self) -> str:
        """The drop counters of the walk's log line."""
        foreign = f", {self.foreign} rows of another sport dropped" if self.sport_prefix else ""
        return f"{self.hidden} offscreen rows skipped, {self.short} short links dropped{foreign}"

    def warn_if_all_hidden(self, logger: logging.Logger, listing: str, url: str) -> None:
        """Warn when the page had rows and hid every one: the trap hides one row, never all of them."""
        if self.hidden and not self.visible:
            logger.warning(
                f"All {self.hidden} rows of this {listing} ({url}) are hidden: a hiding style on the page itself "
                "would read as an empty listing (gotchas §28)."
            )

    def warn_if_all_foreign(self, logger: logging.Logger, listing: str) -> None:
        """Warn when every visible row links under another sport: the page lists none of the requested sport."""
        if self.sport_prefix and self.visible and self.foreign == self.visible:
            logger.warning(
                f"None of the {self.visible} rows of this {listing} links under {self.sport_prefix}: "
                f"it lists no '{self.sport}' match."
            )
