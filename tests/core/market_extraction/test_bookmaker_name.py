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


def test_match_key_ignores_whitespace_and_case():
    assert bookmaker_match_key("Betfair  Exchange\n") == bookmaker_match_key("betfairexchange")
    assert bookmaker_match_key("Betfair") != bookmaker_match_key("Betfair Exchange")
