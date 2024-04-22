import time, re
from logger import LOGGER
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementClickInterceptedException
from selenium import webdriver

class OddsPortalOddsExtractor:
    def __init__(self, driver):
        self.driver = driver
    
    def __scroll_to_element(self, by, identifier):
        try:
            element = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((by, identifier)))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        except TimeoutException:
            LOGGER.error("Element with {by}='{identifier}' not found within timeout period.")

    """ This method attempts to click an element based on its text content."""
    def __click_by_inner_text(self, selector: str, text: str) -> bool:
        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
        for element in elements:
            if text in element.text.replace("\n", "").replace(" ", ""):
                try:
                    element.click()
                    return True
                except ElementClickInterceptedException:
                    LOGGER.error(f"Element found with text '{text}' but click was intercepted.")
                    return False
                except Exception as e:
                    LOGGER.error(f"Error clicking element with text '{text}': {e}")
                    return False
        LOGGER.info(f"Element with text '{text}' not found.")
        return False
    
    def __click_by_text(self, selector: str, text: str) -> bool:
        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
        for element in elements:
            if text in element.text:
                element.click()
                return True
        return False
    
    def __select_over_under_market(self, selector: str, market_value: str) -> bool:
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, f"{selector} p")
            for element in elements:
                full_text_pattern = re.compile(fr"(Over/Under \+{market_value})|(O/U \+{market_value})")
                if full_text_pattern.search(element.text):
                    parent_div = element.find_element(By.XPATH, "./..")
                    ## TODO: Testing purposes: self.__scroll_to_element()
                    parent_div.click()
                    return True
            LOGGER.info(f"No matching element found for market_value: {market_value}")
            return False
        except Exception as e:
            LOGGER.error(f"Error while attempting to select desired over under market {market_value}: {e}")
            return False
    
    """Selects the match period based on the provided period string."""
    def __select_match_period(self, period: str):
        match_period_button_selector = "div[data-testid='kickoff-events-nav'] > div"
        try:
            WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, match_period_button_selector)))
            cleaned_period = period.replace("\n", "").replace(" ", "")
            if not self.__click_by_inner_text(match_period_button_selector, cleaned_period):
                LOGGER.error(f"Button with match period: {period} not found or could not be clicked.")
        except TimeoutException:
            LOGGER.error(f"Timed out waiting for match period button to become clickable: {period}")
    
    """Extracts 1X2 odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
    def extract_1X2_odds(self, period: str):
        LOGGER.info(f"Scraping odds for 1x2 for period: {period}")
        ## TODO: assume that "FullTime" is selected - call __select_match_period only if {period} is not already selected
        #self.__select_match_period(period=period)
        bookmaker_rows_selector = "div.border-black-borders.flex.h-9.border-b.border-l.border-r.text-xs"     
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, bookmaker_rows_selector)))
        bookmaker_rows = self.driver.find_elements(By.CSS_SELECTOR, bookmaker_rows_selector)
        odds_data = []

        for row in bookmaker_rows:
            try:
                p_elements = row.find_elements(By.TAG_NAME, "p")
                if len(p_elements) >= 4:
                    bookmaker_name, hw, d, aw = [p.text for p in p_elements[:4]]
                    odds_data.append({"bookMakerName": bookmaker_name, "homeWin": hw, "draw": d, "awayWin": aw})
            except Exception as e:
                LOGGER.error(f"Error extracting odds data from row: {e}")
                continue
        return odds_data
    
    """Extract Over/Under odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
    def extract_over_under_odds(self, over_under_type_chosen: str, period: str):
        ## TODO: assume that "FullTime" is selected - call __select_match_period only if {period} is not already selected
        #self.__select_match_period(period=period)
        time.sleep(2)
        LOGGER.info(f"Scraping odds for under/over {over_under_type_chosen}")
        markets_scrollbar_selector = 'ul.visible-links.bg-black-main.odds-tabs > li'
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, markets_scrollbar_selector)))
        
        if not self.__click_by_text(markets_scrollbar_selector, 'Over/Under'):
            raise Exception("Over/Under tab not found or couldn't be clicked.")
        
        time.sleep(2)
        self.driver.execute_script("window.scrollBy(0, 400);")
        time.sleep(2)
        options_selector = 'div.flex.w-full.items-center.justify-start.pl-3.font-bold'
        if not self.__select_over_under_market(options_selector, over_under_type_chosen):
            raise Exception(f"Option {over_under_type_chosen} not found or couldn't be clicked.")

        time.sleep(2)
        rows_selector = 'div[data-v-59b97132].border-black-borders'
        rows = self.driver.find_elements(By.CSS_SELECTOR, rows_selector)
        data = []
        for row in rows:
            bookmaker_name = row.find_element(By.CSS_SELECTOR, 'a > p').text.strip() if row.find_elements(By.CSS_SELECTOR, 'a > p') else 'Unknown'
            odds_elements = row.find_elements(By.CSS_SELECTOR, 'div.flex-center.font-bold > div > p.height-content')
            odds_over = odds_elements[0].text.strip() if len(odds_elements) > 0 else 'N/A'
            odds_under = odds_elements[1].text.strip() if len(odds_elements) > 1 else 'N/A'
            
            if bookmaker_name != 'Unknown' and odds_over != 'N/A' and odds_under != 'N/A':
                data.append({"bookmakerName": bookmaker_name, "oddsOver": odds_over, "oddsUnder": odds_under})
        return data
    
    """Extract Double Chance odds for the specified period (FullTime, 1stHalf, 2ndHalf)."""
    def extract_double_chance_odds(self, period: str):
        print("WORK IN PROGRESS - scrape 1X, X2, etc..")
        ## Select double chance in scrollbar - Scrape bookmaker odds for 1X, X2, 12