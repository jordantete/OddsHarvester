import re, logging
from playwright.async_api import Page, TimeoutError
from bs4 import BeautifulSoup
from src.core.browser_helper import BrowserHelper

class OddsPortalMarketExtractor:
    """
    Extracts betting odds data from OddsPortal using Playwright.

    This class provides methods to scrape various betting markets (e.g., 1X2, Over/Under)
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
    
    async def extract_1X2_odds(
        self, 
        period: str = "FullTime"
    ) -> list:
        """
        Extracts 1X2 odds for the specified period (e.g., FullTime, 1stHalf, 2ndHalf).

        Args:
            period (str): The match period to scrape odds for.

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds.
        """
        self.logger.info(f"Scraping odds for 1x2 for period: {period}")
        odds_data = []
        bookmaker_rows_selector = "div.border-black-borders.flex.h-9.border-b.border-l.border-r.text-xs"

        try:
            await self.page.wait_for_selector(bookmaker_rows_selector, state="attached", timeout=self.DEFAULT_TIMEOUT)
            bookmaker_rows = await self.page.query_selector_all(bookmaker_rows_selector)

            if not bookmaker_rows:
                self.logger.warning(f"No bookmaker rows found for period {period}. Selector: {bookmaker_rows_selector}")
                return odds_data

            for row in bookmaker_rows:
                try:
                    p_elements = await row.query_selector_all("p")
                    if len(p_elements) < 4:
                        self.logger.warning("Incomplete data found in bookmaker row. Skipping...")
                        continue

                    texts = [await p.inner_text() for p in p_elements[:4]]
                    bookmaker_name, hw, d, aw = texts

                    if not bookmaker_name or not hw or not d or not aw:
                        self.logger.warning(f"Missing data in row: {texts}. Skipping...")
                        continue

                    odds_data.append({
                        "bookMakerName": bookmaker_name.strip(),
                        "homeWin": hw.strip(),
                        "draw": d.strip(),
                        "awayWin": aw.strip(),
                    })

                except Exception as row_error:
                    self.logger.error(f"Error extracting odds data from row: {row_error}")
                    continue

            self.logger.info(f"Successfully extracted 1X2 odds: {len(odds_data)} rows.")
            return odds_data
        
        except TimeoutError:
            self.logger.error(f"Timed out waiting for bookmaker rows for period {period}")
            return []
        
        except Exception as e:
            self.logger.error(f"Unexpected error during 1X2 odds extraction: {e}")
            return []
    
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
        markets_tab_selector = 'ul.visible-links.bg-black-main.odds-tabs > li'

        # Navigate to Over/Under tab
        if not await self.browser_helper.wait_and_click(page=self.page, selector=markets_tab_selector, text='Over/Under', timeout=self.DEFAULT_TIMEOUT):
            self.logger.error("Failed to find or click Over/Under tab.")
            return []
        
        await self.page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
        await self.page.evaluate("window.scrollBy(0, 500);") # Scroll verticaly to reach Over selector row

        over_under_option_selector = 'div.flex.w-full.items-center.justify-start.pl-3.font-bold'
        
        if not await self._click_over_under_option(selector=over_under_option_selector, market_value=over_under_market):
            self.logger.error(f"Over/Under {over_under_market} not found or couldn't be selected.")
            return []
        
        await self.page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
        html_content = await self.page.content()
        return await self._parse_over_under_odds(html_content=html_content)

    async def _click_over_under_option(
        self, 
        selector: str, 
        market_value: str
    ) -> bool:
        """
        Attempts to click a specific Over/Under market option.

        Args:
            selector (str): The CSS selector for the market options container.
            market_value (str): The value of the Over/Under market to select.

        Returns:
            bool: True if the option was clicked successfully, False otherwise.
        """
        self.logger.info(f"Selecting Over/Under market: {market_value}")
        try:
            elements = await self.page.query_selector_all(f"{selector} p")

            for element in elements:
                text_content = await element.text_content()

                if re.search(fr"(Over/Under \+{market_value})|(O/U \+{market_value})", text_content or ""):
                    parent_div = await element.evaluate_handle("element => element.parentElement")
                    await parent_div.click()
                    return True
                
            self.logger.warning(f"No matching Over/Under market found for value: {market_value}")
            return False
        
        except Exception as e:
            self.logger.error(f"Error selecting Over/Under market {market_value}: {e}")
            return False
    
    async def _parse_over_under_odds(
        self, 
        html_content: str
    ) -> list:
        """
        Parses Over/Under odds data from the page's HTML content.

        Args:
            html_content (str): The HTML content of the page.

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
            img_tag = block.find("img", class_="bookmaker-logo")
            bookmaker_name = img_tag["title"] if img_tag and "title" in img_tag.attrs else "Unknown"
            odds_blocks = block.find_all("div", class_=re.compile(r"flex-center.*flex-col.*font-bold"))

            if len(odds_blocks) >= 2:
                odds_over = odds_blocks[0].get_text(strip=True)
                odds_under = odds_blocks[1].get_text(strip=True)
                odds_data.append({"bookmakerName": bookmaker_name, "oddsOver": odds_over, "oddsUnder": odds_under})

        self.logger.info(f"Successfully parsed Over/Under odds: {odds_data}")
        return odds_data
        
    async def extract_double_chance_odds(self, period: str = "FullTime"):
        """Placeholder for scraping double chance odds."""
        raise NotImplementedError("The method extract_double_chance_odds is not implemented.")

    async def extract_btts_odds(self, period: str = "FullTime"):
        """Placeholder for scraping Both Teams To Score (BTTS) odds."""
        raise NotImplementedError("The method extract_btts_odds is not implemented.")