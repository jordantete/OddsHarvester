import re
from typing import ClassVar


class OddsPortalSelectors:
    """Centralized CSS selectors for OddsPortal website elements."""

    # Cookie banner
    COOKIE_BANNER = "#onetrust-accept-btn-handler"

    # 2026-08 redesign (issue #85). Digits are <button>s, the current page a <span>;
    # the widget's parent stays display:none until the listing is scrolled to the
    # bottom, so read text_content (not inner_text) on the items.
    PAGINATION_CONTAINER = "nav.pagination"
    PAGINATION_ITEM = "nav.pagination button, nav.pagination span"

    # Listing rows and their date grouping (redesign): rows carry
    # data-testid='game-row'; date headers are siblings (inside a
    # 'secondary-header' element), not children of the first row of a group.
    LISTING_ROW_SELECTOR = "div[data-testid='game-row']"
    DATE_HEADER_TESTID = "date-header"

    # Match view (redesign): content renders only after an in-page hashchange to
    # '#<id>:<market>;<scope>'; game-time-item is the hydration-complete signal.
    MATCH_CONTENT_READY_SELECTOR = "div[data-testid='game-time-item']"

    # Market tabs (redesign)
    MARKET_TAB_ACTIVE = "[data-testid='sports-nav-active-tab']"
    MARKET_TAB_ANY = "[data-testid='sports-nav-active-tab'], [data-testid='sports-nav-inactive-tab']"

    # Sub-nav row: bookies filter (All/Classic/Crypto Bookies) and period tabs.
    SUB_NAV_TAB_ANY = "[data-testid='sub-nav-active-tab'], [data-testid='sub-nav-inactive-tab']"
    SUB_NAV_TAB_ACTIVE_TESTID = "sub-nav-active-tab"

    # Odds table (redesign): one <tr> per bookmaker; peripheral rows to skip.
    BOOKMAKER_NAME_TESTID = "outrights-expanded-bookmaker-name"
    BOOKMAKER_NAME_CSS = "[data-testid='outrights-expanded-bookmaker-name']"
    BOOKMAKER_ROW_WITH_NAME_CSS = "tr:has([data-testid='outrights-expanded-bookmaker-name'])"
    ODD_CELL_CSS = "[data-testid^='odd-container']"
    ODD_CELL_TESTID_PREFIX = "odd-container"
    PAYOUT_TESTID = "payout-container"
    TABLE_SKIP_ROW_TESTIDS: ClassVar[tuple[str, ...]] = ("my-coupon-row", "user-predictions-row", "odds-alert-row")

    # Login modal observed blocking match-page rendering on cold profiles.
    LOGIN_MODAL_CLOSE = "[data-testid='modal'] button[aria-label='Close']"

    @staticmethod
    def page_fragment(n: int) -> str:
        """Listing page fragment for the redesigned SPA ('#page/N', no leading slash)."""
        return f"#page/{n}"

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

    # Market navigation - sub-market selection. Line rows are clickable <tr>s
    # whose full label sits in a span (redesign); click the enclosing <tr>.
    SUB_MARKET_SELECTOR = "tr.cursor-pointer span"
    SUB_MARKET_CLICK_ANCESTOR = "tr"

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
        "cricket": {"FullIncludingOT": 1},
    }

    # Match details — data-testid values for DOM-based extraction
    # (used by base_scraper._extract_match_details DOM helpers)
    MATCH_DETAILS_GAME_TIME_TESTID = "game-time-item"
    MATCH_DETAILS_GAME_HOST_TESTID = "game-host"
    MATCH_DETAILS_GAME_GUEST_TESTID = "game-guest"
    MATCH_DETAILS_BREADCRUMBS_TESTID = "breadcrumbs-line"

    # Community Top Predictions page (/predictions/). All data-testid based; see
    # docs/agentic-gotchas.md (community predictions entry).
    COMMUNITY_LEAGUE_HEADER = "div[data-testid='sport-country-league-item']"
    COMMUNITY_OUTCOME_HEADER = "div[data-testid='betting-tip-header']"
    COMMUNITY_GAME_ROW = "div[data-testid='game-row']"
    COMMUNITY_DATE_TIME = "div[data-testid='date-time-item']"
    COMMUNITY_PARTICIPANTS = "div[data-testid='event-participants']"
    COMMUNITY_PARTICIPANT_NAME = "[data-testid='participant-name']"
    COMMUNITY_ODD_CELL = "p[data-testid='odd-container-default']"
    COMMUNITY_PREDICTION_CELL = "div[data-testid='prediction-container']"
    COMMUNITY_BREADCRUMB_SPORT = "a[data-testid='header-sport-item']"
    COMMUNITY_BREADCRUMB_COUNTRY = "a[data-testid='header-country-item']"
    COMMUNITY_BREADCRUMB_LEAGUE = "a[data-testid='header-tournament-item']"

    # Community user profile page (/users/<username>/). Header renders even when
    # private; the pick marker ('prediction-pick-item') is matched as a raw
    # data-testid inside a document-order descendants loop, not a CSS selector.
    COMMUNITY_PROFILE_USERNAME = "[data-testid='username']"
    COMMUNITY_PROFILE_ROI = "[data-testid='user-roi']"
    COMMUNITY_PROFILE_MEMBER_INFO = "[data-testid='member-info']"
    COMMUNITY_PROFILE_STATS_HEADER = "[data-testid='stats-table-header-line']"
    # Profile sub-tabs (Feed / Followers / Following); the active one carries
    # 'tab-navigation-active-tab' instead.
    COMMUNITY_PROFILE_TAB = "[data-testid='navigation-inactive-tab']"

    # Live (in-play) pages. `live-info` is the match-page live header (period,
    # score, partial result); it disappears once the match ends. `game-row` is
    # the listing row testid shared with community pages.
    LIVE_INFO_TESTID = "live-info"
    LIVE_PARTIAL_RESULT_TESTID = "partial-result"
    GAME_ROW_TESTID = "game-row"

    @staticmethod
    def event_id_from_url(url: str) -> str | None:
        """Return the event id from a '#<id>' or '#<id>:<market>;<scope>' fragment, else None."""
        if not isinstance(url, str) or "#" not in url:
            return None
        fragment = url.split("#", 1)[1].strip().split(":", 1)[0]
        if not fragment or "/" in fragment:
            return None
        return fragment

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

    # OddsPortal strikes through an odds value when the feed's per-outcome `act`
    # flag is false (bookmaker no longer offering that bet). A CSS selector, not a
    # class regex: soupsieve matches class tokens exactly. See gotchas §18.
    ODDS_BLOCKED_SELECTOR = ".line-through"
    # Match the tooltip header by class: its text is localized on regional mirrors.
    ODDS_MOVEMENT_HEADER = "h3.font-semibold.uppercase.leading-6"

    # Per-row status indicators on the listing page (issue #58 / gotchas §9).
    # Both are required to detect started matches: live flips only time-item,
    # finished fills only game-status-box.
    EVENT_ROW_TIME_ITEM_TESTID = "time-item"
    EVENT_ROW_GAME_STATUS_BOX_TESTID = "game-status-box"

    # Submarket name — BeautifulSoup class
    SUBMARKET_CLEAN_NAME_CLASS = "max-sm:hidden"
