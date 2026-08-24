from datetime import UTC, datetime
import logging
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors

_FRACTIONAL_RE = re.compile(r"^(\d+)/(\d+)$")
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

        # 2026-08 redesign: odds are a real <table>, one leaf <tr> per bookmaker.
        # Per-bookmaker cells carry data-testid='odd-container' (or the -winning
        # variant); collapsed submarket line rows carry '-default' cells and must
        # not be parsed as bookmakers. Non-leaf rows (an expanded submarket row
        # wraps a nested table), Betting Exchanges rows (Back/Lay prices, not
        # fixed odds) and peripheral rows (My coupon, User Predictions,
        # OddsAlert) are excluded.
        odd_cell_re = re.compile(rf"^{OddsPortalSelectors.ODD_CELL_TESTID_PREFIX}(-winning)?$")
        bookmaker_rows = []
        for tr in soup.find_all("tr"):
            if tr.find("tr") is not None:
                continue
            if not tr.find(attrs={"data-testid": odd_cell_re}):
                continue
            if tr.find_parent(attrs={"data-testid": "betting-exchanges-section"}):
                continue
            if tr.find(attrs={"data-testid": list(OddsPortalSelectors.TABLE_SKIP_ROW_TESTIDS)}):
                continue
            bookmaker_rows.append(tr)

        if not bookmaker_rows:
            self.logger.warning("No bookmaker rows found.")
            return []

        odds_data = []
        for row in bookmaker_rows:
            try:
                bookmaker_name = self._extract_bookmaker_name(row)

                if not bookmaker_name or (target_bookmaker and bookmaker_name.lower() != target_bookmaker.lower()):
                    continue

                odds_cells = row.find_all(attrs={"data-testid": odd_cell_re})

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

    def parse_odds_history_modal(self, modal_html: str) -> dict[str, Any]:
        """
        Parses the HTML content of an odds history modal.

        Args:
            modal_html (str): Raw HTML from the modal.

        Returns:
            dict: Parsed odds history data, including historical odds and the opening odds.
        """
        self.logger.info("Parsing modal content for odds history.")
        soup = BeautifulSoup(modal_html, "html.parser")

        try:
            odds_history = []
            # Redesign: history columns are siblings inside a flex-row wrapper
            # (col 0 = timestamps, col 1 = values, col 2 = deltas).
            cols = soup.select("div.flex.flex-row.gap-3 > div.flex.flex-col.gap-1")
            timestamps = cols[0].select("div.font-normal") if cols else []
            odds_values = cols[1].select("div.font-bold") if len(cols) > 1 else []

            for ts, odd in zip(timestamps, odds_values, strict=False):
                time_text = ts.get_text(strip=True)
                try:
                    dt = datetime.strptime(time_text, "%d %b, %H:%M")
                    formatted_time = dt.replace(year=datetime.now(UTC).year).isoformat()
                except ValueError:
                    self.logger.warning(f"Failed to parse datetime: {time_text}")
                    continue

                odds_history.append({"timestamp": formatted_time, "odds": parse_odds_value(odd.get_text(strip=True))})

            # Parse opening odds
            opening_odds_block = soup.select_one("div.mt-2.gap-1")
            opening_ts_div = opening_odds_block.select_one("div.flex.gap-1 div")
            opening_val_div = opening_odds_block.select_one("div.flex.gap-1 .font-bold")

            opening_odds = None
            if opening_ts_div and opening_val_div:
                try:
                    dt = datetime.strptime(opening_ts_div.get_text(strip=True), "%d %b, %H:%M")
                    opening_odds = {
                        "timestamp": dt.replace(year=datetime.now(UTC).year).isoformat(),
                        "odds": parse_odds_value(opening_val_div.get_text(strip=True)),
                    }
                except ValueError:
                    self.logger.warning("Failed to parse opening odds timestamp.")

            return {"odds_history": odds_history, "opening_odds": opening_odds}

        except Exception as e:
            self.logger.error(f"Failed to parse odds history modal: {e}")
            return {}

    def _extract_bookmaker_name(self, block: Tag) -> str | None:
        """Extract bookmaker name from a row using a fallback chain.

        Strategies tried in order:
        1. ``[data-testid='outrights-expanded-bookmaker-name']`` text
        2. ``<a title="...">`` wrapping the logo / name
        3. ``<img>`` with an ``alt`` attribute containing the name
        """
        # 1. Primary (redesign): the bookmaker-name testid element
        name_el = block.find(attrs={"data-testid": OddsPortalSelectors.BOOKMAKER_NAME_TESTID})
        if name_el:
            name = name_el.get_text(strip=True)
            if name:
                return name

        # 2. Fallback: <a> with a title attribute (logo links)
        a_tag = block.find("a", attrs={"title": True})
        if a_tag and a_tag["title"]:
            name = a_tag["title"]
            # Normalise CTA-style titles like "Go to Betfair Exchange website!"
            if name.lower().startswith("go to ") and name.endswith("!"):
                name = name[len("go to ") : -1].strip()
                # Strip trailing "website" if present
                if name.lower().endswith(" website"):
                    name = name[: -len(" website")].strip()
            self.logger.debug(f"Resolved bookmaker name via <a title>: {name}")
            return name

        # 3. Fallback: any <img> with a meaningful alt attribute
        for img in block.find_all("img"):
            alt = img.get("alt", "")
            if alt and alt.lower() not in ("", "logo"):
                self.logger.debug(f"Resolved bookmaker name via <img alt>: {alt}")
                return alt

        self.logger.debug("Could not resolve bookmaker name from block")
        return None
