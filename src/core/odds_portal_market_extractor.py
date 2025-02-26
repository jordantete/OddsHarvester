import re, logging
from typing import Dict, Any, List
from playwright.async_api import Page
from bs4 import BeautifulSoup
from .browser_helper import BrowserHelper
from .sport_market_registry import SportMarketRegistry

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
        period: str = "FullTime"
    ) -> Dict[str, Any]:
        """
        Extract market data for a given match.

        Args:
            page (Page): A Playwright Page instance for this task.
            sport (str): The sport to scrape odds for.
            markets (List[str]): A list of markets to scrape (e.g., ['1x2', 'over_under_2_5']).
            period (str): The match period (e.g., "FullTime").

        Returns:
            Dict[str, Any]: A dictionary containing market data.
        """
        market_data = {}
        market_methods = SportMarketRegistry.get_market_mapping(sport)

        for market in markets:
            try:
                if market in market_methods:
                    self.logger.info(f"Scraping market: {market} (Period: {period})")
                    market_data[f"{market}_market"] = await market_methods[market](self, page, period)
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
        odds_labels: list = None
    ) -> list:
        """
        Extracts odds for a given main market and optional specific sub-market.

        Args:
            page (Page): The Playwright page instance.
            main_market (str): The main market name (e.g., "Over/Under", "European Handicap").
            specific_market (str, optional): The specific market within the main market (e.g., "Over/Under 2.5", "EH +1").
            period (str): The match period (e.g., "FullTime").
            odds_labels (list): Labels corresponding to odds values in the extracted data.

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
            odds_data = await self._parse_market_odds(html_content=html_content, period=period, odds_labels=odds_labels)

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
        odds_labels: list
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