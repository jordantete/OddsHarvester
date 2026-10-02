from datetime import UTC, datetime
import logging
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from oddsharvester.core.market_extraction.bookmaker_name import resolve_bookmaker_name
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.page_time import local_to_shown, shown_to_local

_FRACTIONAL_RE = re.compile(r"^(\d+)/(\d+)$")
# OddsPortal abbreviates September as "Sept", which %b does not accept.
_MONTH_ABBR_RE = re.compile(r"\bSept\b")
_logger = logging.getLogger(__name__)


def parse_odds_value(text: str) -> float:
    """Parse an odds string that may be decimal (``1.80``) or fractional (``4/5``).

    Fractional odds are converted to decimal: numerator / denominator + 1.
    """
    m = _FRACTIONAL_RE.match(text)
    if m:
        decimal = int(m.group(1)) / int(m.group(2)) + 1
        _logger.debug(f"Converted fractional odds '{text}' -> {decimal:.4f}")
        return decimal
    return float(text)


def empty_history_block() -> dict[str, Any]:
    """History block for an outcome whose odds movement could not be read."""
    return {"odds_history": [], "opening_odds": None}


class OddsParser:
    """Handles parsing of odds data from HTML content."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def parse_market_odds(
        self, html_content: str, period: str, odds_labels: list, target_bookmaker: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Parses odds for a given market type in a generic way.

        Args:
            html_content (str): The HTML content of the page.
            period (str): The match period (e.g., "FullTime").
            odds_labels (list): A list of labels defining the expected odds columns (e.g., ["odds_over", "odds_under"]).
            target_bookmaker (str, optional): If set, only parse odds for this bookmaker.

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds.
        """
        self.logger.info("Parsing odds from HTML content.")
        soup = BeautifulSoup(html_content, "html.parser")

        # Odds are a real <table>, one leaf <tr> per bookmaker, identified by the
        # bookmaker links in its first cell: collapsed submarket line rows carry
        # the expand arrow instead, and the peripheral rows (My coupon, User
        # Predictions, OddsAlert) render outside the table. Non-leaf rows are
        # excluded: an expanded submarket row wraps a nested bookmaker table.
        root = OddsPortalSelectors.content_root(soup)
        bookmaker_rows = [
            tr for tr in root.select(OddsPortalSelectors.BOOKMAKER_ROW_WITH_NAME_CSS) if tr.find("tr") is None
        ]

        if not bookmaker_rows:
            self.logger.warning("No bookmaker rows found.")
            return []

        odds_data = []
        for row in bookmaker_rows:
            try:
                bookmaker_name = self._extract_bookmaker_name(row)

                if not bookmaker_name:
                    self.logger.warning("A bookmaker row has no name, no title and no link slug. Skipping...")
                    continue
                if target_bookmaker and bookmaker_name.lower() != target_bookmaker.lower():
                    continue

                odds_cells = row.select(OddsPortalSelectors.ODD_CELL_CSS)

                if len(odds_cells) < len(odds_labels):
                    self.logger.warning(f"Incomplete odds data for bookmaker: {bookmaker_name}. Skipping...")
                    continue

                extracted_odds = {label: odds_cells[i].get_text(strip=True) for i, label in enumerate(odds_labels)}

                for key, value in extracted_odds.items():
                    extracted_odds[key] = re.sub(r"(\d+\.\d+)\1", r"\1", value)

                blocked_outcomes = [
                    label
                    for i, label in enumerate(odds_labels)
                    if odds_cells[i].select_one(OddsPortalSelectors.ODDS_BLOCKED_SELECTOR)
                ]

                extracted_odds["bookmaker_name"] = bookmaker_name
                extracted_odds["period"] = period
                if blocked_outcomes:
                    extracted_odds["blocked_outcomes"] = blocked_outcomes
                odds_data.append(extracted_odds)

            except Exception as e:
                self.logger.error(f"Error parsing odds: {e}")
                continue

        self.logger.info(f"Successfully parsed odds for {len(odds_data)} bookmakers.")
        return odds_data

    def parse_odds_history_modal(
        self, modal_html: str, reference: datetime | None = None, tz_name: str | None = None
    ) -> dict[str, Any]:
        """
        Parses the HTML content of an odds history modal.

        Args:
            modal_html (str): Raw HTML from the modal.
            reference (datetime, optional): True local kickoff, naive, in the browser timezone. The modal omits the
                year: each timestamp takes the year of the kickoff as the page shows it, or the year before when its
                month comes after that kickoff's month. Without it, the current UTC year is used.
            tz_name (str, optional): The browser timezone. The modal shows every time at its UTC offset of the
                scrape moment; each timestamp comes out as the local time of that zone on its date.

        Returns:
            dict: {"odds_history": [...], "opening_odds": {...} or None}; both empty when the modal is unreadable.
        """
        self.logger.info("Parsing modal content for odds history.")

        try:
            soup = BeautifulSoup(modal_html, "html.parser")
            odds_history = []
            # Redesign: history columns are siblings inside a flex-row wrapper
            # (col 0 = timestamps, col 1 = values, col 2 = deltas).
            cols = soup.select("div.flex.flex-row.gap-3 > div.flex.flex-col.gap-1")
            timestamps = cols[0].select("div.font-normal") if cols else []
            odds_values = cols[1].select("div.font-bold") if len(cols) > 1 else []

            for ts, odd in zip(timestamps, odds_values, strict=False):
                time_text = ts.get_text(strip=True)
                try:
                    formatted_time = self._history_timestamp(time_text, reference, tz_name)
                except ValueError:
                    self.logger.warning(f"Failed to parse datetime: {time_text}")
                    continue

                odds_history.append({"timestamp": formatted_time, "odds": parse_odds_value(odd.get_text(strip=True))})

            opening_odds = None
            opening_odds_block = soup.select_one("div.mt-2.gap-1")
            opening_ts_div = opening_odds_block.select_one("div.flex.gap-1 div") if opening_odds_block else None
            opening_val_div = opening_odds_block.select_one("div.flex.gap-1 .font-bold") if opening_odds_block else None
            if opening_ts_div and opening_val_div:
                try:
                    opening_odds = {
                        "timestamp": self._history_timestamp(opening_ts_div.get_text(strip=True), reference, tz_name),
                        "odds": parse_odds_value(opening_val_div.get_text(strip=True)),
                    }
                except ValueError:
                    self.logger.warning("Failed to parse opening odds timestamp.")

            return {"odds_history": odds_history, "opening_odds": opening_odds}

        except Exception as e:
            self.logger.error(f"Failed to parse odds history modal: {e}")
            return empty_history_block()

    @staticmethod
    def _history_timestamp(
        text: str, reference: datetime | None, tz_name: str | None = None, now: datetime | None = None
    ) -> str:
        """Naive ISO local time, in the browser zone on that date, of a modal time such as '27 Dec, 18:08'."""
        # Parsed against a leap year so that 29 February is accepted before the real year is known.
        parsed = datetime.strptime(f"{_MONTH_ABBR_RE.sub('Sep', text)} 2000", "%d %b, %H:%M %Y")
        if reference is None:
            year = (now or datetime.now(UTC)).year
        else:
            # The year rule compares shown dates, so the kickoff is moved to the page's offset first.
            shown_kickoff = local_to_shown(reference, tz_name, now)
            year = shown_kickoff.year - 1 if parsed.month > shown_kickoff.month else shown_kickoff.year
        shown = datetime(year, parsed.month, parsed.day, parsed.hour, parsed.minute)
        return shown_to_local(shown, tz_name, now).isoformat()

    def _extract_bookmaker_name(self, block: Tag) -> str | None:
        """Extract the bookmaker name: the label next to the logo, else the logo link title, else its link slug."""
        name_el = block.select_one(f"{OddsPortalSelectors.BOOKMAKER_LINK_CSS} p")
        a_tag = block.find("a", attrs={"title": True})
        link = block.select_one(OddsPortalSelectors.BOOKMAKER_LINK_CSS)
        name = resolve_bookmaker_name(
            name_el.get_text(strip=True) if name_el else None,
            a_tag["title"] if a_tag else None,
            link.get("href") if link else None,
        )
        if name is None:
            self.logger.debug("Could not resolve bookmaker name from block")
        return name
