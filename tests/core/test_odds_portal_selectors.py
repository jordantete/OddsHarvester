from bs4 import BeautifulSoup
from tests.dom_builders import bookmaker_row, date_header, line_row, listing_row, match_header, odds_table, page

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors


def test_market_code_from_url_extracts_code():
    url = "https://www.cuotasahora.com/football/h2h/cabo-verde-x/uruguay-y/#4pPp9nn3:over-under;2"
    assert OddsPortalSelectors.market_code_from_url(url) == "over-under"


def test_market_code_from_url_default_active_tab():
    assert OddsPortalSelectors.market_code_from_url("https://x/#abcd:1X2;2") == "1X2"


def test_market_code_from_url_no_market_segment():
    # Fragment with only the match id (before any market tab is clicked).
    assert OddsPortalSelectors.market_code_from_url("https://x/#abcd") is None


def test_market_code_from_url_no_fragment():
    assert OddsPortalSelectors.market_code_from_url("https://x/football/h2h/a/b/") is None


def test_market_code_from_url_non_string():
    # Defensive against mocked Page.url in unit tests.
    assert OddsPortalSelectors.market_code_from_url(None) is None
    assert OddsPortalSelectors.market_code_from_url(12345) is None


def test_submarket_match_text_strips_main_market_prefix():
    # On localized mirrors only the main-market prefix is translated; the tail
    # ('+20.5 Games') is identical across mirrors, so we match on the tail.
    assert OddsPortalSelectors.submarket_match_text("Over/Under +20.5 Games", "Over/Under") == "+20.5 Games"
    assert OddsPortalSelectors.submarket_match_text("Asian Handicap -2.5 Sets", "Asian Handicap") == "-2.5 Sets"
    assert OddsPortalSelectors.submarket_match_text("European Handicap 0:1", "European Handicap") == "0:1"


def test_submarket_match_text_tail_is_substring_of_localized_label():
    # Real localized label observed on cuotasahora.com (issue #70 follow-up).
    tail = OddsPortalSelectors.submarket_match_text("Over/Under +20.5 Games", "Over/Under")
    assert tail in "Más/Menos de +20.5 Games"
    assert tail in "Over/Under +20.5 Games"  # still matches the English .com label
    # The '+' guards against adjacent-line collisions ('+2.5' must not match '+20.5').
    assert (
        OddsPortalSelectors.submarket_match_text("Over/Under +2.5 Sets", "Over/Under") not in "Más/Menos de +20.5 Sets"
    )


def test_submarket_match_text_falls_back_to_full_label():
    # No prefix given, or prefix not present -> use the label as-is.
    assert OddsPortalSelectors.submarket_match_text("Over/Under +20.5 Games") == "Over/Under +20.5 Games"
    assert OddsPortalSelectors.submarket_match_text("2:1", "Correct Score") == "2:1"


def test_period_scope_from_url_extracts_scope():
    # Period scope is the ';<scope>' segment of the fragment (gotchas §7).
    assert OddsPortalSelectors.period_scope_from_url("https://x/#IXkNtYcL:over-under;2") == 2
    assert OddsPortalSelectors.period_scope_from_url("https://x/#abcd:over-under;12") == 12


def test_period_scope_from_url_no_scope_segment():
    assert OddsPortalSelectors.period_scope_from_url("https://x/#abcd:over-under") is None
    assert OddsPortalSelectors.period_scope_from_url("https://x/#abcd") is None
    assert OddsPortalSelectors.period_scope_from_url("https://x/football/h2h/a/b/") is None


def test_period_scope_from_url_non_string():
    assert OddsPortalSelectors.period_scope_from_url(None) is None
    assert OddsPortalSelectors.period_scope_from_url(12345) is None


def test_period_scope_code_universal_full_time():
    # FullTime is scope 2 on every sport (verified football/tennis/baseball).
    assert OddsPortalSelectors.period_scope_code("tennis", "FullTime") == 2
    assert OddsPortalSelectors.period_scope_code("football", "FullTime") == 2
    assert OddsPortalSelectors.period_scope_code("ice-hockey", "FullTime") == 2


def test_period_scope_code_per_sport():
    assert OddsPortalSelectors.period_scope_code("football", "FirstHalf") == 3
    assert OddsPortalSelectors.period_scope_code("football", "SecondHalf") == 4
    assert OddsPortalSelectors.period_scope_code("tennis", "FirstSet") == 12
    assert OddsPortalSelectors.period_scope_code("baseball", "FullIncludingOT") == 1


def test_period_scope_code_unknown_returns_none():
    # Unverified periods fall back to label matching; scope lookup must not guess.
    assert OddsPortalSelectors.period_scope_code("basketball", "FirstQuarter") is None
    assert OddsPortalSelectors.period_scope_code("tennis", "SecondSet") is None
    # 'FirstHalf' is per-sport: verified for football, NOT generalized (baseball
    # 'FirstHalf' is actually '1st Inning' = scope 17, a different concept).
    assert OddsPortalSelectors.period_scope_code("baseball", "FirstHalf") is None


def test_period_scope_code_cricket_full_including_ot():
    assert OddsPortalSelectors.period_scope_code("cricket", "FullIncludingOT") == 1


