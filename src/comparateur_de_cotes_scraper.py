import re, os, csv
from logger import LOGGER
from utils import FRENCH_ODDS_SCRAPPER_LEAGUE_URLS_MAPPING
from bs4 import BeautifulSoup

SAVED_HTML_FILE_PATH = "page_content.html"
ODDS_OUTPUT_FILE = 'french_bookmaker_odds.csv'

class FrenchOddsScrapper:
    def __init__(self, league: str, should_use_saved_html_file: bool = True):
        LOGGER.info(f"Initialize FrenchOddsScrapper - league: {league}")
        self.league = league
        self.should_use_saved_html_file = should_use_saved_html_file
        self.__initialize_webdriver()

    def __initialize_webdriver(self):
        playwright = sync_playwright().start()
        browser_args = [
            '--window-size=1800,2500',
            "--full-memory-crash-report",
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            "--disable-gpu",
            '--use-gl=egl'
        ]
        self.browser = playwright.chromium.launch(headless=True, args=browser_args)
        context = self.browser.new_context(ignore_https_errors=True, permissions=['notifications'],)
        self.page = context.new_page()
    
    # def __read_html_file(self, file_path):
    #     with open(file_path, 'r', encoding='utf-8') as file:
    #         html_content = file.read()
    #         return html_content
    
    # def __save_html_file(self, file_path, html_content):
    #     with open(file_path, 'w', encoding='utf-8') as file:
    #         file.write(html_content)
    
    # def __extract_team_names_and_date(self, match_block):
    #     LOGGER.info(f"Will extract match informations")
    #     team_names_and_date = {}        
    #     match_name_div = match_block.find('h2', class_='matchname')
    #     if match_name_div:
    #         teams = re.split(r'\s*-\s*', match_name_div.get_text(strip=True))
    #         if len(teams) == 2:
    #             team_names_and_date['home_team'], team_names_and_date['away_team'] = teams
    #         else:
    #             LOGGER.warn(f"Unable to parse team names - please check teams = {teams}")
        
    #     parent_container = match_name_div.find_parent('td') if match_name_div else None
    #     if parent_container:
    #         date_text = parent_container.find(text=re.compile(r'\b\d{1,2}\s+\w+\s+\d{4}\b'))
    #         if date_text:
    #             team_names_and_date['date'] = date_text.strip()
    #         else:
    #             LOGGER.warn(f"Unable to parse match date - please check date_text = {date_text}")
    #     return team_names_and_date
    
    # def __extract_bookmaker_odds(self, match_block):
    #     LOGGER.info("Will extract bookmaker odds")
    #     odds = []
    #     next_rows = match_block.find_next_siblings('tr')

    #     for row in next_rows:
    #         if row.get('style') == "background-color:white":
    #             break
    #         img_src = row.find('img').get('src', '')
    #         bookmaker_name_raw = img_src.split('/')[-1].split('.')[0] if img_src else 'Unknown'
    #         bookmaker_name = bookmaker_name_raw.replace("logop-", "")
    #         odds_values = [td.get_text(strip=True) for td in row.find_all('td', class_='bet')]
    #         odds.append({'bookmaker': bookmaker_name, 'odds': odds_values})
    #     return odds
        
    # """Fetches HTML content either from a saved file or through Selenium WebDriver."""
    # def __fetch_html_content(self, url):
    #     html_content = None
    #     if self.should_use_saved_html_file and os.path.exists(SAVED_HTML_FILE_PATH):
    #         html_content = self.__read_html_file(file_path=SAVED_HTML_FILE_PATH)
    #         if html_content:
    #             LOGGER.info("HTML content read from saved file.")
    #         else:
    #             LOGGER.info("Saved HTML file is empty or couldn't be read.")

    #     if not html_content:
    #         self.driver.get(url)
    #         html_content = self.driver.page_source
    #         if self.should_use_saved_html_file:
    #             self.__save_html_file(file_path=SAVED_HTML_FILE_PATH, html_content=html_content)
    #             LOGGER.info("HTML content fetched and saved.")
    #         else:
    #             LOGGER.info("HTML content fetched from web.")
    #     return BeautifulSoup(html_content, 'html.parser')
    
    # def __store_data(self, file_path, matches_data):
    #     LOGGER.info("Will store data into csv file")
    #     headers = ['Home Team', 'Away Team', 'Date', 'Bookmaker', 'Odds 1', 'Odds X', 'Odds 2']
    #     with open(file_path, mode='w', newline='', encoding='utf-8') as file:
    #         writer = csv.writer(file)
    #         writer.writerow(headers)

    #         for match in matches_data:
    #             team_names_and_date = self.__extract_team_names_and_date(match)                
    #             for odd in self.__extract_bookmaker_odds(match):
    #                 row = [
    #                     team_names_and_date['home_team'],
    #                     team_names_and_date['away_team'],
    #                     team_names_and_date['date'],
    #                     odd['bookmaker'],
    #                     odd['odds'][0],  # Odds 1
    #                     odd['odds'][1],  # Odds X
    #                     odd['odds'][2],  # Odds 2
    #                 ]
    #                 writer.writerow(row)

    def scrape_and_store_matches(self):
        base_url = FRENCH_ODDS_SCRAPPER_LEAGUE_URLS_MAPPING.get(self.league)
        # if not base_url:
        #     raise ValueError(f"URL mapping not found for league: {self.league}")

        # soup = self.__fetch_html_content(url=base_url)
        # matches = soup.find_all('tr', style="background-color:white")
        # self.__store_data(file_path=ODDS_OUTPUT_FILE, matches_data=matches)