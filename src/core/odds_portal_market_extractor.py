import re, logging
from playwright.async_api import Page
from bs4 import BeautifulSoup
from core.browser_helper import BrowserHelper

class OddsPortalMarketExtractor:
    """
    Extracts betting odds data from OddsPortal using Playwright.

    This class provides methods to scrape various betting markets (e.g., 1X2, Over/Under, BTTS, ..)
    for specific match periods and bookmaker odds.
    """
    DEFAULT_TIMEOUT = 5000
    SCROLL_PAUSE_TIME = 2000

    def __init__(
        self, 
        page: Page,
        browser_helper: BrowserHelper
    ):
        """
        Initialize OddsPortalMarketExtractor.

        Args:
            page (Page): The Playwright page instance to interact with.
            browser_helper (BrowserHelper): Helper class for browser interactions.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.page = page
        self.browser_helper = browser_helper

    async def extract_over_under_odds(
        self, 
        over_under_market: str, 
        period: str = "FullTime"
    ) -> list:
        """
        Extract Over/Under odds for the specified type and period.

        Args:
            over_under_type (str): The Over/Under market (e.g., "1.5", "2.5").
            period (str): The match period to scrape odds for.

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds.
        """
        self.logger.info(f"Scraping Over/Under odds for type {over_under_market}, period {period}")
        try: 
            if not await self.browser_helper.navigate_to_market_tab(page=self.page, market_tab_name='Over/Under', timeout=self.DEFAULT_TIMEOUT):
                self.logger.error("Failed to find or click Over/Under tab.")
                return []
            
            if not await self.browser_helper.scroll_until_visible_and_click_parent(
                page=self.page,
                selector='div.flex.w-full.items-center.justify-start.pl-3.font-bold p',
                text=f"Over/Under +{over_under_market}"
            ):
                self.logger.error(f"Over/Under {over_under_market} not found or couldn't be selected.")
                return []
            
            await self.page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
            html_content = await self.page.content()
            return await self._parse_over_under_odds(html_content=html_content, period=period)
        
        except Exception as e:
            self.logger.error(f"Error during Over/Under odds extraction: {e}")
            return []
    
    async def _parse_over_under_odds(
        self, 
        html_content: str,
        period: str = "FullTime"
    ) -> list:
        """
        Parses Over/Under odds data from the page's HTML content.

        Args:
            html_content (str): The HTML content of the page.
            period (str): The match period to scrape odds for.

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds data.
        """
        self.logger.info("Parsing Over/Under odds from HTML content.")
        soup = BeautifulSoup(html_content, "lxml")
        bookmaker_blocks = soup.find_all("div", class_=re.compile(r"^border-black-borders flex h-9"))

        if not bookmaker_blocks:
            self.logger.warning("No bookmaker blocks found in Over/Under odds.")
            return []

        odds_data = []
        for block in bookmaker_blocks:
            try:
                img_tag = block.find("img", class_="bookmaker-logo")
                bookmaker_name = img_tag["title"] if img_tag and "title" in img_tag.attrs else "Unknown"
                odds_blocks = block.find_all("div", class_=re.compile(r"flex-center.*flex-col.*font-bold"))
                
                if len(odds_blocks) < 2:
                    self.logger.warning(f"Incomplete odds data for bookmaker: {bookmaker_name}. Skipping...")
                    continue

                odds_over = odds_blocks[0].get_text(strip=True)
                odds_under = odds_blocks[1].get_text(strip=True)
                odds_over = re.sub(r"(\d+\.\d+)\1", r"\1", odds_over)
                odds_under = re.sub(r"(\d+\.\d+)\1", r"\1", odds_under)
                
                odds_data.append({
                    "bookmaker_name": bookmaker_name, 
                    "odds_over": odds_over, 
                    "odds_under": odds_under,
                    "period": period
                })

            except:
                self.logger.error(f"Error parsing Over/Under odds for block: {e}")
                continue

        self.logger.info(f"Successfully parsed Over/Under odds: {odds_data}")
        return odds_data
        
    async def extract_odds(
        self, 
        market_name: str, 
        period: str = "FullTime", 
        odds_labels: list = []
    ) -> list:
        """
        Generic method to extract odds for a specified market.

        Args:
            market_name (str): The market tab name to navigate to.
            period (str): The match period for which to scrape odds.
            odds_labels (list): The labels for the odds being scraped (e.g., ['1X', '12', 'X2']).

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds for the specified market.
        """
        self.logger.info(f"Scraping {market_name} odds for period: {period}")

        # Navigate to the correct market tab
        if not await self.browser_helper.navigate_to_market_tab(page=self.page, market_tab_name=market_name, timeout=self.DEFAULT_TIMEOUT):
            self.logger.error(f"Failed to find or click {market_name} tab.")
            return []
        
        try:
            await self.page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
            html_content = await self.page.content()
            soup = BeautifulSoup(html_content, "lxml")

            bookmaker_rows = soup.find_all("div", class_=re.compile(r"border-black-borders.*flex.*h-9.*border-b.*border-l.*border-r.*text-xs"))

            if not bookmaker_rows:
                self.logger.error(f"No bookmaker rows found for {market_name} odds.")
                return []

            odds_data = []

            for row in bookmaker_rows:
                try:
                    bookmaker_name_element = row.find("p", class_="height-content")
                    bookmaker_name = bookmaker_name_element.text.strip() if bookmaker_name_element else "Unknown"
                    odds_containers = row.find_all("div", class_=re.compile(r"border-black-borders.*relative.*flex.*min-w-\[60px\].*flex-col.*items-center.*justify-center.*gap-1"))

                    if len(odds_containers) < len(odds_labels):
                        self.logger.warning(f"Insufficient {market_name} odds data for bookmaker: {bookmaker_name}. Skipping...")
                        continue

                    odds_info = {"bookmaker_name": bookmaker_name, "period": period}
                    
                    for idx, label in enumerate(odds_labels):
                        odds_element = odds_containers[idx].find("a", class_="min-mt:!flex") or odds_containers[idx].find("p", class_="height-content")
                        odds_value = odds_element.text.strip() if odds_element else None
                        
                        if not odds_value:
                            self.logger.warning(f"Missing odds value for {label} in bookmaker row {bookmaker_name}. Skipping...")
                            continue
                        
                        odds_info[label] = odds_value
                    
                    odds_data.append(odds_info)
                
                except Exception as row_error:
                    self.logger.error(f"Error processing row for {market_name}: {row_error}")
                    continue

            self.logger.info(f"Successfully extracted {market_name} odds for {len(odds_data)} bookmaker(s).")
            return odds_data
        
        except Exception as e:
            self.logger.error(f"Error scraping {market_name} odds: {e}")
            return []