def test_odds_movement_header_is_language_independent():
    # Header text is i18n-translated on localized mirrors; match by class, not text.
    selector = OddsPortalSelectors.ODDS_MOVEMENT_HEADER
    assert selector == "h3.font-semibold.uppercase.leading-6"
    assert ":text(" not in selector
    assert "Odds movement" not in selector


def test_market_tab_codes_cover_registry_main_markets():
    # Every distinct main_market label passed by sport_market_registry must map
    # to a stable code so the localized-mirror fallback can resolve it.
    expected = {
        "1X2",
        "Home/Away",
        "Over/Under",
        "Asian Handicap",
        "European Handicap",
        "Handicap",
        "Both Teams to Score",
        "Correct Score",
        "Double Chance",
        "Draw No Bet",
    }
    assert expected <= set(OddsPortalSelectors.MARKET_TAB_CODES)


class TestRedesignSelectors:
    """Selectors for a DOM carrying no data-testid (issue #86)."""

    def test_page_fragment(self):
        assert OddsPortalSelectors.page_fragment(1) == "#page/1"
        assert OddsPortalSelectors.page_fragment(12) == "#page/12"

    def test_pagination_selectors(self):
        assert OddsPortalSelectors.PAGINATION_CONTAINER == "nav.pagination"
        assert "button" in OddsPortalSelectors.PAGINATION_ITEM
        assert "span" in OddsPortalSelectors.PAGINATION_ITEM

    def test_content_root_is_the_innermost_main(self):
        soup = BeautifulSoup(page("<p>content</p>"), "lxml")
        root = OddsPortalSelectors.content_root(soup)
        assert root.get_text(strip=True) == "content"

    def test_content_root_falls_back_to_the_document(self):
        soup = BeautifulSoup("<div><p>content</p></div>", "lxml")
        assert OddsPortalSelectors.content_root(soup).get_text(strip=True) == "content"

    def test_is_match_link_matches_h2h_anchors_only(self):
        row = BeautifulSoup(listing_row("/football/h2h/a-1/b-2/#EV"), "lxml").find("a")
        other = BeautifulSoup('<a href="/football/england/premier-league/">League</a>', "lxml").find("a")
        assert OddsPortalSelectors.is_match_link(row) is True
        assert OddsPortalSelectors.is_match_link(other) is False

    def test_is_date_header_matches_group_dates(self):
        for text in ("04 Sep 2026", "Today, 02 Sep", "Today, 02 Sep  - Clausura", "18 April 2026"):
            el = BeautifulSoup(date_header(text), "lxml").find("div")
            assert OddsPortalSelectors.is_date_header(el) is True, text

    def test_is_date_header_rejects_labels_without_a_day_number(self):
        # The listing's "Today" nav filter must not register as a date header.
        el = BeautifulSoup(date_header("Today"), "lxml").find("div")
        assert OddsPortalSelectors.is_date_header(el) is False

    def test_is_date_header_rejects_non_leaf_elements(self):
        el = BeautifulSoup("<div><span>04 Sep 2026</span></div>", "lxml").find("div")
        assert OddsPortalSelectors.is_date_header(el) is False

    def test_match_header_helpers_locate_date_and_participants(self):
        soup = BeautifulSoup(match_header(home="Ipswich", away="Liverpool"), "lxml")
        assert OddsPortalSelectors.match_date_cell(soup).get_text(" ", strip=True) == "Friday, 04 Sep 2026, 21:00"
        title = OddsPortalSelectors.match_title_block(soup)
        names = [el.get_text(strip=True) for el in title.select(OddsPortalSelectors.PARTICIPANT_NAME_CSS)]
        assert names == ["Ipswich", "Liverpool"]

    def test_match_header_helpers_return_none_without_a_header(self):
        soup = BeautifulSoup(page("<div>no header</div>"), "lxml")
        assert OddsPortalSelectors.match_date_cell(soup) is None
        assert OddsPortalSelectors.match_title_block(soup) is None

    def test_bookmaker_rows_exclude_submarket_line_rows(self):
        html = odds_table(
            bookmaker_row("Betclic.fr", ["1.50", "3.00", "5.00"]) + line_row("Over/Under +2.5", ["1.40", "2.90"])
        )
        root = OddsPortalSelectors.content_root(BeautifulSoup(html, "lxml"))
        assert len(root.select(OddsPortalSelectors.BOOKMAKER_ROW_WITH_NAME_CSS)) == 1
        assert len(root.select(OddsPortalSelectors.SUBMARKET_LINE_ROW_CSS)) == 1

    def test_odds_cells_exclude_the_payout_column(self):
        html = odds_table(bookmaker_row("Betclic.fr", ["1.50", "3.00", "5.00"], payout="93.8%"))
        row = OddsPortalSelectors.content_root(BeautifulSoup(html, "lxml")).select_one(
            OddsPortalSelectors.BOOKMAKER_ROW_WITH_NAME_CSS
        )
        assert [c.get_text(strip=True) for c in row.select(OddsPortalSelectors.ODD_CELL_CSS)] == [
            "1.50",
            "3.00",
            "5.00",
        ]

    def test_login_modal_close_is_scoped_to_the_modal(self):
        assert OddsPortalSelectors.LOGIN_MODAL_CLOSE.startswith(".login-modal ")
