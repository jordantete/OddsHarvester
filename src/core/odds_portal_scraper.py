import random
from typing import Optional, List, Dict, Any
from src.core.url_builder import URLBuilder
from src.core.base_scraper import BaseScraper
from playwright.async_api import Page
from src.utils.constants import ODDSPORTAL_BASE_URL

class OddsPortalScraper(BaseScraper):
    """
    Main class that manages the scraping workflow from OddsPortal.
    """

    async def start_playwright(
        self, 
        headless: bool = True, 
        browser_user_agent: str | None = None,
        browser_locale_timezone: str | None = None,
        browser_timezone_id: str | None = None,
        proxy: Optional[Dict[str, str]] = None
    ):
        """
        Initializes Playwright using PlaywrightManager.

        Args:
            headless (bool): Whether to run Playwright in headless mode.
            proxy (Optional[Dict[str, str]]): Proxy configuration if needed.
        """
        await self.playwright_manager.initialize(
            headless=headless, 
            user_agent=browser_user_agent,
            locale=browser_locale_timezone,
            timezone_id=browser_timezone_id,
            proxy=proxy
        )

    async def stop_playwright(self):
        """Stops Playwright and cleans up resources."""
        await self.playwright_manager.cleanup()

    async def scrape_historic(
        self, 
        sport: str,
        league: str, 
        season: str, 
        markets: Optional[List[str]] = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrapes historical odds data.

        Args:
            sport (str): The sport to scrape.
            league (str): The league to scrape.
            season (str): The season to scrape.
            markets (Optional[List[str]]): List of markets.
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.
            max_pages (Optional[int]): Maximum number of pages to scrape (default is None for all pages).

        Returns:
            List[Dict[str, Any]]: A list of dictionaries containing scraped historical match odds data.
        """
        current_page = self.playwright_manager.page
        if not current_page:
            raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")
        
        base_url = URLBuilder.get_historic_matches_url(sport=sport, league=league, season=season)
        self.logger.info(f"Fetching historical odds from URL: {base_url}")

        await current_page.goto(base_url)
        await self._prepare_page_for_scraping(page=current_page)

        pages_to_scrape = await self._get_pagination_info(page=current_page, max_pages=max_pages)
        all_links = await self._collect_match_links(base_url=base_url, pages_to_scrape=pages_to_scrape)
        return await self.extract_match_odds(
            sport=sport, 
            match_links=all_links, 
            markets=markets, 
            scrape_odds_history=scrape_odds_history, 
            target_bookmaker=target_bookmaker
        )

    async def scrape_upcoming(
        self, 
        sport: str, 
        date: str, 
        league: Optional[str] = None,
        markets: Optional[List[str]] = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None
    ) -> List[Dict[str, Any]]:
        """
        Scrapes upcoming match odds.

        Args:
            sport (str): The sport to scrape.
            date (str): The date to scrape.
            league (Optional[str]): The league to scrape.
            markets (Optional[List[str]]): List of markets.
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.

        Returns:
            List[Dict[str, Any]]: A List of dictionaries containing upcoming match odds data.
        """
        current_page = self.playwright_manager.page
        if not current_page:
            raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")

        url = URLBuilder.get_upcoming_matches_url(sport=sport, date=date, league=league)
        self.logger.info(f"Fetching upcoming odds from {url}")

        await current_page.goto(url, timeout=10000, wait_until="domcontentloaded")
        await self._prepare_page_for_scraping(page=current_page)
        match_links = await self.extract_match_links(page=current_page)

        if not match_links:
            self.logger.warning("No match links found for upcoming matches.")
            return []

        return await self.extract_match_odds(
            sport=sport, 
            match_links=match_links, 
            markets=markets, 
            scrape_odds_history=scrape_odds_history, 
            target_bookmaker=target_bookmaker
        )
    
    async def scrape_matches(
        self,
        match_links: List[str],
        sport: str,
        markets: List[str] | None = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None
    ) -> List[Dict[str, Any]]:
        """
        Scrapes match odds from a list of specific match URLs.

        Args:
            match_links (List[str]): List of URLs of matches to scrape.
            sport (str): The sport to scrape.
            markets (List[str] | None): List of betting markets to scrape. Defaults to None.
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.

        Returns:
            List[Dict[str, Any]]: A list containing odds and match details.
        """
        current_page = self.playwright_manager.page
        if not current_page:
            raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")
        
        await current_page.goto(ODDSPORTAL_BASE_URL, timeout=20000, wait_until="domcontentloaded")
        await self._prepare_page_for_scraping(page=current_page)
        return await self.extract_match_odds(
            sport=sport, 
            match_links=match_links, 
            markets=markets,
            scrape_odds_history=scrape_odds_history, 
            target_bookmaker=target_bookmaker,
            concurrent_scraping_task=len(match_links)
        )

    async def _prepare_page_for_scraping(self, page: Page):
        """
        Prepares the Playwright page for scraping by setting odds format and dismissing banners.

        Args:
            page: Playwright page instance.
        """
        await self.set_odds_format(page=page)
        await self.browser_helper.dismiss_cookie_banner(page=page)
    
    async def _get_pagination_info(
        self, 
        page: Page, 
        max_pages: Optional[int]
    ) -> List[int]:
        """
        Extracts pagination details from the page.

        Args:
            page: Playwright page instance.
            max_pages (Optional[int]): Maximum pages to scrape.

        Returns:
            List[int]: List of pages to scrape.
        """
        pagination_links = await page.query_selector_all("a.pagination-link:not([rel='next'])")
        total_pages = [int(await link.inner_text()) for link in pagination_links if (await link.inner_text()).isdigit()]

        if not total_pages:
            self.logger.info("No pagination found; scraping only the current page.")
            return [1]

        pages_to_scrape = sorted(total_pages)[:max_pages] if max_pages else total_pages
        self.logger.info(f"Pages to scrape: {pages_to_scrape}")
        return pages_to_scrape

    async def _collect_match_links(
        self, 
        base_url: str, 
        pages_to_scrape: List[int]
    ) -> List[str]:
        """
        Collects match links from multiple pages.

        Args:
            base_url (str): The base URL of the historic matches.
            pages_to_scrape (List[int]): Pages to scrape.

        Returns:
            List[str]: List of match links found.
        """
        all_links = []
        for page_number in pages_to_scrape:
            try:
                self.logger.info(f"Processing page: {page_number}")
                tab = await self.playwright_manager.context.new_page()

                page_url = f"{base_url}#/page/{page_number}"
                self.logger.info(f"Navigating to: {page_url}")
                await tab.goto(page_url, timeout=10000, wait_until="domcontentloaded")
                await tab.wait_for_timeout(random.randint(2000, 4000))

                links = await self.extract_match_links(page=tab)
                all_links.extend(links)
                self.logger.info(f"Extracted {len(links)} links from page {page_number}.")

            except Exception as e:
                self.logger.error(f"Error processing page {page_number}: {e}")

            finally:
                if 'tab' in locals() and tab:
                    await tab.close()

        unique_links = list(set(all_links))
        self.logger.info(f"Total unique match links found: {len(unique_links)}")
        return unique_links