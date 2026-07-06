import logging
from typing import Any

from playwright.async_api import Page

from oddsharvester.core.browser.market_navigation import MarketTabNavigator
from oddsharvester.core.browser.scrolling import PageScroller
from oddsharvester.core.browser.selection import (
    PERIOD_STRATEGY,
    PeriodSelector,
    SelectionManager,
)
from oddsharvester.core.market_extraction import (
    MarketGrouping,
    NavigationManager,
    OddsHistoryExtractor,
    OddsParser,
    SubmarketExtractor,
)
from oddsharvester.core.market_extraction.line_tokens import line_name_to_token
from oddsharvester.core.sport_market_registry import SportMarketRegistry
from oddsharvester.core.sport_period_registry import SportPeriodRegistry
from oddsharvester.utils.sport_market_constants import FOOTBALL_UMBRELLA_MARKETS, Sport


class OddsPortalMarketExtractor:
    """
    Extracts betting odds data from OddsPortal using Playwright.

    This class provides methods to scrape various betting markets (e.g., 1X2, Over/Under, BTTS, ..)
    for specific match periods and bookmaker odds.
    """

    def __init__(self, scroller: PageScroller, tab_navigator: MarketTabNavigator, selection_manager: SelectionManager):
        """
        Initialize OddsPortalMarketExtractor.

        Args:
            scroller (PageScroller): Handles incremental page scrolling.
            tab_navigator (MarketTabNavigator): Handles market tab navigation.
            selection_manager (SelectionManager): Manages period selection.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.scroller = scroller
        self.tab_navigator = tab_navigator
        self.selection_manager = selection_manager
        self.period_selector = PeriodSelector()

        # Initialize component classes
        self.navigation_manager = NavigationManager(tab_navigator=tab_navigator, scroller=scroller)
        self.odds_parser = OddsParser()
        self.submarket_extractor = SubmarketExtractor()
        self.odds_history_extractor = OddsHistoryExtractor()
        self.market_grouping = MarketGrouping()

    async def scrape_markets(
        self,
        page: Page,
        sport: str,
        markets: list[str],
        period: str = "FullTime",
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        preview_submarkets_only: bool = False,
    ) -> dict[str, Any]:
        """
        Extract market data for a given match.

        Args:
            page (Page): A Playwright Page instance for this task.
            sport (str): The sport to scrape odds for.
            markets (List[str]): A list of markets to scrape (e.g., ['1x2', 'over_under_2_5']).
            period (str): The match period (e.g., "FullTime").
            scrape_odds_history (bool): Whether to extract historic odds evolution.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.
            preview_submarkets_only (bool): If True, only scrape the collapsed submarket odds (best/highest shown
            per line, not per-bookmaker) from visible submarkets.

        Returns:
            Dict[str, Any]: A dictionary containing market data.
        """
        market_data = {}
        market_methods = SportMarketRegistry.get_market_mapping(sport)

        # Expand umbrella tokens (e.g. "over_under") into the concrete per-line tokens
        # actually rendered on the page (e.g. "over_under_2_5", "over_under_3_5") before
        # running the normal per-market extraction loop below.
        expanded_markets: list[str] = []
        for market in markets:
            umbrella_main_market = FOOTBALL_UMBRELLA_MARKETS.get(market) if sport == Sport.FOOTBALL.value else None
            if umbrella_main_market is None:
                if market not in expanded_markets:
                    expanded_markets.append(market)
                continue

            try:
                line_names = await self._discover_line_names(
                    page=page, main_market=umbrella_main_market, sport=sport, period=period
                )
                line_tokens: list[str] = []
                for line_name in line_names:
                    token = line_name_to_token(umbrella_main_market, line_name)
                    if token is not None and token not in line_tokens:
                        line_tokens.append(token)
            except Exception as e:
                self.logger.warning(f"Error discovering lines for umbrella market '{market}': {e}")
                continue

            if not line_tokens:
                self.logger.warning(f"Umbrella market '{market}' discovered no lines on the page; skipping.")
                continue

            for token in line_tokens:
                if token not in expanded_markets:
                    expanded_markets.append(token)

        markets = expanded_markets

        # Group markets by their main market type for optimization in preview mode
        market_groups = {}

        for market in markets:
            try:
                if market in market_methods:
                    # For preview mode, group markets by their main market type
                    if preview_submarkets_only:
                        # Get the main market info from the existing market method
                        main_market_info = self.market_grouping.get_main_market_info(market_methods[market])
                        if main_market_info:
                            main_market_name = main_market_info["main_market"]
                            if main_market_name not in market_groups:
                                market_groups[main_market_name] = []
                            market_groups[main_market_name].append(market)
                    else:
                        # Normal mode: scrape each market individually
                        self.logger.info(f"Scraping market: {market} (Period: {period})")
                        market_data[f"{market}_market"] = await market_methods[market](
                            self, page, period, scrape_odds_history, target_bookmaker, preview_submarkets_only, sport
                        )
                else:
                    self.logger.warning(f"Market '{market}' is not supported for sport '{sport}'.")

            except Exception as e:
                self.logger.error(f"Error scraping market '{market}': {e}")
                market_data[f"{market}_market"] = None

        # Handle grouped markets in preview mode
        if preview_submarkets_only and market_groups:
            for main_market_name, grouped_markets in market_groups.items():
                try:
                    self.logger.info(
                        f"Scraping main market: {main_market_name} for submarkets: {grouped_markets} (Period: {period})"
                    )

                    # Use the first market in the group to get the odds labels
                    first_market = grouped_markets[0]
                    if first_market in market_methods:
                        main_market_info = self.market_grouping.get_main_market_info(market_methods[first_market])
                        odds_labels = main_market_info["odds_labels"] if main_market_info else None

                        # Scrape the main market once
                        main_market_data = await self.extract_market_odds(
                            page=page,
                            main_market=main_market_name,
                            specific_market=None,  # No specific market, scrape all submarkets
                            period=period,
                            odds_labels=odds_labels,
                            scrape_odds_history=scrape_odds_history,
                            target_bookmaker=target_bookmaker,
                            preview_submarkets_only=preview_submarkets_only,
                            sport=sport,
                        )

                        # Distribute the results to each specific market
                        for specific_market in grouped_markets:
                            market_data[f"{specific_market}_market"] = main_market_data

                except Exception as e:
                    self.logger.error(f"Error scraping grouped markets for {main_market_name}: {e}")
                    for specific_market in grouped_markets:
                        market_data[f"{specific_market}_market"] = None

        return market_data

    async def _discover_line_names(self, page: Page, main_market: str, sport: str, period: str) -> list[str]:
        """
        Navigate to a main-market tab and enumerate the rendered line names (e.g. "Over/Under +2.5").

        Args:
            page (Page): The Playwright page instance.
            main_market (str): The main market name (e.g., "Over/Under", "Asian Handicap").
            sport (str): The sport being scraped.
            period (str): The match period (e.g., "FullTime").

        Returns:
            list[str]: The rendered submarket names currently visible on the page.
        """
        if not await self.navigation_manager.navigate_to_market_tab(page=page, market_tab_name=main_market):
            self.logger.warning(f"Failed to find or click {main_market} tab while discovering lines")
            return []

        await self.navigation_manager.wait_for_market_switch(page, main_market)

        submarkets = await self.submarket_extractor.extract_visible_submarkets_passive(
            page=page, main_market=main_market, period=period
        )
        return [submarket["submarket_name"] for submarket in submarkets if submarket.get("submarket_name")]

    async def extract_market_odds(
        self,
        page: Page,
        main_market: str,
        specific_market: str | None = None,
        period: str = "FullTime",
        odds_labels: list | None = None,
        scrape_odds_history: bool = False,
        target_bookmaker: str | None = None,
        preview_submarkets_only: bool = False,
        sport: str | None = None,
    ) -> list:
        """
        Extracts odds for a given main market and optional specific sub-market.

        Args:
            page (Page): The Playwright page instance.
            main_market (str): The main market name (e.g., "Over/Under", "European Handicap").
            specific_market (str, optional): The specific market within the main market (e.g., "Over/Under 2.5", ...)
            period (str): The match period (e.g., "FullTime").
            odds_labels (list): Labels corresponding to odds values in the extracted data.
            scrape_odds_history (bool): Whether to scrape and attach odds history.
            target_bookmaker (str): If set, only scrape odds for this bookmaker.
            preview_submarkets_only (bool): If True, only scrape the collapsed submarket odds (best/highest shown
            per line, not per-bookmaker) from visible submarkets.
            sport (str): The sport being scraped (used for period selection).

        Returns:
            list[dict]: A list of dictionaries containing bookmaker odds.
        """
        self.logger.info(
            f"Scraping odds for market: {main_market}, specific: {specific_market}, period: {period}, "
            f"preview_mode: {preview_submarkets_only}"
        )

        try:
            # Navigate to the main market tab
            if not await self.navigation_manager.navigate_to_market_tab(page=page, market_tab_name=main_market):
                self.logger.error(f"Failed to find or click {main_market} tab")
                return []

            # Wait for market switch to complete
            await self.navigation_manager.wait_for_market_switch(page, main_market)

            # Ensure correct period is selected after market switch. Prefer the
            # language-independent scope code (works on localized mirrors, §7);
            # fall back to localized-label matching when no scope is verified.
            if sport:
                period_enum = SportPeriodRegistry.from_internal_value(period, sport)
                if period_enum:
                    scope_selected = await self.period_selector.select_by_scope(
                        page=page, sport=sport, internal_period=period
                    )
                    if scope_selected is None:
                        display_label = period_enum.get_display_label(period_enum)
                        await self.selection_manager.ensure_selected(
                            page=page,
                            target_value=display_label,
                            display_label=display_label,
                            strategy=PERIOD_STRATEGY,
                        )
                else:
                    self.logger.debug(f"Period selection skipped for sport: {sport}")

            # Handle different scraping modes
            if preview_submarkets_only:
                # For preview mode, always try passive extraction first
                self.logger.info(f"Using passive mode for {main_market} in preview mode")
                odds_data = await self.submarket_extractor.extract_visible_submarkets_passive(
                    page=page, main_market=main_market, period=period, odds_labels=odds_labels
                )

                # If no data was extracted passively, fall back to normal scraping
                if not odds_data:
                    self.logger.info(f"No data extracted passively for {main_market}, falling back to normal scraping")
                    if specific_market and not await self.navigation_manager.select_specific_market(
                        page=page, specific_market=specific_market, main_market=main_market
                    ):
                        self.logger.error(f"Failed to find or select {specific_market} within {main_market}")
                        return []

                    await self.navigation_manager.wait_for_page_load(page)
                    html_content = await page.content()

                    odds_data = self.odds_parser.parse_market_odds(
                        html_content=html_content,
                        period=period,
                        odds_labels=odds_labels,
                        target_bookmaker=target_bookmaker,
                    )
            else:
                # Active mode: click on specific submarket if provided
                if specific_market and not await self.navigation_manager.select_specific_market(
                    page=page, specific_market=specific_market, main_market=main_market
                ):
                    self.logger.error(f"Failed to find or select {specific_market} within {main_market}")
                    return []

                await self.navigation_manager.wait_for_page_load(page)
                html_content = await page.content()

                odds_data = self.odds_parser.parse_market_odds(
                    html_content=html_content, period=period, odds_labels=odds_labels, target_bookmaker=target_bookmaker
                )

            if scrape_odds_history:
                self.logger.info("Fetching odds history for all parsed bookmakers.")

                for odds_entry in odds_data:
                    bookmaker_name = odds_entry.get("bookmaker_name")

                    if not bookmaker_name or (target_bookmaker and bookmaker_name.lower() != target_bookmaker.lower()):
                        continue

                    modals = await self.odds_history_extractor.extract_odds_history_for_bookmaker(page, bookmaker_name)

                    if modals:
                        all_histories = []
                        for modal_html in modals:
                            parsed_history = self.odds_parser.parse_odds_history_modal(modal_html)
                            if parsed_history:
                                all_histories.append(parsed_history)

                        odds_entry["odds_history_data"] = all_histories

            # Close the sub-market after scraping to avoid duplicates
            if specific_market:
                await self.navigation_manager.close_specific_market(page, specific_market, main_market=main_market)

            return odds_data

        except Exception as e:
            self.logger.error(f"Error extracting odds for {main_market} {specific_market}: {e}")
            return []
