import time, re
from logger import LOGGER
from playwright.sync_api import TimeoutError

class OddsPortalOddsExtractor:
    def __init__(self, page):
        self.page = page

    """ This method attempts to click an element based on its text content."""
    def __click_by_inner_text(self, selector: str, text: str) -> bool:
        try:
            # Use XPath to find elements that contain the text after cleaning whitespace and newlines
            cleaned_text = ''.join(text.split())
            elements = self.page.query_selector_all(f'xpath=//{selector}[contains(text(), "{cleaned_text}")]')

            if not elements:
                LOGGER.info(f"Element with text '{text}' not found.")
                return False

            for element in elements:
                if ''.join(element.text_content().split()) == cleaned_text:
                    element.click()
                    return True

        except Exception as e:
            LOGGER.error(f"Error clicking element with text '{text}': {e}")
            return False
        
        LOGGER.info(f"Element with text '{text}' not found.")
        return False

    def __click_by_text(self, selector: str, text: str) -> bool:
        elements = self.page.query_selector_all(selector)
        for element in elements:
            element_text = element.text_content()
            if element_text and text in element_text:
                element.click()
                return True
        return False
    
    def __can_select_over_under_market(self, selector: str, market_value: str) -> bool:
        try:
            elements = self.page.query_selector_all(f"{selector} p")
            for element in elements:
                full_text_pattern = re.compile(fr"(Over/Under \+{market_value})|(O/U \+{market_value})")
                if full_text_pattern.search(element.text_content()):
                    parent_div = element.evaluate_handle("element => element.parentElement")
                    parent_div.click()
                    return True
            LOGGER.info(f"No matching element found for market_value: {market_value}")
            return False
        except Exception as e:
            LOGGER.error(f"Error while attempting to select desired over under market {market_value}: {e}")
            return False
    
    """Selects the match period based on the provided period string."""
    def __select_match_period(self, period: str):
        LOGGER.info(f"Will select match period: {period}")
        match_period_button_selector = "div[data-testid='kickoff-events-nav'] > div"
        cleaned_period = period.replace("\n", "").replace(" ", "")
        try:
            button = self.page.wait_for_selector(match_period_button_selector, state="visible", timeout=5000)
            if not self.__click_by_inner_text(match_period_button_selector, cleaned_period):
                LOGGER.error(f"Button with match period: {period} not found or could not be clicked.")
        except TimeoutError:
            LOGGER.error(f"Timed out waiting for match period button to become clickable: {period}")
    
    """Extracts 1X2 odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
    def extract_1X2_odds(self, period: str):
        LOGGER.info(f"Scraping odds for 1x2 for period: {period}")
        odds_data = []
        ## TODO: assume that "FullTime" is selected - call __select_match_period only if {period} is not already selected
        #self.__select_match_period(period=period)
        bookmaker_rows_selector = "div.border-black-borders.flex.h-9.border-b.border-l.border-r.text-xs"
        self.page.wait_for_selector(bookmaker_rows_selector, state="attached", timeout=10000)
        bookmaker_rows = self.page.query_selector_all(bookmaker_rows_selector)

        if not bookmaker_rows:
            LOGGER.info(f"Failed to find bookmaker rows elements using all bookmaker_rows_selector {bookmaker_rows_selector}")
            return odds_data

        for row in bookmaker_rows:
            try:
                p_elements = row.query_selector_all("p")
                if len(p_elements) >= 4:
                    bookmaker_name, hw, d, aw = [p.inner_text() for p in p_elements[:4]]
                    odds_data.append({"bookMakerName": bookmaker_name, "homeWin": hw, "draw": d, "awayWin": aw})
            except Exception as e:
                LOGGER.error(f"Error extracting odds data from row: {e}")
                continue
        return odds_data
    
    """Extract Over/Under odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
    def extract_over_under_odds(self, over_under_type_chosen: str, period: str):
        ## TODO: assume that "FullTime" is selected - call __select_match_period only if {period} is not already selected
        #self.__select_match_period(period=period)
        LOGGER.info(f"Scraping odds for under/over {over_under_type_chosen}")
        markets_scrollbar_selector = 'ul.visible-links.bg-black-main.odds-tabs > li'
        self.page.wait_for_selector(markets_scrollbar_selector, state="visible")
        
        if not self.__click_by_text(markets_scrollbar_selector, 'Over/Under'):
            raise Exception("Over/Under tab not found or couldn't be clicked.")
        
        self.page.wait_for_timeout(2000)
        self.page.evaluate("window.scrollBy(0, 500);") # Scroll verticaly to reach Over selector row
        self.page.wait_for_timeout(2000)

        options_selector = 'div.flex.w-full.items-center.justify-start.pl-3.font-bold'
        if not self.__can_select_over_under_market(options_selector, over_under_type_chosen):
            raise Exception(f"Option {over_under_type_chosen} not found or couldn't be clicked.")

        self.page.wait_for_timeout(2000)
        odds_data = []
        rows_selector = 'div[data-v-3d9d04c2].border-black-borders'
        #rows_selector = 'div:has-text("Bookmakers")' # find a way to not make use of id which changes frequently

        rows = self.page.query_selector_all(rows_selector)    

        if not rows:
            LOGGER.info(f"Failed to find bookmaker rows elements using all rows_selector {rows_selector}")
            return odds_data

        for row in rows:
            bookmaker_name = row.query_selector('a > p').text_content().strip() if row.query_selector('a > p') else 'Unknown'
            odds_elements = row.query_selector_all('div.flex-center.font-bold > div > p.height-content')
            odds_over = odds_elements[0].text_content().strip() if len(odds_elements) > 0 else 'N/A'
            odds_under = odds_elements[1].text_content().strip() if len(odds_elements) > 1 else 'N/A'
            
            if bookmaker_name != 'Unknown' and odds_over != 'N/A' and odds_under != 'N/A' and bookmaker_name not in odds_data:
                odds_data.append({"bookmakerName": bookmaker_name, "oddsOver": odds_over, "oddsUnder": odds_under})
        return odds_data
    
    """Extract Double Chance odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
    def extract_double_chance_odds(self, period: str):
        print("WORK IN PROGRESS - scrape 1X, X2, etc..")
        ## Select double chance in scrollbar - Scrape bookmaker odds for 1X, X2, 12