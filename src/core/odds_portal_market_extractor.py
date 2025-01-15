import re, logging
from playwright.async_api import Page, TimeoutError
from bs4 import BeautifulSoup
from src.core.browser_helper import BrowserHelper

class OddsPortalMarketExtractor:
    def __init__(
        self, 
        page: Page,
        browser_helper: BrowserHelper
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.page = page
        self.browser_helper = browser_helper

    async def __can_select_over_under_market(self, selector: str, market_value: str) -> bool:
        self.logger.info(f"__can_select_over_under_market with selector: {selector} and market_value: {market_value}")
        
        try:
            await self.page.wait_for_selector(f"{selector} p", timeout=5000)
            elements = await self.page.query_selector_all(f"{selector} p")
            self.logger.info(f"__can_select_over_under_market number of elements found: {len(elements)}")

            for element in elements:
                self.logger.info(f"__can_select_over_under_market element text_content: {await element.text_content()}")
                full_text_pattern = re.compile(fr"(Over/Under \+{market_value})|(O/U \+{market_value})")

                if full_text_pattern.search(await element.text_content()):
                    parent_div = await element.evaluate_handle("element => element.parentElement")
                    await parent_div.click()
                    return True
                
            self.logger.warning(f"No matching element found for market_value: {market_value}")
            return False
        
        except Exception as e:
            self.logger.error(f"Error while attempting to select desired over under market {market_value}: {e}")
            return False
    
    """Selects the match period based on the provided period string."""
    async def __select_match_period(self, period: str):
        self.logger.info(f"Will select match period: {period}")
        match_period_button_selector = "div[data-testid='kickoff-events-nav'] > div"
        cleaned_period = period.replace("\n", "").replace(" ", "")
        try:
            button = await self.page.wait_for_selector(match_period_button_selector, state="visible", timeout=5000)
            
            if not await self.browser_helper.click_by_inner_text(page=self.page, selector=match_period_button_selector, text=cleaned_period):
                self.logger.error(f"Button with match period: {period} not found or could not be clicked.")
        
        except TimeoutError:
            self.logger.error(f"Timed out waiting for match period button to become clickable: {period}")
    
    async def extract_1X2_odds(self, period: str):
        """Extracts 1X2 odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
        self.logger.info(f"Scraping odds for 1x2 for period: {period}")
        odds_data = []
        ## TODO: assume that "FullTime" is selected - call __select_match_period only if {period} is not already selected
        #await self.__select_match_period(period=period)
        bookmaker_rows_selector = "div.border-black-borders.flex.h-9.border-b.border-l.border-r.text-xs"
        await self.page.wait_for_selector(bookmaker_rows_selector, state="attached", timeout=10000)
        bookmaker_rows = await self.page.query_selector_all(bookmaker_rows_selector)

        if not bookmaker_rows:
            self.logger.info(f"Failed to find bookmaker rows elements using all bookmaker_rows_selector {bookmaker_rows_selector}")
            return odds_data

        for row in bookmaker_rows:
            try:
                p_elements = await row.query_selector_all("p")
                if len(p_elements) >= 4:
                    texts = []
                    for p in p_elements[:4]:
                        text = await p.inner_text()
                        texts.append(text)
                    bookmaker_name, hw, d, aw = texts
                    # bookmaker_name, hw, d, aw = [await p.inner_text() for p in p_elements[:4]]
                    odds_data.append({"bookMakerName": bookmaker_name, "homeWin": hw, "draw": d, "awayWin": aw})
            
            except Exception as e:
                self.logger.error(f"Error extracting odds data from row: {e}")
                continue
        
        self.logger.info(f"Successfully fetch 1x2 odds_data: {odds_data}")
        return odds_data
    
    async def __extract_bookmakers_and_over_under_odds(self, html_content):
        soup = BeautifulSoup(html_content, 'lxml')
        bookmaker_blocks = soup.find_all('div', attrs={'class': re.compile(r'^border-black-borders flex h-9')})
        
        if not bookmaker_blocks:
            self.logger.warning("No bookmaker_blocks found, check class names and HTML structure")
            return []

        odds_data = []
        for block in bookmaker_blocks:
            img_tag = block.find('img', class_="bookmaker-logo")
            bookmaker_name = img_tag['title'] if img_tag and 'title' in img_tag.attrs else 'Unknown'
            odds_blocks = block.find_all('div', class_=re.compile(r'flex-center.*flex-col.*font-bold'))

            if not odds_blocks:
                self.logger.warning("No odds_blocks found, check class names and HTML structure")
                return []

            odds_over = 'N/A'
            odds_under = 'N/A'
            for idx, odds_block in enumerate(odds_blocks):
                p_tags = odds_block.find_all('p')
                if p_tags:
                    if idx == 0:  # Assuming the first block contains 'over' odds
                        odds_over = p_tags[0].text.strip()
                    elif idx == 1:  # Assuming the second block contains 'under' odds
                        odds_under = p_tags[0].text.strip()

            if bookmaker_name != 'Unknown' and odds_over != 'N/A' and odds_under != 'N/A':
                odds_data.append({"bookmakerName": bookmaker_name, "oddsOver": odds_over, "oddsUnder": odds_under})
        
        self.logger.info(f"Successfully fetch over/under odds_data: {odds_data}")
        return odds_data
    
    async def extract_over_under_odds(self, over_under_type_chosen: str, period: str):
        """Extract Over/Under odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
        #await self.__select_match_period(period=period) ## assume that "FullTime" is selected - call __select_match_period only if {period} is not already selected
        self.logger.info(f"Scraping odds for under/over {over_under_type_chosen}")
        markets_scrollbar_selector = 'ul.visible-links.bg-black-main.odds-tabs > li'
        await self.page.wait_for_selector(markets_scrollbar_selector, state="visible")
        
        if not await self.browser_helper.click_by_text(page=self.page, selector=markets_scrollbar_selector, text='Over/Under'):
            self.logger.error("Over/Under tab not found or couldn't be clicked.")
            return []
        
        await self.page.wait_for_timeout(2000)
        await self.page.evaluate("window.scrollBy(0, 500);") # Scroll verticaly to reach Over selector row
        await self.page.wait_for_timeout(2000)

        over_under_options_selector = 'div.flex.w-full.items-center.justify-start.pl-3.font-bold'
        
        if not await self.__can_select_over_under_market(over_under_options_selector, over_under_type_chosen):
            self.logger.error(f"Option {over_under_type_chosen} not found or couldn't be clicked.")
            return []

        await self.page.wait_for_timeout(2000)
        html_content = await self.page.content()
        odds_data = await self.__extract_bookmakers_and_over_under_odds(html_content=html_content)
        return odds_data
    
    async def extract_double_chance_odds(self, period: str):
        self.logger("WORK IN PROGRESS - scrape 1X, X2, etc..")
        ## Select double chance in scrollbar - Scrape bookmaker odds for 1X, X2, 12