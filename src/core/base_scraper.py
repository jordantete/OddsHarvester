import logging, re, json, asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError, Error
from .playwright_manager import PlaywrightManager
from .browser_helper import BrowserHelper
from .odds_portal_market_extractor import OddsPortalMarketExtractor
from utils.constants import ODDSPORTAL_BASE_URL, ODDS_FORMAT, SCRAPE_CONCURRENCY_TASKS

class BaseScraper:
    """
    Base class for scraping match data from OddsPortal.
    """

    def __init__(
        self, 
        playwright_manager: PlaywrightManager,
        browser_helper: BrowserHelper, 
        market_extractor: OddsPortalMarketExtractor
    ):
        """
        Args:
            playwright_manager (PlaywrightManager): Handles Playwright lifecycle.
            browser_helper (BrowserHelper): Helper class for browser interactions.
            market_extractor (OddsPortalMarketExtractor): Handles market scraping.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.playwright_manager = playwright_manager
        self.browser_helper = browser_helper
        self.market_extractor = market_extractor

    async def set_odds_format(
        self, 
        page: Page, 
        odds_format: str = ODDS_FORMAT
    ):
        """
        Sets the odds format on the page.

        Args:
            page (Page): The Playwright page instance.
            odds_format (str): The desired odds format.
        """
        try:
            self.logger.info(f"Setting odds format: {odds_format}")
            button_selector = "div.group > button.gap-2"
            await page.wait_for_selector(button_selector, state="attached", timeout=5000)
            dropdown_button = await page.query_selector(button_selector)

            # Check if the desired format is already selected
            current_format = await dropdown_button.inner_text()
            self.logger.info(f"Current odds format detected: {current_format}")

            if current_format == odds_format:
                self.logger.info(f"Odds format is already set to '{odds_format}'. Skipping.")
                return

            await dropdown_button.click()
            await page.wait_for_timeout(1000)
            format_option_selector = "div.group > div.dropdown-content > ul > li > a"
            format_options = await page.query_selector_all(format_option_selector)

            for option in format_options:
                option_text = await option.inner_text()

                if option_text == odds_format:
                    self.logger.info(f"Selecting odds format: {option_text}")
                    await option.click()
                    self.logger.info(f"Odds format changed to '{odds_format}'.")
                    return
            
            self.logger.warning(f"Desired odds format '{odds_format}' not found in dropdown options.")

        except TimeoutError:
            self.logger.error("Timeout while setting odds format. Dropdown may not have loaded.")

        except Exception as e:
            self.logger.error(f"Error while setting odds format: {e}", exc_info=True)
    
    async def extract_match_links(
        self, 
        page: Page
    ) -> List[str]:
        """
        Extract and parse match links from the current page.

        Args:
            page (Page): A Playwright Page instance for this task.

        Returns:
            List[str]: A list of unique match links found on the page.
        """
        try:
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'lxml')
            event_rows = soup.find_all(class_=re.compile("^eventRow"))
            self.logger.info(f"Found {len(event_rows)} event rows.")

            match_links = {
                link['href']
                for row in event_rows
                for link in row.find_all('a', href=True)
                if len(link['href'].strip('/').split('/')) > 3
            }

            self.logger.info(f"Extracted {len(match_links)} unique match links.")
            return list(match_links)

        except Exception as e:
            self.logger.error(f"Error extracting match links: {e}", exc_info=True)
            return []

    async def extract_match_odds(
        self, 
        sport: str,
        match_links: List[str],
        markets: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract odds for a list of match links concurrently.

        Args:
            sport (str): The sport to scrape odds for.
            match_links (List[str]): A list of match links to scrape odds for.
            markets (Optional[List[str]]: The list of markets to scrape.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing scraped odds data.
        """
        self.logger.info(f"Starting to scrape odds for {len(match_links)} match links...")
        semaphore = asyncio.Semaphore(SCRAPE_CONCURRENCY_TASKS)
        failed_links = []

        async def scrape_with_semaphore(link):
            async with semaphore:
                tab = None
                
                try:
                    tab = await self.playwright_manager.context.new_page()
                    data = await self._scrape_match_data(page=tab, sport=sport, match_link=link, markets=markets)
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
            self.logger.warning(f"Failed to scrape data for {len(failed_links)} links: {failed_links}")

        return odds_data

    async def _scrape_match_data(
        self, 
        page: Page,
        sport: str,
        match_link: str, 
        markets: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Scrape data for a specific match based on the desired markets.

        Args:
            page (Page): A Playwright Page instance for this task.
            sport (str): The sport to scrape odds for.
            match_link (str): The link to the match page.
            markets (Optional[List[str]]): A list of markets to scrape (e.g., ['1x2', 'over_under_2_5']).

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing scraped data, or None if scraping fails.
        """
        full_match_url = f"{ODDSPORTAL_BASE_URL}{match_link}"
        self.logger.info(f"Scraping match URL: {full_match_url}")

        try:
            await page.goto(full_match_url, timeout=5000, wait_until="domcontentloaded")
            match_details = await self._extract_match_details_event_header(page)

            if not match_details:
                self.logger.warning(f"No match details found for {full_match_url}")
                return None

            if markets:
                self.logger.info(f"Scraping markets: {markets}")
                market_data = await self.market_extractor.scrape_markets(page=page, sport=sport, markets=markets)
                match_details.update(market_data)

            return match_details

        except Error as e:
            self.logger.error(f"Error scraping match data from {match_link}: {e}")
            return None

    async def _extract_match_details_event_header(    
        self, 
        page: Page
    ) -> Optional[Dict[str, Any]]:
        """
        Extract match details such as date, teams, and scores from the react event header.

        Args:
            page (Page): A Playwright Page instance for this task.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing match details, or None if header is is not found.
        """
        try:
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            script_tag = soup.find('div', id='react-event-header')

            if not script_tag:
                self.logger.error("Error: Couldn't find the JSON-LD script tag.")
                return None
        
            try:
                json_data = json.loads(script_tag.get('data'))

            except (TypeError, json.JSONDecodeError):
                self.logger.error("Error: Failed to parse JSON data.")
                return None

            event_body = json_data.get("eventBody", {})
            event_data = json_data.get("eventData", {})
            unix_timestamp = event_body.get("startDate")

            match_date = (
                datetime.fromtimestamp(unix_timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
                if unix_timestamp
                else None
            )

            return {
                "match_date": match_date,
                "home_team": event_data.get("home"),
                "away_team": event_data.get("away"),
                "league_name": event_data.get("tournamentName"),
                "home_score": event_body.get("homeResult"),
                "away_score": event_body.get("awayResult"),
                "partial_results": event_body.get("partialresult"),
                "venue": event_body.get("venue"),
                "venue_town": event_body.get("venueTown"),
                "venue_country": event_body.get("venueCountry"),
            }
        
        except Exception as e:
            self.logger.error(f"Error extracting match details while parsing React event Header: {e}")
            return None