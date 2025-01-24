import re, logging
from playwright.async_api import Page, TimeoutError
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
        self.logger.info(f"Scraping odds for 1X2 market, period: {period}")
        odds_data = []
        bookmaker_rows_selector = "div.border-black-borders.flex.h-9.border-b.border-l.border-r.text-xs"

        try:
            self.logger.info(f"Waiting for bookmaker rows using selector: {bookmaker_rows_selector}")
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
                    bookmaker_name, home_win_odd, draw_odd, away_win_odd = texts

                    if not bookmaker_name or not home_win_odd or not draw_odd or not away_win_odd:
                        self.logger.warning(f"Missing data in row: {texts}. Skipping...")
                        continue

                    odds_data.append({
                        "bookmaker_name": bookmaker_name.strip(),
                        "home_win_odd": home_win_odd.strip(),
                        "draw_odd": draw_odd.strip(),
                        "away_win_odd": away_win_odd.strip(),
                        "period": period,
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
        
    async def extract_double_chance_odds(
        self, 
        period: str = "FullTime"
    ) -> list:
        """
        Extract Double Chance odds for the specified period (e.g., FullTime, 1stHalf).

        Args:
            period (str): The match period for which to scrape Double Chance odds.

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds for the Double Chance market.

        This method navigates to the Double Chance market tab, extracts odds for the 1X, 12, and X2 markets 
        from each bookmaker, and returns them in a structured format. If no odds data is found or an error 
        occurs, an empty list is returned. The method also logs warnings and errors for missing data or 
        unexpected issues.
        """
        self.logger.info(f"Scraping Double Chance odds for period: {period}")

        if not await self.browser_helper.navigate_to_market_tab(page=self.page, market_tab_name='Double Chance', timeout=self.DEFAULT_TIMEOUT):
            self.logger.error("Failed to find or click Double Chance tab.")
            return {}
        
        try:
            await self.page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
            html_content = await self.page.content()
            soup = BeautifulSoup(html_content, "lxml")
            bookmaker_rows = soup.find_all("div", class_=re.compile(r"border-black-borders.*flex.*h-9.*border-b.*border-l.*border-r"))
            results = []

            for row in bookmaker_rows:
                bookmaker_container = row.find("div", class_=re.compile(r"min-ms:!justify-start.*flex.*items-center.*justify-center"))
                bookmaker_name = "Unknown"

                if bookmaker_container:
                    bookmaker_name_element = bookmaker_container.find("p", class_="height-content")
                    bookmaker_name = bookmaker_name_element.text.strip() if bookmaker_name_element else "Unknown"

                odds_containers = row.find_all("div", class_=re.compile(r"border-black-borders.*flex.*min-w-\[60px\].*flex-col.*items-center.*justify-center.*gap-1.*border-l"))
                odds_labels = ["1X", "12", "X2"]
                odds_data = {
                    "bookmaker_name": bookmaker_name, 
                    "period:": period
                }

                for idx, label in enumerate(odds_labels):
                    if idx >= len(odds_containers):
                        self.logger.warning(f"Missing odds container for {label} in bookmaker row {bookmaker_name}. Skipping...")
                        continue

                    odds_element = odds_containers[idx].find("p", class_=re.compile(r"height-content"))
                    if not odds_element:
                        odds_element = odds_containers[idx].find("a", class_=re.compile(r".*underline.*"))  # Check for <a> tags with underline

                    odds_value = odds_element.text.strip() if odds_element else None

                    if not odds_value:
                        self.logger.warning(f"Missing odds value for {label} in bookmaker row {bookmaker_name}. Skipping...")
                        continue

                    odds_data[label] = odds_value

                results.append(odds_data)

            self.logger.info(f"Successfully extracted Double Chance odds for multiple rows: {results}")
            return results

        except Exception as e:
            self.logger.error(f"Error scraping Double Chance odds: {e}")
            return {}

    async def extract_btts_odds(
        self,
        period: str = "FullTime"
    ) -> list:
        """
        Extract BTTS (Both Teams to Score) odds for the specified period (e.g., FullTime, 1stHalf).

        Args:
            period (str): The match period for which to scrape BTTS odds.

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds for BTTS Yes/No.

        This method navigates to the BTTS (Both Teams to Score) market tab, extracts the odds for the "Yes" 
        and "No" outcomes for each bookmaker, and returns them in a structured format. If no odds data is 
        found or an error occurs, an empty list is returned. It handles cases where odds are contained in 
        either <p> or <a> tags and logs missing or incomplete data.
        """
        self.logger.info(f"Scraping BTTS odds for period: {period}")
        
        if not await self.browser_helper.navigate_to_market_tab(page=self.page, market_tab_name='Both Teams to Score', timeout=self.DEFAULT_TIMEOUT):
            self.logger.error("Failed to find or click BTTS tab.")
            return []
        
        try:
            await self.page.wait_for_timeout(self.SCROLL_PAUSE_TIME)
            html_content = await self.page.content()
            soup = BeautifulSoup(html_content, "lxml")

            bookmaker_rows = soup.find_all("div", class_=re.compile(r"border-black-borders.*flex.*h-9.*border-b.*border-l.*border-r.*text-xs"))

            if not bookmaker_rows:
                self.logger.error("No bookmaker rows found for BTTS odds.")
                return []

            btts_odds_data = []

            for row in bookmaker_rows:
                try:
                    bookmaker_name_element = row.find("p", class_="height-content")
                    bookmaker_name = bookmaker_name_element.text.strip() if bookmaker_name_element else "Unknown"
                    odds_containers = row.find_all("div", class_=re.compile(r"border-black-borders.*relative.*flex.*min-w-\[60px\].*flex-col.*items-center.*justify-center.*gap-1"))

                    if len(odds_containers) < 2:
                        self.logger.warning(f"Insufficient BTTS odds data for bookmaker: {bookmaker_name}. Skipping...")
                        continue

                    # Attempt to extract BTTS Yes and No odds from <a> tags first, fallback to <p> tags if not present
                    btts_yes_element = odds_containers[0].find("a", class_="min-mt:!flex") or odds_containers[0].find("p", class_="height-content")
                    btts_no_element = odds_containers[1].find("a", class_="min-mt:!flex") or odds_containers[1].find("p", class_="height-content")

                    btts_yes = btts_yes_element.text.strip() if btts_yes_element else None
                    btts_no = btts_no_element.text.strip() if btts_no_element else None

                    if not btts_yes or not btts_no:
                        self.logger.warning(f"Missing BTTS odds for bookmaker: {bookmaker_name}. Skipping...")
                        continue

                    btts_odds_data.append({
                        "bookmaker_name": bookmaker_name,
                        "btts_yes": btts_yes,
                        "btts_no": btts_no,
                        "period": period
                    })

                except Exception as row_error:
                    self.logger.error(f"Error processing row: {row_error}")
                    continue

            self.logger.info(f"Successfully extracted BTTS odds for {len(btts_odds_data)} bookmaker(s).")
            return btts_odds_data

        except Exception as e:
            self.logger.error(f"Error scraping BTTS odds: {e}")
            return []