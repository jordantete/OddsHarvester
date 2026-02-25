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

        # Try broader "border-black-borders" pattern first as it works better
        bookmaker_blocks = soup.find_all("div", class_=re.compile(OddsPortalSelectors.BOOKMAKER_ROW_CLASS))

        if not bookmaker_blocks:
            # Fallback to broader selector
            bookmaker_blocks = soup.find_all("div", class_=re.compile(OddsPortalSelectors.BOOKMAKER_ROW_FALLBACK_CLASS))

        if not bookmaker_blocks:
            self.logger.warning("No bookmaker blocks found.")
            return []

        odds_data = []
        for block in bookmaker_blocks:
            try:
                bookmaker_name = self._extract_bookmaker_name(block)

                if not bookmaker_name or (target_bookmaker and bookmaker_name.lower() != target_bookmaker.lower()):
                    continue

                odds_blocks = block.find_all("div", class_=re.compile(OddsPortalSelectors.ODDS_BLOCK_CLASS_PATTERN))

                if len(odds_blocks) < len(odds_labels):
                    self.logger.warning(f"Incomplete odds data for bookmaker: {bookmaker_name}. Skipping...")
                    continue

                extracted_odds = {label: odds_blocks[i].get_text(strip=True) for i, label in enumerate(odds_labels)}

                for key, value in extracted_odds.items():
                    extracted_odds[key] = re.sub(r"(\d+\.\d+)\1", r"\1", value)

                extracted_odds["bookmaker_name"] = bookmaker_name
                extracted_odds["period"] = period
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
            timestamps = soup.select("div.flex.flex-col.gap-1 > div.flex.gap-3 > div.font-normal")
            odds_values = soup.select("div.flex.flex-col.gap-1 + div.flex.flex-col.gap-1 > div.font-bold")

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
        1. ``<img class="bookmaker-logo" title="...">``
        2. ``<a title="...">`` wrapping the logo / name
        3. ``<img>`` with an ``alt`` attribute containing the name
        """
        # 1. Primary: img.bookmaker-logo[title]
        img_tag = block.find("img", class_=OddsPortalSelectors.BOOKMAKER_LOGO_CLASS)
        if img_tag and img_tag.get("title"):
            return img_tag["title"]

        # 2. Fallback: <a> with a title attribute (logo links)
        a_tag = block.find("a", attrs={"title": True})
        if a_tag and a_tag["title"]:
            name = a_tag["title"]
            # Normalise CTA-style titles like "Go to Betfair Exchange website!"
            if name.lower().startswith("go to ") and name.endswith("!"):
                name = name[len("go to "):-1].strip()
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
