import re
from typing import ClassVar


class OddsPortalSelectors:
    """Centralized CSS selectors for OddsPortal website elements."""

    # Cookie banner
    COOKIE_BANNER = "#onetrust-accept-btn-handler"

    # 2026-09 (issue #86): OddsPortal stripped every data-testid from the DOM.
    # Anchors are hrefs, HTML semantics and text shape; see gotchas §20.

    # The SPA nests page content in a second <main>; parsing is scoped to the
    # innermost one so sidebar widgets never leak into listing/match extraction.
    CONTENT_ROOT = "main"

    # 2026-08 redesign (issue #85). Digits are <button>s, the current page a <span>;
    # the widget's parent stays display:none until the listing is scrolled to the
    # bottom, so read text_content (not inner_text) on the items.
    PAGINATION_CONTAINER = "nav.pagination"
    PAGINATION_ITEM = "nav.pagination button, nav.pagination span"

    # Listing rows: each row is an <a> to the match H2H fragment URL. Its two
    # direct <div> children are the kickoff/status cell and the participants.
    LISTING_ROW_SELECTOR = 'a[href*="/h2h/"]'
    MATCH_LINK_HREF_SUBSTRING = "/h2h/"
    # Date headers: a leaf element whose whole text is the group date
    # ("04 Sep 2026", "Today, 02 Sep", "Today, 02 Sep  - Clausura"). The day
    # number is required so the "Today" nav filter is not read as a header.
    DATE_HEADER_RE = re.compile(
        r"^(?:(?:today|tomorrow|yesterday)\s*,\s*)?\d{1,2}\s+\w{3,}\.?(?:\s+\d{4})?(?:\s+-\s+.+)?$",
        re.IGNORECASE,
    )

    # Match view: the market tabs are the render-complete signal (they exist even
    # on a match with no bookmaker coverage).
    MATCH_CONTENT_READY_SELECTOR = "main li.tab-item"

    # Market tabs; the active one carries font-bold on its label span.
    MARKET_TAB_ANY = "li.tab-item"
    MARKET_TAB_ACTIVE = "li.tab-item:has(span.font-bold)"

    # Sub-nav row: bookies filter (All/Classic/Crypto Bookies) and period tabs,
    # plain buttons whose active one carries an inline font-weight.
    SUB_NAV_TAB_ANY = "main button[type='button']"
    SUB_NAV_ACTIVE_STYLE_MARKER = "font-weight: 700"

    # Odds table: one leaf <tr> per bookmaker, identified by its bookmaker links;
    # collapsed submarket line rows carry the expand arrow instead. Odds cells are
    # the odds-column <td>s that hold a value block (the submarket line label sits
    # in an odds column too, but is a bare span).
    ODDS_TABLE = "main table"
    BOOKMAKER_LINK_CSS = 'a[href*="/bookmakers/"]'
    BOOKMAKER_ROW_WITH_NAME_CSS = 'tr:has(a[href*="/bookmakers/"])'
    SUBMARKET_LINE_ROW_CSS = 'tr:has(img[alt="arrow"])'
    ODD_CELL_CSS = 'td[class*="event-table-odd-col"]:has(.font-bold)'
    ODD_COLUMN_CELL_CSS = 'td[class*="event-table-odd-col"]'

    # Login modal observed blocking match-page rendering on cold profiles.
    LOGIN_MODAL_CLOSE = ".login-modal button[aria-label='Close']"

    @staticmethod
    def content_root(soup):
        """Innermost <main>, i.e. the page content without nav, sidebars and footer."""
        mains = soup.find_all("main")
        return mains[-1] if mains else soup

    # The header's date cell holds weekday / date / time paragraphs; it is the
    # anchor for everything else in the header, which carries no stable attribute.
    MATCH_DATE_PARAGRAPH_RE = re.compile(r"^\d{1,2} \w{3} \d{4},?$")

    @staticmethod
    def match_date_cell(soup):
        """The match header's date cell, or None when the header is absent."""
        for div in OddsPortalSelectors.content_root(soup).find_all("div"):
            paragraphs = div.find_all("p", recursive=False)
            if len(paragraphs) >= 3 and OddsPortalSelectors.MATCH_DATE_PARAGRAPH_RE.match(
                paragraphs[1].get_text(strip=True)
            ):
                return div
        return None

    @staticmethod
    def match_title_block(soup):
        """The match header's participants row: home block, separator, away block."""
        date_cell = OddsPortalSelectors.match_date_cell(soup)
        header = date_cell.parent.parent if date_cell is not None and date_cell.parent is not None else None
        return header.find("div", recursive=False) if header is not None else None

    @staticmethod
    def is_date_header(el) -> bool:
        """True for a listing date-header element (a leaf holding only the group date)."""
        if el.find(True) is not None:
            return False
        text = el.get_text(" ", strip=True)
        return bool(text) and bool(OddsPortalSelectors.DATE_HEADER_RE.match(text))

    @staticmethod
    def is_match_link(el) -> bool:
        """True for a listing row: an <a> pointing at a match H2H fragment URL."""
        return el.name == "a" and OddsPortalSelectors.MATCH_LINK_HREF_SUBSTRING in (el.get("href") or "")

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

    # Participants: the two team/player labels of a listing row or match header,
    # truncated to their column.
    PARTICIPANT_NAME_CSS = "p.truncate, a.truncate"

    # Community Top Predictions page (/community/predictions/#sport/<sport>/):
    # one column per outcome, holding its label header, odds and vote percentage.
    COMMUNITY_ROW_READY_SELECTOR = 'main a[href*="/h2h/"]'
    COMMUNITY_OUTCOME_LABEL = "div[class*='bg-gray-light']"
    COMMUNITY_ODD_CELL = "p.font-bold"
    COMMUNITY_PICK_MARKER = ".user-pred-pick"

    # Community user profile page (/profile/<username>/). The header renders even
    # when the profile is private; the statistics are the page's only table and
    # the Feed / Followers / Following sub-tabs are ordinary tab items.
    COMMUNITY_PROFILE_USERNAME = "main h1"
    COMMUNITY_PROFILE_STATS_TABLE = "main table"
    COMMUNITY_PROFILE_TAB = "li.tab-item"

    # Live (in-play) pages: the header's live block (period, running score,
    # partial result) is marked by this pulse element and disappears once the
    # match ends.
    LIVE_INFO_MARKER = ".result-live"

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

    # Submarket name — BeautifulSoup class
    SUBMARKET_CLEAN_NAME_CLASS = "max-sm:hidden"
