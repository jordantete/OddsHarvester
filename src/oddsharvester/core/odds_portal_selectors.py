from typing import ClassVar


class OddsPortalSelectors:
    """Centralized CSS selectors for OddsPortal website elements."""

    # Cookie banner
    COOKIE_BANNER = "#onetrust-accept-btn-handler"

    # Market navigation tabs
    MARKET_TAB_SELECTORS: ClassVar[list[str]] = [
        "ul.visible-links.bg-black-main.odds-tabs > li",
        "ul.odds-tabs > li",
        "ul[class*='odds-tabs'] > li",
        "div[class*='odds-tabs'] li",
        "li[class*='tab']",
        "nav li",
    ]

    # "More" dropdown button selectors
    MORE_BUTTON_SELECTORS: ClassVar[list[str]] = [
        "button.toggle-odds:has-text('More')",
        "button[class*='toggle-odds']",
        ".visible-btn-odds:has-text('More')",
        "li:has-text('More')",
        "li:has-text('more')",
        "li[class*='more']",
        "li button:has-text('More')",
        "li a:has-text('More')",
    ]

    # Market navigation - sub-market selection
    SUB_MARKET_SELECTOR = "div.flex.w-full.items-center.justify-start.pl-3.font-bold p"

    # Bookmaker filter navigation
    BOOKIES_FILTER_CONTAINER = "div[data-testid='bookies-filter-nav']"
    BOOKIES_FILTER_ACTIVE_CLASS = "active-item-calendar"

    # Period selection navigation
    PERIOD_SELECTOR_CONTAINER = "div[data-testid='kickoff-events-nav']"
    PERIOD_ACTIVE_CLASS = "active-item-calendar"

    @staticmethod
    def get_dropdown_selectors_for_market(market_name: str) -> list[str]:
        """Generate dropdown selectors for a specific market name."""
        return [
            f"li:has-text('{market_name}')",
            f"a:has-text('{market_name}')",
            f"button:has-text('{market_name}')",
            f"div:has-text('{market_name}')",
            f"span:has-text('{market_name}')",
        ]

    @staticmethod
    def get_bookies_filter_selector(filter_value: str) -> str:
        """
        Generate selector for a specific bookmaker filter option.

        Args:
            filter_value: The filter value (e.g., 'all', 'classic', 'crypto').

        Returns:
            str: CSS selector for the filter option.
        """
        return f"div[data-testid='bookies-filter-nav'] div[data-testid='{filter_value}']"

    # Bookmaker elements — BeautifulSoup class patterns
    BOOKMAKER_ROW_CLASS = "border-black-borders"
    BOOKMAKER_ROW_FALLBACK_CLASS = r"^border-black-borders flex h-9"
    BOOKMAKER_LOGO_CLASS = "bookmaker-logo"
    ODDS_BLOCK_CLASS_PATTERN = r"flex-center.*flex-col.*font-bold"

    # Bookmaker elements — Playwright CSS selectors
    BOOKMAKER_ROW_CSS = "div.border-black-borders.flex.h-9"
    BOOKMAKER_LOGO_CSS = "img.bookmaker-logo"
    ODDS_BLOCK_CSS = "div.flex-center.flex-col.font-bold"
    ODDS_MOVEMENT_HEADER = "h3:text('Odds movement')"

    # Event listing — BeautifulSoup class pattern
    EVENT_ROW_CLASS_PATTERN = "^eventRow"

    # Submarket name — BeautifulSoup class
    SUBMARKET_CLEAN_NAME_CLASS = "max-sm:!hidden"

    # Debug selectors
    DROPDOWN_DEBUG_ELEMENTS = "li, a, button, div, span"
