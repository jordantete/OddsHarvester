import re, logging
from typing import Dict, Any, List
from playwright.async_api import Page
from bs4 import BeautifulSoup
from src.core.browser_helper import BrowserHelper
from src.core.sport_market_registry import SportMarketRegistry
from datetime import datetime, timezone

class OddsPortalMarketExtractor:
    """
    Extracts betting odds data from OddsPortal using Playwright.

    This class provides methods to scrape various betting markets (e.g., 1X2, Over/Under, BTTS, ..)
    for specific match periods and bookmaker odds.
    """
    DEFAULT_TIMEOUT = 5000
    SCROLL_PAUSE_TIME = 2000

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
        markets: List[str],
        period: str = "FullTime",
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None
    ) -> Dict[str, Any]:
        """
        Extract market data for a given match.

        Args:
            page (Page): A Playwright Page instance for this task.
            sport (str): The sport to scrape odds for.
            markets (List[str]): A list of markets to scrape (e.g., ['1x2', 'over_under_2_5']).
            period (str): The match period (e.g., "FullTime").
            scrape_odds_history (bool): Whether to extract historic odds evolution.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.

        Returns:
            Dict[str, Any]: A dictionary containing market data.
        """
        market_data = {}
        market_methods = SportMarketRegistry.get_market_mapping(sport)

        for market in markets:
            try:
                if market in market_methods:
                    self.logger.info(f"Scraping market: {market} (Period: {period})")
                    market_data[f"{market}_market"] = await market_methods[market](self, page, period, scrape_odds_history, target_bookmaker)
                else:
                    self.logger.warning(f"Market '{market}' is not supported for sport '{sport}'.")

            except Exception as e:
                self.logger.error(f"Error scraping market '{market}': {e}")
                market_data[f"{market}_market"] = None

        return market_data

    async def extract_market_odds(
        self,
        page: Page,
        main_market: str,
        specific_market: str = None,
        period: str = "FullTime",
        odds_labels: list = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None
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

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds.
        """
        self.logger.info(f"Scraping odds for market: {main_market}, specific: {specific_market}, period: {period}")

        try:
            # Navigate to the main market tab
            if not await self.browser_helper.navigate_to_market_tab(page=page, market_tab_name=main_market, timeout=self.DEFAULT_TIMEOUT):
                self.logger.error(f"Failed to find or click {main_market} tab")
                return []

            # If a specific sub-market needs to be selected (e.g., Over/Under 2.5)
            if specific_market:
                if not await self.browser_helper.scroll_until_visible_and_click_parent(
                    page=page,
                    selector='div.flex.w-full.items-center.justify-start.pl-3.font-bold p',
                    text=specific_market
                ):
                    self.logger.error(f"Failed to find or select {specific_market} within {main_market}")
                    return []

            await page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
            html_content = await page.content()
            odds_data = await self._parse_market_odds(html_content=html_content, period=period, odds_labels=odds_labels, target_bookmaker=target_bookmaker)

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
                    selector='div.flex.w-full.items-center.justify-start.pl-3.font-bold p',
                    text=specific_market
                ):
                    self.logger.warning(f"Failed to close {specific_market}, might affect next scraping.")

            return odds_data

        except Exception as e:
            self.logger.error(f"Error extracting odds for {main_market} {specific_market}: {e}")
            return []
    
    async def _parse_market_odds(
        self, 
        html_content: str, 
        period: str, 
        odds_labels: list,
        target_bookmaker: str | None = None
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
        soup = BeautifulSoup(html_content, "lxml")
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

    async def _extract_odds_history_for_bookmaker(
        self, 
        page: Page, 
        bookmaker_name: str
    ) -> List[str]:
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

                            odds_movement_element = await page.wait_for_selector("h3:text('Odds movement')", timeout=3000)
                            modal_wrapper = await odds_movement_element.evaluate_handle("node => node.parentElement")
                            modal_element = modal_wrapper.as_element()

                            if modal_element:
                                html = await modal_element.inner_html()
                                modals_data.append(html)
                            else:
                                self.logger.warning(f"Unable to retrieve odds' evolution modal: modal_element is None")
            
            except Exception as e:
                self.logger.warning(f"Failed to process a bookmaker row: {e}")

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
        soup = BeautifulSoup(modal_html, "lxml")

        try:
            odds_history = []
            timestamps = soup.select("div.flex.flex-col.gap-1 > div.flex.gap-3 > div.font-normal")
            odds_values = soup.select("div.flex.flex-col.gap-1 + div.flex.flex-col.gap-1 > div.font-bold")

            for ts, odd in zip(timestamps, odds_values):
                time_text = ts.get_text(strip=True)
                try:
                    dt = datetime.strptime(time_text, "%d %b, %H:%M")
                    formatted_time = dt.replace(year=datetime.now(timezone.utc).year).isoformat()
                except ValueError:
                    self.logger.warning(f"Failed to parse datetime: {time_text}")
                    continue

                odds_history.append({
                    "timestamp": formatted_time,
                    "odds": float(odd.get_text(strip=True))
                })

            # Parse opening odds
            opening_odds_block = soup.select_one("div.mt-2.gap-1")
            opening_ts_div = opening_odds_block.select_one("div.flex.gap-1 div")
            opening_val_div = opening_odds_block.select_one("div.flex.gap-1 .font-bold")

            opening_odds = None
            if opening_ts_div and opening_val_div:
                try:
                    dt = datetime.strptime(opening_ts_div.get_text(strip=True), "%d %b, %H:%M")
                    opening_odds = {
                        "timestamp": dt.replace(year=datetime.now(timezone.utc).year).isoformat(),
                        "odds": float(opening_val_div.get_text(strip=True))
                    }
                except ValueError:
                    self.logger.warning("Failed to parse opening odds timestamp.")

            return {
                "odds_history": odds_history,
                "opening_odds": opening_odds
            }

        except Exception as e:
            self.logger.error(f"Failed to parse odds history modal: {e}")
            return {}