from datetime import UTC, datetime
import logging
import re
from typing import Any

from bs4 import BeautifulSoup
from playwright.async_api import Page

from src.core.browser_helper import BrowserHelper
from src.core.sport_market_registry import SportMarketRegistry


class OddsPortalMarketExtractor:
    """
    Extracts betting odds data from OddsPortal using Playwright.

    This class provides methods to scrape various betting markets (e.g., 1X2, Over/Under, BTTS, ..)
    for specific match periods and bookmaker odds.
    """

    DEFAULT_TIMEOUT = 5000
    SCROLL_PAUSE_TIME = 2000
    MARKET_SWITCH_WAIT_TIME = 3000

    def __init__(self, browser_helper: BrowserHelper):
        """
        Initialize OddsPortalMarketExtractor.

        Args:
            browser_helper (BrowserHelper): Helper class for browser interactions.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.browser_helper = browser_helper

    async def scrape_markets(
        self,
        page: Page,
        sport: str,
        markets: list[str],
        period: str = "FullTime",
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        preview_submarkets_only: bool = False,
    ) -> dict[str, Any]:
        """
        Extract market data for a given match.

        Args:
            page (Page): A Playwright Page instance for this task.
            sport (str): The sport to scrape odds for.
            markets (List[str]): A list of markets to scrape (e.g., ['1x2', 'over_under_2_5']).
            period (str): The match period (e.g., "FullTime").
            scrape_odds_history (bool): Whether to extract historic odds evolution.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.
            preview_submarkets_only (bool): If True, only scrape average odds from visible submarkets without loading individual bookmaker details.

        Returns:
            Dict[str, Any]: A dictionary containing market data.
        """
        market_data = {}
        market_methods = SportMarketRegistry.get_market_mapping(sport)

        # Group markets by their main market type for optimization in preview mode
        market_groups = {}

        for market in markets:
            try:
                if market in market_methods:
                    # For preview mode, group markets by their main market type
                    if preview_submarkets_only:
                        # Get the main market info from the existing market method
                        main_market_info = self._get_main_market_info(market_methods[market])
                        if main_market_info:
                            main_market_name = main_market_info["main_market"]
                            if main_market_name not in market_groups:
                                market_groups[main_market_name] = []
                            market_groups[main_market_name].append(market)
                    else:
                        # Normal mode: scrape each market individually
                        self.logger.info(f"Scraping market: {market} (Period: {period})")
                        market_data[f"{market}_market"] = await market_methods[market](
                            self, page, period, scrape_odds_history, target_bookmaker, preview_submarkets_only
                        )
                else:
                    self.logger.warning(f"Market '{market}' is not supported for sport '{sport}'.")

            except Exception as e:
                self.logger.error(f"Error scraping market '{market}': {e}")
                market_data[f"{market}_market"] = None

        # Handle grouped markets in preview mode
        if preview_submarkets_only and market_groups:
            for main_market_name, grouped_markets in market_groups.items():
                try:
                    self.logger.info(
                        f"Scraping main market: {main_market_name} for submarkets: {grouped_markets} (Period: {period})"
                    )

                    # Use the first market in the group to get the odds labels
                    first_market = grouped_markets[0]
                    if first_market in market_methods:
                        main_market_info = self._get_main_market_info(market_methods[first_market])
                        odds_labels = main_market_info["odds_labels"] if main_market_info else None

                        # Scrape the main market once
                        main_market_data = await self.extract_market_odds(
                            page=page,
                            main_market=main_market_name,
                            specific_market=None,  # No specific market, scrape all submarkets
                            period=period,
                            odds_labels=odds_labels,
                            scrape_odds_history=scrape_odds_history,
                            target_bookmaker=target_bookmaker,
                            preview_submarkets_only=preview_submarkets_only,
                        )

                        # Distribute the results to each specific market
                        for specific_market in grouped_markets:
                            market_data[f"{specific_market}_market"] = main_market_data

                except Exception as e:
                    self.logger.error(f"Error scraping grouped markets for {main_market_name}: {e}")
                    for specific_market in grouped_markets:
                        market_data[f"{specific_market}_market"] = None

        return market_data

    def _get_main_market_info(self, market_method) -> dict | None:
        """
        Extract main market information from a market method lambda.

        Args:
            market_method: The market method lambda function

        Returns:
            dict | None: Dictionary with main_market and odds_labels, or None if not found
        """
        try:
            # The market method is a lambda that calls extract_market_odds with specific parameters
            # We can inspect its closure to get the main_market and odds_labels
            if hasattr(market_method, "__closure__") and market_method.__closure__:
                # Extract the main_market and odds_labels from the lambda's closure
                closure_vars = market_method.__code__.co_freevars
                closure_values = [cell.cell_contents for cell in market_method.__closure__]

                # Find main_market and odds_labels in the closure
                main_market = None
                odds_labels = None

                for var_name, var_value in zip(closure_vars, closure_values, strict=False):
                    if var_name == "main_market":
                        main_market = var_value
                    elif var_name == "odds_labels":
                        odds_labels = var_value

                if main_market:
                    return {"main_market": main_market, "odds_labels": odds_labels}
        except Exception as e:
            self.logger.debug(f"Could not extract market info from method: {e}")

        return None

    async def extract_market_odds(
        self,
        page: Page,
        main_market: str,
        specific_market: str | None = None,
        period: str = "FullTime",
        odds_labels: list | None = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        preview_submarkets_only: bool = False,
    ) -> list:
        """
        Extracts odds for a given main market and optional specific sub-market.

        Args:
            page (Page): The Playwright page instance.
            main_market (str): The main market name (e.g., "Over/Under", "European Handicap").
            specific_market (str, optional): The specific market within the main market (e.g., "Over/Under 2.5", "EH +1").
            period (str): The match period (e.g., "FullTime").
            odds_labels (list): Labels corresponding to odds values in the extracted data.
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.
            preview_submarkets_only (bool): If True, only scrape average odds from visible submarkets without loading individual bookmaker details.

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds.
        """
        self.logger.info(
            f"Scraping odds for market: {main_market}, specific: {specific_market}, period: {period}, preview_mode: {preview_submarkets_only}"
        )

        try:
            # Navigate to the main market tab
            if not await self.browser_helper.navigate_to_market_tab(
                page=page, market_tab_name=main_market, timeout=self.DEFAULT_TIMEOUT
            ):
                self.logger.error(f"Failed to find or click {main_market} tab")
                return []

            # Wait for market switch to complete
            await self._wait_for_market_switch(page, main_market)

            # Handle different scraping modes
            if preview_submarkets_only:
                # For preview mode, always try passive extraction first
                self.logger.info(f"Using passive mode for {main_market} in preview mode")
                odds_data = await self._extract_visible_submarkets_passive(
                    page=page, main_market=main_market, period=period, odds_labels=odds_labels
                )

                # If no data was extracted passively, fall back to normal scraping
                if not odds_data:
                    self.logger.info(f"No data extracted passively for {main_market}, falling back to normal scraping")
                    if specific_market and not await self.browser_helper.scroll_until_visible_and_click_parent(
                        page=page,
                        selector="div.flex.w-full.items-center.justify-start.pl-3.font-bold p",
                        text=specific_market,
                    ):
                        self.logger.error(f"Failed to find or select {specific_market} within {main_market}")
                        return []

                    await page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
                    html_content = await page.content()

                    odds_data = await self._parse_market_odds(
                        html_content=html_content,
                        period=period,
                        odds_labels=odds_labels,
                        target_bookmaker=target_bookmaker,
                    )
            else:
                # Active mode: click on specific submarket if provided
                if specific_market and not await self.browser_helper.scroll_until_visible_and_click_parent(
                    page=page,
                    selector="div.flex.w-full.items-center.justify-start.pl-3.font-bold p",
                    text=specific_market,
                ):
                    self.logger.error(f"Failed to find or select {specific_market} within {main_market}")
                    return []

                await page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
                html_content = await page.content()

                odds_data = await self._parse_market_odds(
                    html_content=html_content, period=period, odds_labels=odds_labels, target_bookmaker=target_bookmaker
                )

            if scrape_odds_history:
                self.logger.info("Fetching odds history for all parsed bookmakers.")

                for odds_entry in odds_data:
                    bookmaker_name = odds_entry.get("bookmaker_name")

                    if not bookmaker_name or (target_bookmaker and bookmaker_name.lower() != target_bookmaker.lower()):
                        continue

                    modals = await self._extract_odds_history_for_bookmaker(page, bookmaker_name)

                    if modals:
                        all_histories = []
                        for modal_html in modals:
                            parsed_history = self._parse_odds_history_modal(modal_html)
                            if parsed_history:
                                all_histories.append(parsed_history)

                        odds_entry["odds_history_data"] = all_histories

            # Close the sub-market after scraping to avoid duplicates
            if specific_market:
                self.logger.info(f"Closing sub-market: {specific_market}")
                if not await self.browser_helper.scroll_until_visible_and_click_parent(
                    page=page,
                    selector="div.flex.w-full.items-center.justify-start.pl-3.font-bold p",
                    text=specific_market,
                ):
                    self.logger.warning(f"Failed to close {specific_market}, might affect next scraping.")

            return odds_data

        except Exception as e:
            self.logger.error(f"Error extracting odds for {main_market} {specific_market}: {e}")
            return []

    async def _is_preview_compatible_market(self, page, main_market: str) -> bool:
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
                        f"Market {main_market} has {visible_submarkets_count} visible submarkets ({submarkets_with_odds} with odds) - compatible with preview mode"
                    )
                    return True
                else:
                    self.logger.info(
                        f"Market {main_market} has {visible_submarkets_count} visible submarkets but only {submarkets_with_odds} with odds - incompatible with preview mode"
                    )
                    return False
            else:
                self.logger.info(f"Market {main_market} has no visible submarkets - incompatible with preview mode")
                return False

        except Exception as e:
            self.logger.error(f"Error analyzing market structure for {main_market}: {e}")

    async def _extract_visible_submarkets_passive(
        self, page: Page, main_market: str, period: str, odds_labels: list | None = None
    ) -> list:
        """
        Extracts all visible submarkets from the current page without clicking to load more.

        Args:
            page (Page): The Playwright page instance.
            main_market (str): The main market name (e.g., "Over/Under", "European Handicap").
            period (str): The match period (e.g., "FullTime").
            odds_labels (list, optional): Labels corresponding to odds values. If None, defaults to ["odds_over", "odds_under"].

        Returns:
            list[dict]: A list of dictionaries containing submarket data with odds.
        """
        self.logger.info(f"Extracting visible submarkets for {main_market} in passive mode")

        try:
            await page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
            html_content = await page.content()
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
                    submarket_name = None

                    # First, try to find the div with data-testid pattern (for Over/Under markets)
                    market_key = main_market.lower().replace("/", "-").replace(" ", "-")
                    data_testid_pattern = f"{market_key}-collapsed-option-box"
                    submarket_name_element = row.find("div", attrs={"data-testid": re.compile(data_testid_pattern)})

                    if submarket_name_element:
                        # For markets like Over/Under, look for the clean name in max-sm:!hidden class
                        clean_name_p = submarket_name_element.find("p", class_="max-sm:!hidden")
                        if clean_name_p:
                            submarket_name = clean_name_p.get_text(strip=True)
                        else:
                            # Fallback to any <p> in the div
                            first_p = submarket_name_element.find("p")
                            if first_p:
                                submarket_name = first_p.get_text(strip=True)

                    # If not found, try to find any div with the flex classes (for other markets)
                    if not submarket_name:
                        flex_div = row.find("div", class_=re.compile(r"flex.*items-center.*justify-start"))
                        if flex_div:
                            # Look for the clean name in max-sm:!hidden class first
                            clean_name_p = flex_div.find("p", class_="max-sm:!hidden")
                            if clean_name_p:
                                submarket_name = clean_name_p.get_text(strip=True)
                            else:
                                # Fallback to any <p> in the div
                                first_p = flex_div.find("p")
                                if first_p:
                                    submarket_name = first_p.get_text(strip=True)

                    # If still not found, try to find any <p> with font-bold class
                    if not submarket_name:
                        bold_p = row.find("p", class_=re.compile(r"font-bold"))
                        if bold_p:
                            submarket_name = bold_p.get_text(strip=True)

                    # If still not found, try to find any <p> that looks like a submarket name
                    if not submarket_name:
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
                                submarket_name = text
                                break

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
                            f"Skipping row with {len(odds_containers)} odds, need at least {min_odds_required} for {main_market}"
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

    async def _wait_for_market_switch(self, page: Page, market_name: str, max_attempts: int = 3) -> bool:
        """
        Wait for the market switch to complete and verify the correct market is active.

        Args:
            page (Page): The Playwright page instance.
            market_name (str): The name of the market that should be active.
            max_attempts (int): Maximum number of verification attempts.

        Returns:
            bool: True if the market switch is confirmed, False otherwise.
        """
        self.logger.info(f"Waiting for market switch to complete for: {market_name}")

        for attempt in range(max_attempts):
            try:
                # Wait for the market switch animation to complete
                await page.wait_for_timeout(self.MARKET_SWITCH_WAIT_TIME)

                # Check if the market tab is active
                active_tab = await page.query_selector("li.active, li[class*='active'], .active")
                if active_tab:
                    tab_text = await active_tab.text_content()
                    if tab_text and market_name.lower() in tab_text.lower():
                        self.logger.info(f"Market switch confirmed: {market_name} is active")
                        return True

            except Exception as e:
                self.logger.warning(f"Market switch verification attempt {attempt + 1} failed: {e}")

        self.logger.warning(f"Market switch verification failed after {max_attempts} attempts")
        return False

    async def _parse_market_odds(
        self, html_content: str, period: str, odds_labels: list, target_bookmaker: str | None = None
    ) -> list:
        """
        Parses odds for a given market type in a generic way.

        Args:
            html_content (str): The HTML content of the page.
            period (str): The match period (e.g., "FullTime").
            odds_labels (list): A list of labels defining the expected odds columns (e.g., ["odds_over", "odds_under"]).

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds.
        """
        self.logger.info("Parsing odds from HTML content.")
        soup = BeautifulSoup(html_content, "html.parser")

        # Try broader "border-black-borders" pattern first as it works better
        bookmaker_blocks = soup.find_all("div", class_=re.compile(r"border-black-borders"))

        if not bookmaker_blocks:
            # Fallback to original selector for backwards compatibility
            bookmaker_blocks = soup.find_all("div", class_=re.compile(r"^border-black-borders flex h-9"))

        if not bookmaker_blocks:
            self.logger.warning("No bookmaker blocks found.")
            return []

        odds_data = []
        for block in bookmaker_blocks:
            try:
                img_tag = block.find("img", class_="bookmaker-logo")
                bookmaker_name = img_tag["title"] if img_tag and "title" in img_tag.attrs else "Unknown"

                if not bookmaker_name or (target_bookmaker and bookmaker_name.lower() != target_bookmaker.lower()):
                    continue

                odds_blocks = block.find_all("div", class_=re.compile(r"flex-center.*flex-col.*font-bold"))

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

    async def _extract_odds_history_for_bookmaker(self, page: Page, bookmaker_name: str) -> list[str]:
        """
        Hover on odds for a specific bookmaker to trigger and capture the odds history modal.

        Args:
            page (Page): Playwright page instance.
            bookmaker_name (str): Name of the bookmaker to match.

        Returns:
            List[str]: List of raw HTML content from modals triggered by hovering over matched odds blocks.
        """
        self.logger.info(f"Extracting odds history for bookmaker: {bookmaker_name}")
        await page.wait_for_timeout(self.SCROLL_PAUSE_TIME)

        modals_data = []

        try:
            # Find all bookmaker rows
            rows = await page.query_selector_all("div.border-black-borders.flex.h-9")

            for row in rows:
                try:
                    logo_img = await row.query_selector("img.bookmaker-logo")

                    if logo_img:
                        title = await logo_img.get_attribute("title")

                        if title and bookmaker_name.lower() in title.lower():
                            self.logger.info(f"Found matching bookmaker row: {title}")
                            odds_blocks = await row.query_selector_all("div.flex-center.flex-col.font-bold")

                            for odds in odds_blocks:
                                await odds.hover()
                                await page.wait_for_timeout(2000)

                                odds_movement_element = await page.wait_for_selector(
                                    "h3:text('Odds movement')", timeout=3000
                                )
                                modal_wrapper = await odds_movement_element.evaluate_handle(
                                    "node => node.parentElement"
                                )
                                modal_element = modal_wrapper.as_element()

                                if modal_element:
                                    html = await modal_element.inner_html()
                                    modals_data.append(html)
                                else:
                                    self.logger.warning(
                                        "Unable to retrieve odds' evolution modal: modal_element is None"
                                    )

                except Exception as e:
                    self.logger.warning(f"Failed to process a bookmaker row: {e}")
        except Exception as e:
            self.logger.warning(f"Failed to extract odds history for bookmaker {bookmaker_name}: {e}")

        return modals_data

    def _parse_odds_history_modal(self, modal_html: str) -> dict:
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

                odds_history.append({"timestamp": formatted_time, "odds": float(odd.get_text(strip=True))})

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
                        "odds": float(opening_val_div.get_text(strip=True)),
                    }
                except ValueError:
                    self.logger.warning("Failed to parse opening odds timestamp.")

            return {"odds_history": odds_history, "opening_odds": opening_odds}

        except Exception as e:
            self.logger.error(f"Failed to parse odds history modal: {e}")
            return {}
