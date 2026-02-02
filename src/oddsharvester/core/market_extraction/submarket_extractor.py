import logging
import re
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import Page


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
            # Get current page HTML
            html_content = await page.content()
            if not isinstance(html_content, str):
                html_content = ""
            soup = BeautifulSoup(html_content, "html.parser")

            # Look for submarket containers
            submarket_containers = soup.find_all("div", class_="border-black-borders")

            if submarket_containers:
                visible_submarkets_count = len(submarket_containers)
                self.logger.debug(f"Found {visible_submarkets_count} visible submarkets for {main_market}")

                # Check if any of these submarkets have visible odds
                submarkets_with_odds = 0
                for container in submarket_containers[:5]:  # Check first 5 submarkets
                    odds_containers = container.find_all("p", attrs={"data-testid": "odd-container-default"})
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
            await page.wait_for_timeout(2000)  # SCROLL_PAUSE_TIME
            html_content = await page.content()
            if not isinstance(html_content, str):
                html_content = ""
            soup = BeautifulSoup(html_content, "html.parser")

            # Find all submarket rows (these contain the handicap names and odds)
            submarket_rows = soup.find_all("div", class_=re.compile(r"border-black-borders"))

            if not submarket_rows:
                self.logger.warning("No submarket rows found in passive mode")
                return []

            submarkets_data = []

            for row in submarket_rows:
                try:
                    # Extract submarket name - improved parsing for different market types
                    submarket_name = self._extract_submarket_name(row, main_market)

                    if not submarket_name:
                        continue

                    # Log the extracted submarket name for debugging
                    self.logger.debug(f"Extracted submarket name: '{submarket_name}'")

                    # Find all odds containers in this row
                    odds_containers = row.find_all("p", attrs={"data-testid": "odd-container-default"})

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
        """Extract submarket name from a row using multiple strategies."""
        # First, try to find the div with data-testid pattern (for Over/Under markets)
        market_key = main_market.lower().replace("/", "-").replace(" ", "-")
        data_testid_pattern = f"{market_key}-collapsed-option-box"
        submarket_name_element = row.find("div", attrs={"data-testid": re.compile(data_testid_pattern)})

        if submarket_name_element:
            # For markets like Over/Under, look for the clean name in max-sm:!hidden class
            clean_name_p = submarket_name_element.find("p", class_="max-sm:!hidden")
            if clean_name_p:
                return clean_name_p.get_text(strip=True)
            else:
                # Fallback to any <p> in the div
                first_p = submarket_name_element.find("p")
                if first_p:
                    return first_p.get_text(strip=True)

        # If not found, try to find any div with the flex classes (for other markets)
        flex_div = row.find("div", class_=re.compile(r"flex.*items-center.*justify-start"))
        if flex_div:
            # Look for the clean name in max-sm:!hidden class first
            clean_name_p = flex_div.find("p", class_="max-sm:!hidden")
            if clean_name_p:
                return clean_name_p.get_text(strip=True)
            else:
                # Fallback to any <p> in the div
                first_p = flex_div.find("p")
                if first_p:
                    return first_p.get_text(strip=True)

        # If still not found, try to find any <p> with font-bold class
        bold_p = row.find("p", class_=re.compile(r"font-bold"))
        if bold_p:
            return bold_p.get_text(strip=True)

        # If still not found, try to find any <p> that looks like a submarket name
        all_p_tags = row.find_all("p")
        for p_tag in all_p_tags:
            text = p_tag.get_text(strip=True)
            # Skip percentage values, odds values, and other non-submarket text
            if (
                text
                and not text.endswith("%")
                and not text.replace(".", "").isdigit()  # Skip pure numbers like "2.80"
                and len(text) > 1
                and not text.startswith("data-testid")  # Skip any data attributes
                and ":" in text
            ):  # Correct Score submarkets contain ":"
                return text

        return None
