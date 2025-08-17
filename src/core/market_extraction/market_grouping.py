import logging
from typing import Any


class MarketGrouping:
    """Handles grouping of markets by their main market type for optimization."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_main_market_info(self, market_method) -> dict[str, Any] | None:
        """
        Extract main market information from a market method lambda.

        Args:
            market_method: The market method lambda function

        Returns:
            dict | None: Dictionary with main_market and odds_labels, or None if not found
        """
        try:
            # The market method is a lambda that calls extract_market_odds with specific parameters
            # We can inspect its closure to get the main_market and odds_labels
            if hasattr(market_method, "__closure__") and market_method.__closure__:
                # Extract the main_market and odds_labels from the lambda's closure
                closure_vars = market_method.__code__.co_freevars
                closure_values = [cell.cell_contents for cell in market_method.__closure__]

                # Find main_market and odds_labels in the closure
                main_market = None
                odds_labels = None

                for var_name, var_value in zip(closure_vars, closure_values, strict=False):
                    if var_name == "main_market":
                        main_market = var_value
                    elif var_name == "odds_labels":
                        odds_labels = var_value

                if main_market:
                    return {"main_market": main_market, "odds_labels": odds_labels}
        except Exception as e:
            self.logger.debug(f"Could not extract market info from method: {e}")

        return None

    def group_markets_by_main_market(self, markets: list[str], market_methods: dict) -> dict[str, list[str]]:
        """
        Group markets by their main market type for optimization in preview mode.

        Args:
            markets: List of market names to group
            market_methods: Dictionary of market methods from SportMarketRegistry

        Returns:
            dict: Dictionary mapping main market names to lists of grouped markets
        """
        market_groups = {}

        for market in markets:
            if market in market_methods:
                # Get the main market info from the existing market method
                main_market_info = self.get_main_market_info(market_methods[market])
                if main_market_info:
                    main_market_name = main_market_info["main_market"]
                    if main_market_name not in market_groups:
                        market_groups[main_market_name] = []
                    market_groups[main_market_name].append(market)

        return market_groups
