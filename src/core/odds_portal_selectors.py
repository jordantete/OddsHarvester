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

    # Debug selectors
    DROPDOWN_DEBUG_ELEMENTS = "li, a, button, div, span"
