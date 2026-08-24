import logging
import re
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import Page

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import SCROLL_PAUSE_TIME_MS

# Collapsed submarket line rows (2026-08 redesign): one leaf <tr> per line,
# preview odds in data-testid='odd-container-default' cells.
_ODD_DEFAULT_RE = re.compile(r"^odd-container-default")


def _find_line_rows(soup: BeautifulSoup) -> list:
    """Leaf <tr> rows carrying collapsed preview odds (odd-container-default)."""
    rows = []
    for tr in soup.find_all("tr"):
        if tr.find("tr") is not None:
            continue
        if not tr.find(attrs={"data-testid": _ODD_DEFAULT_RE}):
            continue
        rows.append(tr)
    return rows


class SubmarketExtractor:
    """Handles extraction of visible submarkets in passive mode."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def is_preview_compatible_market(self, page: Page, main_market: str) -> bool:
        """
        Determines if a market is compatible with preview mode by analyzing the HTML structure.

        This method dynamically analyzes the page to see if there are multiple visible submarkets
        that can be scraped without clicking.

        Args:
            page: The Playwright page instance.
            main_market (str): The main market name (e.g., "Over/Under", "European Handicap").

        Returns:
            bool: True if the market supports preview mode, False otherwise.
        """
        try:
            html_content = await page.content()
            if not isinstance(html_content, str):
                html_content = ""
            soup = BeautifulSoup(html_content, "html.parser")

            line_rows = _find_line_rows(soup)

            if line_rows:
                visible_submarkets_count = len(line_rows)
                self.logger.debug(f"Found {visible_submarkets_count} visible submarkets for {main_market}")

                # Check if any of these submarkets have visible odds
                submarkets_with_odds = 0
                for row in line_rows[:5]:  # Check first 5 submarkets
                    odds_containers = row.find_all(attrs={"data-testid": _ODD_DEFAULT_RE})
                    if len(odds_containers) >= 2:  # Need at least 2 odds to be useful
                        submarkets_with_odds += 1

                self.logger.debug(f"Found {submarkets_with_odds} submarkets with visible odds for {main_market}")

                # If we have multiple visible submarkets with odds, the market is compatible
                if visible_submarkets_count > 1 and submarkets_with_odds > 0:
                    self.logger.info(
                        f"Market {main_market} has {visible_submarkets_count} visible submarkets "
                        f"({submarkets_with_odds} with odds) - compatible with preview mode"
                    )
                    return True
                else:
                    self.logger.info(
                        f"Market {main_market} has {visible_submarkets_count} visible submarkets but only "
                        f"{submarkets_with_odds} with odds - incompatible with preview mode"
                    )
                    return False
            else:
                self.logger.info(f"Market {main_market} has no visible submarkets - incompatible with preview mode")
                return False

        except Exception as e:
            self.logger.error(f"Error analyzing market structure for {main_market}: {e}")
            return False

    async def extract_visible_submarkets_passive(
        self, page: Page, main_market: str, period: str, odds_labels: list | None = None
    ) -> list[dict[str, Any]]:
        """
        Extracts all visible submarkets from the current page without clicking to load more.

        Args:
            page (Page): The Playwright page instance.
            main_market (str): The main market name (e.g., "Over/Under", "European Handicap").
            period (str): The match period (e.g., "FullTime").
            odds_labels (list, optional): Labels corresponding to odds values. If None, defaults to
            ["odds_over", "odds_under"].

        Returns:
            list[dict]: A list of dictionaries containing submarket data with odds.
        """
        self.logger.info(f"Extracting visible submarkets for {main_market} in passive mode")

        try:
            await page.wait_for_timeout(SCROLL_PAUSE_TIME_MS)
            html_content = await page.content()
            if not isinstance(html_content, str):
                html_content = ""
            soup = BeautifulSoup(html_content, "html.parser")

            line_rows = _find_line_rows(soup)

            if not line_rows:
                self.logger.warning("No submarket rows found in passive mode")
                return []

            submarkets_data = []

            for row in line_rows:
                try:
                    submarket_name = self._extract_submarket_name(row, main_market)

                    if not submarket_name:
                        continue

                    self.logger.debug(f"Extracted submarket name: '{submarket_name}'")

                    odds_containers = row.find_all(attrs={"data-testid": _ODD_DEFAULT_RE})

                    # Use provided odds_labels or determine based on market type
                    if odds_labels is None:
                        # Default to Over/Under labels, but adjust for single-odds markets
                        if "correct score" in main_market.lower():
                            odds_labels = ["correct_score"]
                            min_odds_required = 1
                        else:
                            odds_labels = ["odds_over", "odds_under"]
                            min_odds_required = 2
                    else:
                        min_odds_required = len(odds_labels)

                    if len(odds_containers) < min_odds_required:
                        self.logger.debug(
                            f"Skipping row with {len(odds_containers)} odds, need at least {min_odds_required} "
                            f"for {main_market}"
                        )
                        continue

                    # Extract odds values
                    odds_values = []
                    for container in odds_containers:
                        odds_text = container.get_text(strip=True)
                        if odds_text:
                            odds_values.append(odds_text)

                    if len(odds_values) >= min_odds_required:
                        submarket_data = {
                            "submarket_name": submarket_name,
                            "period": period,
                            "market_type": main_market,
                            "extraction_mode": "passive",
                        }

                        # Add odds with appropriate labels
                        for i, label in enumerate(odds_labels):
                            if i < len(odds_values):
                                submarket_data[label] = odds_values[i]

                        # Add any additional odds beyond the expected labels
                        if len(odds_values) > len(odds_labels):
                            for i, odds_value in enumerate(odds_values[len(odds_labels) :], start=len(odds_labels)):
                                submarket_data[f"odds_option_{i + 1}"] = odds_value

                        submarkets_data.append(submarket_data)

                except Exception as e:
                    self.logger.warning(f"Error processing submarket row: {e}")
                    continue

            self.logger.info(f"Successfully extracted {len(submarkets_data)} visible submarkets in passive mode")
            return submarkets_data

        except Exception as e:
            self.logger.error(f"Error in passive submarket extraction: {e}")
            return []

    def _extract_submarket_name(self, row, main_market: str) -> str | None:
        """Extract submarket name from a line row.

        Strategy 1: the clean-name element (`max-sm:hidden` class) carrying the
        full label (the short form sits in a sibling `sm:hidden` element).
        Strategy 2: first span/p text outside the odds cells that is neither a
        percentage nor a bare number (covers Correct Score '1:0' labels).
        """
        clean = row.find(["span", "p"], class_=OddsPortalSelectors.SUBMARKET_CLEAN_NAME_CLASS)
        if clean:
            text = clean.get_text(strip=True)
            if text:
                return text

        for el in row.find_all(["span", "p"]):
            if el.find_parent(attrs={"data-testid": re.compile(rf"^{OddsPortalSelectors.ODD_CELL_TESTID_PREFIX}")}):
                continue
            text = el.get_text(strip=True)
            if not text or text.endswith("%"):
                continue
            if text.replace(".", "").isdigit():
                continue
            return text

        return None
