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
