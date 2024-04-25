import time, re, random, os
from utils import FOOTBALL_LEAGUES_URLS_MAPPING
from logger import LOGGER
from odds_portal_odds_extractor import OddsPortalOddsExtractor
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError, Error

class OddsPortalScrapper:
    def __init__(self):
        self.__initialize_webdriver()
    
    def __initialize_webdriver(self):
        playwright = sync_playwright().start()
        browser_args = [
            '--window-size=1800,2500',
            '--window-position=000,000',
            "--full-memory-crash-report",
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            "--disable-gpu",
            '--use-gl=egl',
            '--disable-blink-features=AutomationControlled',
            '--disable-background-networking',
            '--enable-features=NetworkService,NetworkServiceInProcess',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-breakpad',
            '--disable-client-side-phishing-detection',
            '--disable-component-extensions-with-background-pages',
            "--ignore-certificate-errors",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            '--disable-default-apps',
            '--disable-extensions',
            '--disable-features=Translate',
            '--disable-hang-monitor',
            '--disable-ipc-flooding-protection',
            '--disable-popup-blocking',
            '--disable-prompt-on-repost',
            '--disable-renderer-backgrounding',
            '--disable-sync',
            '--force-color-profile=srgb',
            '--metrics-recording-only',
            '--enable-automation',
            '--password-store=basic',
            '--use-mock-keychain',
            '--hide-scrollbars',
            '--mute-audio'
        ]
        self.browser = playwright.chromium.launch(headless=False, args=browser_args)
        context = self.browser.new_context(ignore_https_errors=True, permissions=['notifications'],)
        self.page = context.new_page()

    """Scrolls down the page in a loop until no new content is loaded or a timeout is reached."""
    def __scroll_until_loaded(self, timeout=30, scroll_pause_time=1.5):
        end_time = time.time() + timeout
        last_height = self.page.evaluate("document.body.scrollHeight")
        
        while True:
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(scroll_pause_time * 1000)  # Convert seconds to milliseconds

            new_height = self.page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break

            last_height = new_height
            if time.time() > end_time:
                break

    def __get_base_url(self, league: str, season: str = None) -> str:
        base_url = LEAGUES_URLS_MAPPING.get(league)
        if not base_url:
            raise ValueError(f"URL mapping not found for league: {league}")
        
        if not season:
            return base_url
        else:
            try:
                season_components = season.split("-")
                return f"{base_url}-{season_components[0]}-{season_components[1]}/results/"
            except IndexError:
                raise ValueError(f"Invalid season format: {season}. Expected format: 'YYYY-YYYY'")

    def __set_odds_format(self, odds_format: str = "EU Odds"):
        LOGGER.info(f"Set Odds Format {odds_format}")
        try:
            button = self.page.wait_for_selector("div.group > button.gap-2", state="attached")
            button.click()
            self.page.wait_for_timeout(2000) 
            formats = self.page.query_selector_all("div.group > div.dropdown-content > ul > li > a")
            for f in formats:
                if f.inner_text() == odds_format:
                    f.click()
                    LOGGER.info(f"Odds format changed")
                    break
        except TimeoutError:
            LOGGER.warn(f"Odds have not been changed: May be because odds are already set in the required format")
    
    def __get_match_links(self):
        LOGGER.info("Fetching match links")
        html_content = self.page.content()
        soup = BeautifulSoup(html_content, 'lxml')
        event_rows = soup.find_all(class_=re.compile("^eventRow"))
        hrefs = []
        for row in event_rows:
            links = row.find_all('a', href=True)
            for link in links:
                # Parse link:
                link_href = link['href']
                parts = link_href.strip('/').split('/')
                if len(parts) > 3:
                    hrefs.append(link_href)
        return hrefs
    
    def __scrape_match_data(self, match_link):
        LOGGER.info(f"Will scrape match url: {match_link}")
        self.page.goto(f"https://www.oddsportal.com{match_link}")
        self.page.wait_for_timeout(2000)

        try:
            date_elements = self.page.query_selector_all('div.bg-event-start-time ~ p')
            team_elements = self.page.query_selector_all('span.truncate')

            if not date_elements or not team_elements:
                raise Error("Not on the expected page.")
            
            ## TODO: extract only date if day & time_value are not used
            day, date, time_value = [element.inner_text() for element in date_elements]
            homeTeam, awayTeam = [element.inner_text() for element in team_elements]
            odds_extractor = OddsPortalOddsExtractor(self.page)                
            ft_1x2_odds_data = odds_extractor.extract_1X2_odds(period="FullTime")
            #over_under_1_5_odds_data = odds_extractor.extract_over_under_odds(over_under_type_chosen="1.5", period="FullTime")
            over_under_2_5_odds_data = odds_extractor.extract_over_under_odds(over_under_type_chosen="2.5", period="FullTime")
            #double_chance_odds_data = odds_extractor.extract_double_chance_odds(period="FullTime")
            scrapped_data = {
                "date": date,
                "homeTeam": homeTeam,
                "awayTeam": awayTeam,
                "ft_1x2_odds_data": ft_1x2_odds_data,
                "over_under_2_5_odds_data": over_under_2_5_odds_data
            }
            return scrapped_data
        except Error as e:
            LOGGER.warn(f"Elements not found on page: {match_link}. Possibly not the correct page. Error: {e}")
            return None

    def __extract_match_links(self):
        match_links = []
        self.__scroll_until_loaded()
        time.sleep(random.uniform(3, 5))
        try:
            match_links = self.__get_match_links()
            if not match_links:
                raise ValueError(f"No matches links found, plese check. match_links: {match_links}")
            LOGGER.info(f"After filtering fetched matches, remaining links: {len(match_links)}")
        except Exception as e:
            LOGGER.error(f"While extracting data: {e}")
        finally:
            return match_links
    
    def __scrape_odds(self):
        try:
            self.__set_odds_format()
            match_links = self.__extract_match_links()
            odds_data = []

            ## TODO: For testing purpose only scrape odds for the first 3 matchs
            for link in match_links[:3]:
            #for link in match_links:
                match_data = self.__scrape_match_data(match_link=link)
                if match_data:
                    odds_data.append(match_data)
            return odds_data
        except Exception as e:
            LOGGER.error(f"Extracting data or setting odds format: {e}")

    def __scrape_odds_historic(self, nbr_of_pages: int = None):
        historic_odds = []
        pagination_links = self.page.query_selector_all("a.pagination-link:not([rel='next'])")
        pages = [link.inner_text() for link in pagination_links]

        if nbr_of_pages is None:
            max_pages_to_scrape = len(pages)
        else:
            max_pages_to_scrape = min(nbr_of_pages, len(pages))

        current_url = self.page.url()
        for page in pages[:max_pages_to_scrape]:
            if page != 'Next':
                page_url = f"{current_url}#/page/{page}"
                LOGGER.info(f"Page_url: {page_url}")
                try:
                    self.page.goto(page_url)
                    self.page.wait_for_timeout(int(random.uniform(2000, 5000)))  # waiting between 2 to 5 seconds
                    odds_data = self.__scrape_odds()
                    historic_odds.append(odds_data)
                except Exception as error:
                    LOGGER.error(f"error: {error}")
        return historic_odds

    def get_historic_odds(self, league: str, season: str, nbr_of_pages: int = None):
        LOGGER.info(f"Will grab historic odds for season: {season} and league: {league}")
        try:
            base_url = self.__get_base_url(league=league, season=season)
            self.page.goto(base_url)
            historic_odds = self.__scrape_odds_historic(nbr_of_pages=nbr_of_pages)
            return historic_odds
        except Exception as error:
            LOGGER.error(f"Error: {error}")
        finally:
            self.browser.close()
    
    def get_next_matchs_odds(self, league: str):
        LOGGER.info(f"Will grab next matchs odds for league: {league}")
        try:
            base_url = self.__get_base_url(league=league)
            self.page.goto(base_url)
            next_matchs_odds = self.__scrape_odds()
            return next_matchs_odds
        except Exception as error:
            LOGGER.error(f"Error: {error}")
        finally:
            self.browser.close()
    
    ## Sport can be: football, basketball, hockey, volleyball, etc..
    def get_upcoming_matchs_odds(self, sport: str, date):
        LOGGER.info(f"Will grab next matchs odds for sport: {sport} at date: {date}")
        try:
            base_url = f"https://www.oddsportal.com/matches/{sport}/{date}/"
            self.page.goto(base_url)
            next_matchs_odds = self.__scrape_odds()
            return next_matchs_odds
        except Exception as error:
            LOGGER.error(f"Error: {error}")
        finally:
            self.browser.close()
