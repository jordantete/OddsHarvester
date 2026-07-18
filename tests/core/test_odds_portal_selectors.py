from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors


def test_match_details_testid_constants_exist():
    assert OddsPortalSelectors.MATCH_DETAILS_GAME_TIME_TESTID == "game-time-item"
    assert OddsPortalSelectors.MATCH_DETAILS_GAME_HOST_TESTID == "game-host"
    assert OddsPortalSelectors.MATCH_DETAILS_GAME_GUEST_TESTID == "game-guest"
    assert OddsPortalSelectors.MATCH_DETAILS_BREADCRUMBS_TESTID == "breadcrumbs-line"
    assert OddsPortalSelectors.MATCH_DETAILS_BREADCRUMB_LEAGUE_TESTID == "3"


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
