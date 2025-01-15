import re, random, logging
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError, Error
from src.utils.constants import FOOTBALL_LEAGUES_URLS_MAPPING
from src.core.odds_portal_market_extractor import OddsPortalMarketExtractor

class OddsPortalScrapper:
    def __init__(
        self, 
        page: Page, 
        sport: str
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"OddsPortalScrapper will be initialized for sport: {sport}")
        self.page = page
        self.sport = sport
    
    async def scrape(
        self,
        date: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Main scraping method"""
        try:
            self.logger.info(f"Starting scrape for date={date}, league={league}, season={season}")
            await self._set_odds_format()
            
            if league and season:
                self.logger.info(f"Scraping historical odds for {league} season {season}")
                return await self._scrape_historical(league, season)
            else:
                self.logger.info(f"Scraping upcoming matches for date {date}")
                return await self._scrape_upcoming(date)
                
        except Exception as e:
            self.logger.error(f"Error during scraping: {str(e)}", exc_info=True)
            return []

    def __get_base_url(self, league: str, season: str = None) -> str:
        base_url = FOOTBALL_LEAGUES_URLS_MAPPING.get(league)
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

    async def __set_odds_format(self, odds_format: str = "EU Odds"):
        self.logger.info(f"Set Odds Format {odds_format}")
        try:
            button = await self.page.wait_for_selector("div.group > button.gap-2", state="attached")
            await button.click()
            await self.page.wait_for_timeout(2000) 
            formats = await self.page.query_selector_all("div.group > div.dropdown-content > ul > li > a")
            
            for f in formats:
                if await f.inner_text() == odds_format:
                    await f.click()
                    self.logger.info(f"Odds format changed")
                    break
        
        except TimeoutError:
            self.logger.warn(f"Odds have not been changed: May be because odds are already set in the required format")
    
    async def __parse_match_links(self):
        html_content = await self.page.content()
        self.logger.info(f"Will parse match links from page content")
        soup = BeautifulSoup(html_content, 'lxml')
        event_rows = soup.find_all(class_=re.compile("^eventRow"))
        self.logger.info(f"Found number of event_rows: {len(event_rows)}")
        hrefs = []
        
        for row in event_rows:
            links = row.find_all('a', href=True)
            
            for link in links:
                link_href = link['href']
                parts = link_href.strip('/').split('/')
                
                if len(parts) > 3:
                    hrefs.append(link_href)
        return hrefs
    
    async def __scrape_match_data(self, match_link):
        self.logger.info(f"Will scrape match url: {match_link}")
        await self.page.goto(f"https://www.oddsportal.com{match_link}", timeout=150000, wait_until="domcontentloaded")

        try:
            await self.page.wait_for_selector('div.bg-event-start-time ~ p', timeout=5000)
            await self.page.wait_for_selector('span.truncate', timeout=5000)
            date_elements = await self.page.query_selector_all('div.bg-event-start-time ~ p')
            team_elements = await self.page.query_selector_all('span.truncate')

            if not date_elements or not team_elements:
                self.logger.warn("Not on the expected page. date_elements or teams_elements are None.")
                return None
            
            day, date, time_value = [await element.inner_text() for element in date_elements]
            homeTeam, awayTeam = [await element.inner_text() for element in team_elements]

            odds_market_extractor = OddsPortalMarketExtractor(self.page)                
            ft_1x2_odds_data = await odds_market_extractor.extract_1X2_odds(period="FullTime")
            #over_under_1_5_odds_data = await odds_market_extractor.extract_over_under_odds(over_under_type_chosen="1.5", period="FullTime")
            over_under_2_5_odds_data = await odds_market_extractor.extract_over_under_odds(over_under_type_chosen="2.5", period="FullTime")
            #double_chance_odds_data = await odds_market_extractor.extract_double_chance_odds(period="FullTime")
            scrapped_data = {
                "date": date,
                "homeTeam": homeTeam,
                "awayTeam": awayTeam,
                "ft_1x2_odds_data": ft_1x2_odds_data,
                "over_under_2_5_odds_data": over_under_2_5_odds_data
            }
            return scrapped_data
        
        except Error as e:
            self.logger.warn(f"Elements not found on page: {match_link}. Possibly not the correct page. Error: {e}")
            return None

    async def __extract_match_links(self):
        match_links = []
        await self.__scroll_until_loaded()
        await self.page.wait_for_timeout(int(random.uniform(5000, 8000)))
        try:
            match_links = await self.__parse_match_links()
            if not match_links:
                raise ValueError(f"No matches links found, plese check. match_links: {match_links}")
            self.logger.info(f"After filtering fetched matches, remaining links: {len(match_links)}")
        except Exception as e:
            self.logger.error(f"While extracting data: {e}")
        finally:
            return match_links
    
    async def __scrape_odds(self):
        try:
            await self.__set_odds_format()
            match_links = await self.__extract_match_links()
            odds_data = []

            ## TODO: For testing purpose only scrape odds for the first 15 matchs
            for link in match_links[:15]:
            #for link in match_links:
                match_data = await self.__scrape_match_data(match_link=link)
                if match_data:
                    odds_data.append(match_data)
            return odds_data
        
        except Exception as e:
            self.logger.error(f"Extracting data or setting odds format: {e}")

    async def __scrape_odds_historic(self, nbr_of_pages: int = None):
        historic_odds = []
        pagination_links = await self.page.query_selector_all("a.pagination-link:not([rel='next'])")
        pages = [link.inner_text() for link in pagination_links]

        if nbr_of_pages is None:
            max_pages_to_scrape = len(pages)
        else:
            max_pages_to_scrape = min(nbr_of_pages, len(pages))

        current_url = self.page.url()
        for page in pages[:max_pages_to_scrape]:
            if page != 'Next':
                page_url = f"{current_url}#/page/{page}"
                self.logger.info(f"Page_url: {page_url}")
                try:
                    await self.page.goto(page_url)
                    await self.page.wait_for_timeout(int(random.uniform(2000, 5000)))  # waiting between 2 to 5 seconds
                    odds_data = await self.__scrape_odds()
                    historic_odds.append(odds_data)
                except Exception as error:
                    self.logger.error(f"error: {error}")
        return historic_odds

    async def get_historic_odds(self, league: str, season: str, nbr_of_pages: int = None):
        self.logger.info(f"Will grab historic odds for season: {season} and league: {league}")
        try:
            base_url = self.__get_base_url(league=league, season=season)
            await self.page.goto(base_url)
            historic_odds = await self.__scrape_odds_historic(nbr_of_pages=nbr_of_pages)
            return historic_odds
        
        except Exception as error:
            self.logger.error(f"Error: {error}")
        
        finally:
            await self.browser.close()
    
    async def get_next_matchs_odds(self, league: str):
        self.logger.info(f"Will grab next matchs odds for league: {league}")
        try:
            base_url = self.__get_base_url(league=league)
            await self.page.goto(base_url)
            next_matchs_odds = await self.__scrape_odds()
            return next_matchs_odds
        
        except Exception as error:
            self.logger.error(f"Error: {error}")
        
        finally:
            await self.browser.close()
    
    ## Sport can be: football, basketball, hockey, volleyball, etc..
    async def get_upcoming_matchs_odds(self, sport: str, date):
        self.logger.info(f"Will grab upcoming matchs odds for sport: {sport} at date: {date}")
        
        try:
            base_url = f"https://www.oddsportal.com/matches/{sport}/{date}/"
            await self.page.goto(base_url, timeout=200000, wait_until="domcontentloaded")
            next_matchs_odds = await self.__scrape_odds()
            return next_matchs_odds
        
        except Exception as error:
            self.logger.error(f"Error: {error}")
        
        finally:
            await self.browser.close()
