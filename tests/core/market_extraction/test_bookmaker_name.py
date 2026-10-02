import logging

from oddsharvester.core.market_extraction.bookmaker_name import bookmaker_match_key, resolve_bookmaker_name


def test_visible_text_wins_over_title():
    assert resolve_bookmaker_name(" bet365 ", "Go to bet365 website!") == "bet365"


def test_cta_title_is_normalised():
    assert resolve_bookmaker_name(None, "Go to Betfair Exchange website!") == "Betfair Exchange"


def test_cta_title_without_website_suffix():
    assert resolve_bookmaker_name(None, "Go to 1xBet!") == "1xBet"


def test_plain_title_is_kept():
    assert resolve_bookmaker_name("", "Pinnacle") == "Pinnacle"


def test_no_source_gives_none():
    assert resolve_bookmaker_name("  ", None) is None
    assert resolve_bookmaker_name(None, "") is None


def test_a_logo_only_row_takes_the_name_its_link_slug_stands_for():
    assert resolve_bookmaker_name(None, None, "/proxy/bookmakers/unibet-fr/link/") == "Unibet.fr"
    assert resolve_bookmaker_name("", "", "/proxy/bookmakers/bwin-fr/link/") == "bwin.fr"


def test_label_and_title_win_over_the_link():
    assert resolve_bookmaker_name("bet365", None, "/proxy/bookmakers/unibet-fr/link/") == "bet365"
    assert resolve_bookmaker_name(None, "Pinnacle", "/proxy/bookmakers/unibet-fr/link/") == "Pinnacle"


def test_an_unknown_slug_names_the_row_after_the_slug_and_warns(caplog):
    with caplog.at_level(logging.WARNING):
        assert resolve_bookmaker_name(None, None, "/proxy/bookmakers/pinnacle/link/") == "pinnacle"

    assert "pinnacle" in caplog.text


def test_a_link_without_a_slug_gives_none():
    assert resolve_bookmaker_name(None, None, "/proxy/bookmakers/") is None
    assert resolve_bookmaker_name(None, None, None) is None


def test_match_key_ignores_whitespace_and_case():
    assert bookmaker_match_key("Betfair  Exchange\n") == bookmaker_match_key("betfairexchange")
    assert bookmaker_match_key("Betfair") != bookmaker_match_key("Betfair Exchange")
