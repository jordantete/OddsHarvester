from bs4 import BeautifulSoup
import pytest
from tests.dom_builders import (
    bookmaker_row,
    date_header,
    line_row,
    listing_row,
    match_header,
    odds_table,
    page,
    trap_row,
)

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.sport_period_registry import SportPeriodRegistry
from oddsharvester.utils.sport_market_constants import Sport


def test_event_id_from_url_returns_fragment_when_present():
    url = "https://www.oddsportal.com/baseball/h2h/a-team/b-team/#WbDmMwm1"
    assert OddsPortalSelectors.event_id_from_url(url) == "WbDmMwm1"


def test_event_id_from_url_returns_none_when_no_fragment():
    assert OddsPortalSelectors.event_id_from_url("https://www.oddsportal.com/baseball/h2h/a/b/") is None


def test_event_id_from_url_returns_none_when_fragment_is_empty():
    assert OddsPortalSelectors.event_id_from_url("https://www.oddsportal.com/baseball/h2h/a/b/#") is None


def test_event_id_from_url_returns_none_when_fragment_has_slash():
    # Defensive: a stray slash means it isn't a match-id fragment
    assert OddsPortalSelectors.event_id_from_url("https://www.oddsportal.com/x/#a/b") is None


def test_event_id_from_url_strips_whitespace():
    # Some scrapers can produce trailing whitespace from raw href
    assert OddsPortalSelectors.event_id_from_url("https://www.oddsportal.com/x/#abc   ") == "abc"


def test_event_id_from_url_strips_market_suffix():
    # The hydrated SPA rewrites the fragment to '<id>:<market>;<scope>'.
    assert OddsPortalSelectors.event_id_from_url("https://www.oddsportal.com/x/h2h/a/b/#OOklm0j3:1X2;2") == "OOklm0j3"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj:bts;2",
            "https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj",
        ),  # names a market
        (
            "https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj:over-under;2;2.50;0",
            "https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj",
        ),  # a line
        (
            "https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj",
            "https://www.oddsportal.com/football/h2h/a-x/b-y/#UNC9hLMj",
        ),  # bare event
        (
            "https://www.oddsportal.com/football/h2h/a-x/b-y/",
            "https://www.oddsportal.com/football/h2h/a-x/b-y/",
        ),  # no fragment
        (
            "https://www.oddsportal.com/football/england/premier-league-2024-2025/results/#/page/2/",
            "https://www.oddsportal.com/football/england/premier-league-2024-2025/results/#/page/2/",
        ),  # listing fragment
    ],
)
def test_event_url_reduces_fragment_to_the_bare_event_id(url, expected):
    assert OddsPortalSelectors.event_url(url) == expected


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


@pytest.mark.parametrize(
    ("label", "line", "expected"),
    [
        ("Asian Handicap -1", "-1", True),
        ("Hándicap asiático -1", "-1", True),
        ("Asian Handicap -1AH -1", "-1", True),
        ("Asian Handicap -1.75", "-1", False),
        ("Asian Handicap -1.75AH -1.75", "-1", False),
        ("Over/Under +20.5", "+20.5", True),
        ("Over/Under +120.5", "+20.5", False),
        ("Over/Under +2.25", "+2", False),
        ("Asian Handicap 0", "0", True),
        ("0", "0", False),
        ("2:0", "2:0", True),
        ("-", "-1", False),
        ("", "-1", False),
        ("Asian Handicap -1", "", False),
    ],
)
def test_line_label_matches_the_exact_line_at_the_end(label, line, expected):
    assert OddsPortalSelectors.line_label_matches(label, line) is expected


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


def test_period_scope_codes_are_the_site_period_ids():
    """Read from every period tab of one match per sport on 2026-09-29; baseball 1st Half is 3 too."""
    assert OddsPortalSelectors.PERIOD_SCOPE_CODES_UNIVERSAL == {
        "FullIncludingOT": 1,
        "FullTime": 2,
        "FirstHalf": 3,
        "SecondHalf": 4,
        "FirstPeriod": 5,
        "SecondPeriod": 6,
        "ThirdPeriod": 7,
        "FirstQuarter": 8,
        "SecondQuarter": 9,
        "ThirdQuarter": 10,
        "FourthQuarter": 11,
        "FirstSet": 12,
        "SecondSet": 13,
        "ThirdSet": 14,
        "FourthSet": 15,
        "FifthSet": 16,
    }


