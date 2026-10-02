"""Unit tests for the match-view hydration helper; its recipe is pinned through BaseScraper._hydrate_match_view."""

import pytest

from oddsharvester.core.browser.hydration import default_market_code


@pytest.mark.parametrize(
    ("sport", "code"),
    [
        ("tennis", "home-away"),
        ("Basketball", "home-away"),
        ("american-football", "home-away"),
        ("football", "1X2"),
        ("hockey", "1X2"),
        ("", "1X2"),
        (None, "1X2"),
    ],
)
def test_a_view_opens_on_the_default_market_of_its_sport(sport, code):
    assert default_market_code(sport) == code
