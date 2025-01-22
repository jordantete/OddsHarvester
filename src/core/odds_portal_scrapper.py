import re, random, logging, asyncio
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, TimeoutError, Error
from core.odds_portal_market_extractor import OddsPortalMarketExtractor
from core.url_builder import URLBuilder
from core.browser_helper import BrowserHelper
from utils.utils import is_running_in_docker
from utils.command_enum import CommandEnum
from utils.constants import ODDS_FORMAT, ODDSPORTAL_BASE_URL, PLAYWRIGHT_BROWSER_ARGS, PLAYWRIGHT_BROWSER_ARGS_DOCKER, BROWSER_USER_AGENT, BROWSER_LOCALE_TIMEZONE, BROWSER_TIMEZONE_ID

class OddsPortalScrapper:
    SCRAPING_CONCURENT_TASKS = 2 # Limit concurrency to x tasks (adjust as needed)

    def __init__(
        self, 
        browser_helper: BrowserHelper,
        page: Optional[Page] = None, 
        browser: Optional[Any] = None, 
        playwright: Optional[Any] = None
    ):
        """
        Initialize the OddsPortalScrapper class.

        Args:
            browser_helper (BrowserHelper): Helper class for browser-related operations.
            page (Optional[Page]): Playwright Page instance (default is None).
            browser (Optional[Any]): Playwright Browser instance (default is None).
            playwright (Optional[Any]): Playwright instance (default is None).
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.browser_helper = browser_helper
        self.page = page
        self.browser = browser
        self.playwright = playwright
    
    async def initialize_and_start_playwright(
        self, 
        is_webdriver_headless: bool
    ):
        """
        Initialize and start Playwright with a browser and page.

        Args:
            is_webdriver_headless (bool): Whether to start the browser in headless mode.
        """
        try:
            self.logger.info("Starting Playwright...")
            self.playwright = await async_playwright().start()

            self.logger.info("Launching browser...")
            browser_args = PLAYWRIGHT_BROWSER_ARGS_DOCKER if is_running_in_docker() else PLAYWRIGHT_BROWSER_ARGS

            ## TODO: use proxy there if needed
            self.browser = await self.playwright.chromium.launch(
                headless=is_webdriver_headless, 
                args=browser_args
            )

            self.context = await self.browser.new_context(
                locale=BROWSER_LOCALE_TIMEZONE,
                timezone_id=BROWSER_TIMEZONE_ID,
                user_agent=BROWSER_USER_AGENT
            )

            self.logger.info("Opening initial page from context...")
            self.page = await self.context.new_page()
        
        except Exception as e:
            self.logger.error(f"Failed to initialize Playwright: {str(e)}")
            raise
    
    async def cleanup(self):
        """
        Cleanup Playwright resources to avoid memory leaks.
        """
        self.logger.info("Cleaning up Playwright resources...")
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.logger.info("Playwright resources cleanup complete.")
    
    async def scrape(
        self,
        command: CommandEnum,
        sport: Optional[str] = None,
        date: Optional[str] = None,
        league: Optional[str] = None,
        season: Optional[str] = None,
        markets: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Main entry point for scraping odds data.

        Args:
            command (str): The subparser command used ('scrape-upcoming' or 'scrape-historic').
            sport (Optional[str]): The sport to scrape odds for (e.g., "football").
            date (Optional[str]): The date for scraping upcoming matches (YYYY-MM-DD format).
            league (Optional[str]): The league to scrape historical odds for.
            season (Optional[str]): The season for scraping historical odds.
            markets (Optional[List[str]]: The list of markets to scrape.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing scraped odds data.
        """
        try:
            self.logger.info(f"Command received: {command}")
            
            if command == CommandEnum.HISTORIC:
                if not league or not season:
                    raise ValueError("Both 'league' and 'season' must be provided for historic scraping.")
                
                self.logger.info(f"Scraping historical odds for league={league}, season={season}, markets={markets}")
                return await self._scrape_historic_odds(league=league, season=season, markets=markets, max_pages=None)
            
            elif command == CommandEnum.UPCOMING_MATCHES:
                if not date:
                    raise ValueError("A valid 'date' must be provided for upcoming matches scraping.")
                
                self.logger.info(f"Scraping upcoming matches for sport={sport}, date={date}, league={league}, markets={markets}")
                return await self._scrape_upcoming_matches(sport=sport, date=date, league=league, markets=markets)
            
            else:
                raise ValueError(f"Unknown command: {command}. Supported commands are 'upcoming-matches' and 'historic'.")

        except Exception as e:
            self.logger.error(f"Error during scraping process: {e}", exc_info=True)
            return []

    async def _scrape_historic_odds(
        self, 
        league: str, 
        season: str,
        markets: Optional[List[str]] = None,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape historical odds with optional pagination.

        Args:
            league (str): The league to scrape historical odds for.
            season (str): The season for which historical odds should be scraped.
            markets (Optional[List[str]]: The list of markets to scrape.
            max_pages (Optional[int]): Maximum number of pages to scrape (default is None for all pages).

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing scraped historical odds data.
        """
        try:
            base_url = URLBuilder.get_historic_matches_url(league, season)
            self.logger.info(f"Fetching historical odds from URL: {base_url}")

            await self.page.goto(base_url)
            await self._set_odds_format()
            await self.browser_helper.dismiss_cookie_banner(page=self.page)

            all_links = []
            pagination_links = await self.page.query_selector_all("a.pagination-link:not([rel='next'])")
            total_pages = [int(await link.inner_text()) for link in pagination_links if (await link.inner_text()).isdigit()]

            if not total_pages:
                self.logger.info("No pagination links found; only scraping the current page.")
                total_pages = [1]

            pages_to_scrape = sorted(total_pages)[:max_pages] if max_pages else total_pages
            self.logger.info(f"Pages to scrape: {pages_to_scrape}")

            for page_number in pages_to_scrape:
                try:
                    page_url = f"{base_url}#/page/{page_number}"
                    self.logger.info(f"Processing page: {page_url}")
                    
                    await self.page.goto(page_url)
                    await self.page.wait_for_timeout(random.randint(2000, 5000))

                    links = await self._extract_match_links_for_page(page=self.page)
                    all_links.extend(links)

                except Exception as page_error:
                    self.logger.error(f"Error processing page {page_number}: {page_error}")

            unique_links = list(set(all_links))
            self.logger.info(f"Found {len(unique_links)} unique match links across {len(pages_to_scrape)} pages.")
            return await self._extract_match_odds(match_links=unique_links, markets=markets)

        except TimeoutError as te:
            self.logger.error(f"Timeout occurred while navigating to {base_url}: {te}")
            raise TimeoutError(f"Failed to navigate to {base_url}: {te}") from te

        except Exception as e:
            self.logger.error(f"Unexpected error during historical odds scraping: {e}", exc_info=True)
            raise RuntimeError(f"Failed to scrape historical odds: {e}") from e

    async def _scrape_upcoming_matches(
        self, 
        sport: str, 
        date: str,
        league: Optional[str] = None,
        markets: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape upcoming odds for a given sport and date.
        
        Args:
            sport (str): The sport to scrape odds for.
            date (str): The date for which upcoming matches should be scraped.
            markets (Optional[List[str]]: The list of markets to scrape.

        Returns:
            List[Dict[str, Any]]: List of dictionaries containing match odds data.
        """
        try:
            base_url = URLBuilder.get_upcoming_matches_url(sport=sport, date=date, league=league)
            self.logger.info(f"Fetching upcoming odds from URL: {base_url}")

            await self.page.goto(base_url)
            await self._set_odds_format()
            await self.browser_helper.dismiss_cookie_banner(page=self.page)
            links = await self._extract_match_links_for_page(page=self.page)

            if not links:
                self.logger.warning("No match links found for upcoming matches.")
                return []

            self.logger.info(f"Found {len(links)} match links for upcoming matches.")
            match_odds = await self._extract_match_odds(match_links=links, markets=markets)
            self.logger.info(f"Scraped odds for {len(match_odds)} matches.")
            return match_odds

        except TimeoutError as te:
            self.logger.error(f"Timeout occurred while navigating to {base_url}: {te}")
            raise TimeoutError(f"Failed to navigate to {base_url}: {te}") from te

        except Exception as e:
            self.logger.error(f"Unexpected error during upcoming odds scraping: {e}", exc_info=True)
            raise RuntimeError(f"Failed to scrape upcoming matches: {e}") from e

    async def _set_odds_format(
        self, 
        odds_format: str = ODDS_FORMAT
    ):
        """
        Set the odds format on the page.

        Args:
            odds_format (str): The desired odds format.
        """
        self.logger.info(f"Will set Odds Format: {odds_format}")

        try:
            button_selector = "div.group > button.gap-2"
            await self.page.wait_for_selector(button_selector, state="attached", timeout=5000)
            dropdown_button = await self.page.query_selector(button_selector)

            # Check if the desired format is already selected
            current_format = await dropdown_button.inner_text()
            self.logger.info(f"Current odds format detected: {current_format}")

            if current_format == odds_format:
                self.logger.info(f"Odds format is already set to '{odds_format}'. Skipping format selection.")
                return

            await dropdown_button.click()
            await self.page.wait_for_timeout(1000) 
            format_option_selector = "div.group > div.dropdown-content > ul > li > a"
            format_options = await self.page.query_selector_all(format_option_selector)
            
            for option in format_options:
                option_text = await option.inner_text()

                if option_text == odds_format:
                    self.logger.info(f"Selecting odds format: {option_text}")
                    await option.click()
                    self.logger.info(f"Odds format successfully changed to '{odds_format}'.")
                    return
            
            self.logger.warning(f"Desired odds format '{odds_format}' not found in the dropdown options.")

        except TimeoutError:
            self.logger.error("Timeout occurred while attempting to set odds format. The dropdown may not have loaded.")

        except Exception as e:
            self.logger.error(f"Unexpected error while setting odds format: {e}", exc_info=True)

    async def _extract_match_odds(
        self, 
        match_links: List[str],
        markets: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract odds for a list of match links concurrently.

        Args:
            match_links (List[str]): A list of match links to scrape odds for.
            markets (Optional[List[str]]: The list of markets to scrape.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing scraped odds data.
        """
        self.logger.info(f"Starting to scrape odds for {len(match_links)} match links...")
        semaphore = asyncio.Semaphore(self.SCRAPING_CONCURENT_TASKS)
        failed_links = []

        async def scrape_with_semaphore(link):
            async with semaphore:
                tab = None
                
                try:
                    tab = await self.context.new_page()
                    data = await self._scrape_match_data(page=tab, match_link=link, markets=markets)
                    self.logger.info(f"Successfully scraped match link: {link}")
                    return data
                
                except Exception as e:
                    self.logger.error(f"Error scraping link {link}: {e}")
                    failed_links.append(link)
                    return None
                
                finally:
                    if tab:
                        await tab.close()

        tasks = [scrape_with_semaphore(link) for link in match_links]
        results = await asyncio.gather(*tasks)
        odds_data = [result for result in results if result is not None]

        self.logger.info(f"Successfully scraped odds data for {len(odds_data)} matches.")

        if failed_links:
            ## TODO: implement retry mechanism for failed links
            self.logger.warning(f"Failed to scrape data for {len(failed_links)} links: {failed_links}")

        return odds_data
    
    async def _scrape_match_data(
        self, 
        page: Page,
        match_link: str, 
        markets: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Scrape data for a specific match based on the desired markets.

        Args:
            page (Page): A Playwright Page instance for this task.
            match_link (str): The link to the match page.
            markets (Optional[List[str]]): A list of markets to scrape (e.g., ['1x2', 'over_under_2_5']).

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing scraped data, or None if scraping fails.
        """
        full_match_url = f"{ODDSPORTAL_BASE_URL}{match_link}"
        self.logger.info(f"Will scrape match url: {full_match_url}")

        try:
            await page.goto(full_match_url, timeout=5000, wait_until="domcontentloaded")

            html_content = await page.content()
            soup = BeautifulSoup(html_content, "lxml")

            match_date_element = soup.select('div[data-testid="game-time-item"] p')
            match_date = match_date_element[1].text.strip().rstrip(",") if len(match_date_element) > 1 else None

            home_team_element = soup.select_one('div[data-testid="game-host"] p')
            away_team_element = soup.select_one('div[data-testid="game-guest"] p')
            home_team = home_team_element.text.strip() if home_team_element else None
            away_team = away_team_element.text.strip() if away_team_element else None

            home_score_element = soup.select_one('div[data-testid="game-host"] ~ div')
            home_score = home_score_element.text.strip() if home_score_element else None

            away_score_element = soup.select_one('div[data-testid="game-guest"]').find_previous_sibling("div") if soup.select_one('div[data-testid="game-guest"]') else None
            away_score = away_score_element.text.strip() if away_score_element else None

            odds_market_extractor = OddsPortalMarketExtractor(page=page, browser_helper=self.browser_helper)

            market_methods = {
                "1x2": odds_market_extractor.extract_1X2_odds,
                "over_under_1_5": lambda: odds_market_extractor.extract_over_under_odds(over_under_market="1.5"),
                "over_under_2_5": lambda: odds_market_extractor.extract_over_under_odds(over_under_market="2.5"),
                "over_under_3_5": lambda: odds_market_extractor.extract_over_under_odds(over_under_market="3.5"),
                "over_under_4_5": lambda: odds_market_extractor.extract_over_under_odds(over_under_market="4.5"),
                "btts": odds_market_extractor.extract_btts_odds,
                "double_chance": odds_market_extractor.extract_double_chance_odds,
            }

            scrapped_data = {
                "date": match_date,
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
            }

            for market in markets or []:
                try:
                    if market in market_methods:
                        self.logger.info(f"Scraping market: {market}")
                        scrapped_data[f"{market}_data"] = await market_methods[market]()
                    else:
                        self.logger.warning(f"Market '{market}' is not supported.")

                except Exception as e:
                    self.logger.error(f"Error scraping market '{market}': {e}")
                    scrapped_data[f"{market}_data"] = None

            return scrapped_data
        
        except Error as e:
            self.logger.error(f"Error scraping match data from {match_link}: {e}")
            return None

    async def _extract_match_links_for_page(
        self,
        page: Page
    )-> List[str]:
        """
        Extract match links from the current page.

        Args:
            page (Page): The Playwright page to extract match links from.

        Returns:
            List[str]: A list of match links found on the page.
        """
        try:
            match_links = []
            await self.browser_helper.scroll_until_loaded(page=page, timeout=15, max_scroll_attempts=2)
            await page.wait_for_timeout(int(random.uniform(2000, 4000)))
            match_links = await self._parse_match_links_for_page(page=page)            
            self.logger.info(f"After filtering fetched matches, remaining links: {len(match_links)}")
        
        except Exception as e:
            self.logger.error(f"Error while extracting match links for page: {e}")
        
        finally:
            return match_links
    
    async def _parse_match_links_for_page(
        self, 
        page: Page
    ) -> List[str]:
        """
        Parse match links from the HTML content of the current page.

        Args:
            page (Page): The Playwright page to parse links from.

        Returns:
            List[str]: A list of parsed match links.
        """
        html_content = await page.content()
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