def test_every_period_of_every_sport_has_a_scope_code():
    pairs = []
    for sport in Sport:
        period_enum = SportPeriodRegistry.get_period_enum(sport.value)
        pairs += [(sport.value, period_enum.get_internal_value(period)) for period in period_enum]

    assert len(pairs) == 41
    assert [pair for pair in pairs if OddsPortalSelectors.period_scope_code(pair[1]) is None] == []


def test_period_scope_code_of_an_unknown_period_is_none():
    assert OddsPortalSelectors.period_scope_code("NotAPeriod") is None


def test_odds_movement_header_is_language_independent():
    # Header text is i18n-translated on localized mirrors; match by class, not text.
    selector = OddsPortalSelectors.ODDS_MOVEMENT_HEADER
    assert selector == "h3.font-semibold.uppercase.leading-6"
    assert ":text(" not in selector
    assert "Odds movement" not in selector


class TestRedesignSelectors:
    """Selectors for a DOM carrying no data-testid (issue #86)."""

    def test_page_fragment(self):
        assert OddsPortalSelectors.page_fragment(1) == "#page/1"
        assert OddsPortalSelectors.page_fragment(12) == "#page/12"

    def test_pagination_selectors(self):
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


class TestIsHidden:
    """A link is hidden when it or one of its ancestors carries the trap attribute or a hiding inline style."""

    def test_no_style_attr_is_visible(self):
        row = BeautifulSoup(listing_row("/football/h2h/a/b/#x"), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is False

    def test_empty_style_is_visible(self):
        row = BeautifulSoup(listing_row("/football/h2h/a/b/#x", style=""), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is False

    def test_left_minus_9999_marks_offscreen(self):
        row = BeautifulSoup(listing_row("/football/h2h/a/b/#x", style="position: absolute; left: -9999px;"), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is True

    def test_top_minus_9999_marks_offscreen(self):
        row = BeautifulSoup(listing_row("/football/h2h/a/b/#x", style="top:-9999px"), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is True

    def test_display_none_marks_offscreen(self):
        row = BeautifulSoup(listing_row("/football/h2h/a/b/#x", style="display: none;"), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is True

    def test_visibility_hidden_marks_offscreen(self):
        row = BeautifulSoup(listing_row("/football/h2h/a/b/#x", style="visibility:hidden"), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is True

    def test_uppercase_style_normalized(self):
        row = BeautifulSoup(listing_row("/football/h2h/a/b/#x", style="DISPLAY: NONE"), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is True

    def test_unrelated_style_is_visible(self):
        row = BeautifulSoup(listing_row("/football/h2h/a/b/#x", style="color: red; padding-left: 9999px;"), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is False

    def test_the_trap_clone_hides_its_link(self):
        row = BeautifulSoup(trap_row(listing_row("/football/h2h/a-37e4f5e9/b-5a49c1bd/")), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is True

    def test_the_trap_attribute_alone_hides_its_link(self):
        row = BeautifulSoup(trap_row(listing_row("/football/h2h/a/b/"), style=""), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is True

    def test_an_offscreen_ancestor_alone_hides_its_link(self):
        row = BeautifulSoup(trap_row(listing_row("/football/h2h/a/b/"), trap_attribute=False), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is True

    def test_an_aria_hidden_ancestor_alone_keeps_the_link(self):
        """A modal can mark the whole page aria-hidden while it is open, so that attribute alone is no trap."""
        row = BeautifulSoup(trap_row(listing_row("/football/h2h/a/b/#x"), trap_attribute=False, style=""), "lxml").a
        assert OddsPortalSelectors.is_hidden(row) is False
