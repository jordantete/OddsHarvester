import re, asyncio
from logger import LOGGER
from playwright.async_api import TimeoutError
from bs4 import BeautifulSoup

class OddsPortalOddsExtractor:
    def __init__(self, page):
        self.page = page

    """ This method attempts to click an element based on its text content."""
    async def __click_by_inner_text(self, selector: str, text: str) -> bool:
        try:
            cleaned_text = ''.join(text.split())
            elements = await self.page.query_selector_all(f'xpath=//{selector}[contains(text(), "{cleaned_text}")]')

            if not elements:
                LOGGER.info(f"Element with text '{text}' not found.")
                return False

            for element in elements:
                if ''.join(await element.text_content().split()) == cleaned_text:
                    await element.click()
                    return True

        except Exception as e:
            LOGGER.error(f"Error clicking element with text '{text}': {e}")
            return False
        
        LOGGER.info(f"Element with text '{text}' not found.")
        return False

    async def __click_by_text(self, selector: str, text: str) -> bool:
        elements = await self.page.query_selector_all(selector)
        for element in elements:
            element_text = await element.text_content()
            if element_text and text in element_text:
                await element.click()
                return True
        return False
    
    async def __can_select_over_under_market(self, selector: str, market_value: str) -> bool:
        LOGGER.info(f"__can_select_over_under_market with selector: {selector} and market_value: {market_value}")
        try:
            await self.page.wait_for_selector(f"{selector} p", timeout=5000)
            elements = await self.page.query_selector_all(f"{selector} p")
            LOGGER.info(f"__can_select_over_under_market number of elements found: {len(elements)}")
            for element in elements:
                LOGGER.info(f"__can_select_over_under_market element text_content: {await element.text_content()}")
                full_text_pattern = re.compile(fr"(Over/Under \+{market_value})|(O/U \+{market_value})")
                if full_text_pattern.search(await element.text_content()):
                    parent_div = await element.evaluate_handle("element => element.parentElement")
                    await parent_div.click()
                    return True
            LOGGER.warn(f"No matching element found for market_value: {market_value}")
            return False
        except Exception as e:
            LOGGER.error(f"Error while attempting to select desired over under market {market_value}: {e}")
            return False
    
    """Selects the match period based on the provided period string."""
    async def __select_match_period(self, period: str):
        LOGGER.info(f"Will select match period: {period}")
        match_period_button_selector = "div[data-testid='kickoff-events-nav'] > div"
        cleaned_period = period.replace("\n", "").replace(" ", "")
        try:
            button = await self.page.wait_for_selector(match_period_button_selector, state="visible", timeout=5000)
            if not await self.__click_by_inner_text(match_period_button_selector, cleaned_period):
                LOGGER.error(f"Button with match period: {period} not found or could not be clicked.")
        except TimeoutError:
            LOGGER.error(f"Timed out waiting for match period button to become clickable: {period}")
    
    """Extracts 1X2 odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
    async def extract_1X2_odds(self, period: str):
        LOGGER.info(f"Scraping odds for 1x2 for period: {period}")
        odds_data = []
        ## TODO: assume that "FullTime" is selected - call __select_match_period only if {period} is not already selected
        #await self.__select_match_period(period=period)
        bookmaker_rows_selector = "div.border-black-borders.flex.h-9.border-b.border-l.border-r.text-xs"
        await self.page.wait_for_selector(bookmaker_rows_selector, state="attached", timeout=10000)
        bookmaker_rows = await self.page.query_selector_all(bookmaker_rows_selector)

        if not bookmaker_rows:
            LOGGER.info(f"Failed to find bookmaker rows elements using all bookmaker_rows_selector {bookmaker_rows_selector}")
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
                LOGGER.error(f"Error extracting odds data from row: {e}")
                continue
        LOGGER.info(f"Successfully fetch 1x2 odds_data: {odds_data}")
        return odds_data
    
    async def __extract_bookmakers_and_over_under_odds(self, html_content):
        soup = BeautifulSoup(html_content, 'lxml')
        bookmaker_blocks = soup.find_all('div', attrs={'class': re.compile(r'^border-black-borders flex h-9')})
        if not bookmaker_blocks:
            LOGGER.warn("No bookmaker_blocks found, check class names and HTML structure")
            return []

        odds_data = []
        for block in bookmaker_blocks:
            img_tag = block.find('img', class_="bookmaker-logo")
            bookmaker_name = img_tag['title'] if img_tag and 'title' in img_tag.attrs else 'Unknown'
            odds_blocks = block.find_all('div', class_=re.compile(r'flex-center.*flex-col.*font-bold'))

            if not odds_blocks:
                LOGGER.warn("No odds_blocks found, check class names and HTML structure")
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
        LOGGER.info(f"Successfully fetch over/under odds_data: {odds_data}")
        return odds_data
    
    """Extract Over/Under odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
    async def extract_over_under_odds(self, over_under_type_chosen: str, period: str):
        #await self.__select_match_period(period=period) ## assume that "FullTime" is selected - call __select_match_period only if {period} is not already selected
        LOGGER.info(f"Scraping odds for under/over {over_under_type_chosen}")
        markets_scrollbar_selector = 'ul.visible-links.bg-black-main.odds-tabs > li'
        await self.page.wait_for_selector(markets_scrollbar_selector, state="visible")
        
        if not await self.__click_by_text(markets_scrollbar_selector, 'Over/Under'):
            LOGGER.error("Over/Under tab not found or couldn't be clicked.")
            return []
        
        await self.page.wait_for_timeout(2000)
        await self.page.evaluate("window.scrollBy(0, 500);") # Scroll verticaly to reach Over selector row
        await self.page.wait_for_timeout(2000)

        over_under_options_selector = 'div.flex.w-full.items-center.justify-start.pl-3.font-bold'
        if not await self.__can_select_over_under_market(over_under_options_selector, over_under_type_chosen):
            LOGGER.error(f"Option {over_under_type_chosen} not found or couldn't be clicked.")
            return []

        await self.page.wait_for_timeout(2000)
        html_content = await self.page.content()
        odds_data = await self.__extract_bookmakers_and_over_under_odds(html_content=html_content)
        return odds_data
    
    """Extract Double Chance odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
    async def extract_double_chance_odds(self, period: str):
        print("WORK IN PROGRESS - scrape 1X, X2, etc..")
        ## Select double chance in scrollbar - Scrape bookmaker odds for 1X, X2, 12