import re
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

    # Every market tab (visible + 'More' overflow) carries the `odds-item` class.
    MARKET_TAB_ITEM_SELECTOR = "li.odds-item"

    # `data-testid='more-button'` is language-independent (text is localized).
    MORE_BUTTON_SELECTORS: ClassVar[list[str]] = [
        "button[data-testid='more-button']",
        "button.toggle-odds:has-text('More')",
        "button[class*='toggle-odds']",
        ".visible-btn-odds:has-text('More')",
        "li:has-text('More')",
        "li:has-text('more')",
        "li[class*='more']",
        "li button:has-text('More')",
        "li a:has-text('More')",
    ]

    # English main_market -> language-independent market code in the URL fragment
    # (e.g. '#<id>:over-under;2'). Localized-mirror fallback; see gotchas §7.
    MARKET_TAB_CODES: ClassVar[dict[str, str]] = {
        "1X2": "1X2",
        "Home/Away": "home-away",
        "Over/Under": "over-under",
        "Asian Handicap": "ah",
        "European Handicap": "eh",
        "Handicap": "ah",  # rugby: no standalone 'Handicap' tab; preserves prior substring behaviour
        "Both Teams to Score": "bts",
        "Correct Score": "cs",
        "Double Chance": "double",
        "Draw No Bet": "dnb",
    }

    # Market navigation - sub-market selection
    SUB_MARKET_SELECTOR = "div.flex.w-full.items-center.justify-start.pl-3.font-bold p"

    # Bookmaker filter navigation
    BOOKIES_FILTER_CONTAINER = "div[data-testid='bookies-filter-nav']"
    BOOKIES_FILTER_ACTIVE_CLASS = "active-item-calendar"

    # Period selection navigation
    PERIOD_SELECTOR_CONTAINER = "div[data-testid='kickoff-events-nav']"
    PERIOD_ACTIVE_CLASS = "active-item-calendar"
    # Real period tabs carry data-testid='sub-nav-active-tab'/'sub-nav-inactive-tab';
    # peripheral entries (e.g. a 'Todos los bonos' bonus link) do not.
    PERIOD_TAB_SELECTOR = f"{PERIOD_SELECTOR_CONTAINER} > div[data-testid^='sub-nav-']"

    # Language-independent period scope codes — the ';<scope>' segment of the URL
    # fragment ('#<id>:<market>;<scope>'). Scope ids are global OddsPortal period
    # ids, identical across localized mirrors (gotchas §7). Only values verified
    # live are listed; unverified (sport, period) pairs return None and fall back
    # to localized-label matching. Verified: FT=2 (football/tennis/baseball).
    PERIOD_SCOPE_CODES_UNIVERSAL: ClassVar[dict[str, int]] = {
        "FullTime": 2,
    }
    # Per-sport because the same enum name can map to a different scope: baseball
    # 'FirstHalf' renders as '1st Inning' (scope 17), not the football half (3).
    PERIOD_SCOPE_CODES_BY_SPORT: ClassVar[dict[str, dict[str, int]]] = {
        "football": {"FirstHalf": 3, "SecondHalf": 4},
        "tennis": {"FirstSet": 12},
        "baseball": {"FullIncludingOT": 1},
    }

    # Match details — data-testid values for DOM-based extraction
    # (used by base_scraper._extract_match_details_event_header DOM helpers)
    MATCH_DETAILS_GAME_TIME_TESTID = "game-time-item"
    MATCH_DETAILS_GAME_HOST_TESTID = "game-host"
    MATCH_DETAILS_GAME_GUEST_TESTID = "game-guest"
    MATCH_DETAILS_BREADCRUMBS_TESTID = "breadcrumbs-line"
    MATCH_DETAILS_BREADCRUMB_LEAGUE_TESTID = "3"

    @staticmethod
    def market_code_from_url(url: str) -> str | None:
        """Return the market code from a `#<id>:<code>;<scope>` fragment, else None."""
        if not isinstance(url, str) or "#" not in url:
            return None
        fragment = url.split("#", 1)[1]
        if ":" not in fragment:
            return None
        return fragment.split(":", 1)[1].split(";", 1)[0]

    @staticmethod
    def period_scope_from_url(url: str) -> int | None:
        """Return the period scope int from a `#<id>:<market>;<scope>` fragment, else None."""
        if not isinstance(url, str) or "#" not in url:
            return None
        fragment = url.split("#", 1)[1]
        if ";" not in fragment:
            return None
        match = re.match(r"\d+", fragment.rsplit(";", 1)[1])
        return int(match.group()) if match else None

    @staticmethod
    def period_scope_code(sport: str | None, internal_period: str) -> int | None:
        """Return the verified language-independent scope code for (sport, period), else None.

        Per-sport overrides win over the universal map. None means "not verified" —
        the caller should fall back to localized-label matching (gotchas §7).
        """
        by_sport = OddsPortalSelectors.PERIOD_SCOPE_CODES_BY_SPORT.get((sport or "").lower(), {})
        if internal_period in by_sport:
            return by_sport[internal_period]
        return OddsPortalSelectors.PERIOD_SCOPE_CODES_UNIVERSAL.get(internal_period)

    @staticmethod
    def submarket_match_text(specific_market: str, main_market: str | None = None) -> str:
        """Return the language-independent portion of a submarket label.

        On localized mirrors only the main-market prefix is translated
        ('Over/Under' -> 'Más/Menos de'); the numeric line + axis word
        ('+20.5 Games') is identical across mirrors. Stripping the English
        main-market prefix lets the substring match in
        PageScroller.scroll_until_visible_and_click_parent work on every mirror
        (gotchas §7). The retained '+'/'-'/':' guards against adjacent-line
        collisions. Falls back to the full label when no prefix is given or it
        is not present.
        """
        if main_market and specific_market.startswith(main_market):
            tail = specific_market[len(main_market) :].strip()
            if tail:
                return tail
        return specific_market

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
    # Scope marker: the bookmaker table header sits inside the container that holds
    # only the real bookmaker rows. Used to scope row search and skip peripheral
    # sections (Previous Matches, H2H, etc.) whose rows share `border-black-borders`.
    BOOKMAKER_TABLE_HEADER_TESTID = "bookmaker-table-header-line"

    # Bookmaker elements — Playwright CSS selectors
    BOOKMAKER_ROW_CSS = "div.border-black-borders.flex.h-9"
    BOOKMAKER_LOGO_CSS = "img.bookmaker-logo"
    ODDS_BLOCK_CSS = "div.flex-center.flex-col.font-bold"
    # Match the tooltip header by class: its text is localized on regional mirrors.
    ODDS_MOVEMENT_HEADER = "h3.font-semibold.uppercase.leading-6"

    # Event listing — BeautifulSoup class pattern
    EVENT_ROW_CLASS_PATTERN = "^eventRow"
    # Per-row status indicators on the listing page (issue #58 / gotchas §9).
    # Both are required to detect started matches: live flips only time-item,
    # finished fills only game-status-box.
    EVENT_ROW_TIME_ITEM_TESTID = "time-item"
    EVENT_ROW_GAME_STATUS_BOX_TESTID = "game-status-box"

    # Submarket name — BeautifulSoup class
    SUBMARKET_CLEAN_NAME_CLASS = "max-sm:!hidden"

    # Debug selectors
    DROPDOWN_DEBUG_ELEMENTS = "li, a, button, div, span"
