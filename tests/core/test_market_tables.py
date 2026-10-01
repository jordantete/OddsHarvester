"""The hand-kept market tables agree, sport by sport: enums, SPORT_MARKETS_MAPPING, registry, tab codes."""

import pytest

from oddsharvester.core.base_scraper import BaseScraper
from oddsharvester.core.market_extraction.line_tokens import line_name_to_token
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.sport_market_registry import SportMarketRegistrar, SportMarketRegistry
from oddsharvester.utils.sport_market_constants import FOOTBALL_UMBRELLA_MARKETS, Sport
from oddsharvester.utils.utils import get_supported_markets

# Measured before the duplicated rugby and ice hockey members went; a new market updates its sport's count.
ACCEPTED_TOKEN_COUNTS = {
    Sport.FOOTBALL: 65,
    Sport.TENNIS: 148,
    Sport.BASKETBALL: 214,
    Sport.RUGBY_LEAGUE: 42,
    Sport.RUGBY_UNION: 42,
    Sport.ICE_HOCKEY: 16,
    Sport.BASEBALL: 13,
    Sport.AMERICAN_FOOTBALL: 149,
    Sport.HANDBALL: 55,
    Sport.VOLLEYBALL: 113,
    Sport.CRICKET: 1,
}
RUGBY_TOKENS = {
    "1x2",
    "home_away",
    "dnb",
    "double_chance",
    *(f"over_under_{n}_5" for n in (32, 35, 36, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 55)),
    *(f"handicap_{sign}{n}_5" for sign in "+-" for n in (4, 5, 8, 9, 10, 11, 12, 13, 16, 17)),
}
ICE_HOCKEY_TOKENS = {"1x2", "home_away", "dnb", "btts", "double_chance", *(f"over_under_{n}_5" for n in range(1, 12))}


@pytest.fixture(scope="module")
def registry():
    SportMarketRegistry._registry = {}
    SportMarketRegistrar.register_all_markets()
    return {sport: dict(SportMarketRegistry.get_market_mapping(sport.value)) for sport in Sport}


@pytest.mark.parametrize("sport", list(Sport))
def test_supported_markets_list_each_token_once(sport):
    tokens = get_supported_markets(sport)
    assert sorted({t for t in tokens if tokens.count(t) > 1}) == []


@pytest.mark.parametrize("sport", list(Sport))
def test_supported_markets_are_the_registry_tokens(sport, registry):
    assert set(get_supported_markets(sport)) == set(registry[sport])


@pytest.mark.parametrize("sport", list(Sport))
def test_each_sport_accepts_as_many_tokens_as_before(sport):
    assert len(set(get_supported_markets(sport))) == ACCEPTED_TOKEN_COUNTS[sport]


@pytest.mark.parametrize(
    ("sport", "tokens"),
    [(Sport.RUGBY_LEAGUE, RUGBY_TOKENS), (Sport.RUGBY_UNION, RUGBY_TOKENS), (Sport.ICE_HOCKEY, ICE_HOCKEY_TOKENS)],
)
def test_rugby_and_ice_hockey_accept_the_tokens_they_accepted_before(sport, tokens):
    assert set(get_supported_markets(sport)) == tokens


@pytest.mark.parametrize("sport", list(Sport))
def test_every_main_market_has_a_tab_code(sport, registry):
    main_markets = {spec.main_market for spec in registry[sport].values()}
    assert main_markets - set(OddsPortalSelectors.MARKET_TAB_CODES) == set()


def test_football_line_tokens_round_trip(registry):
    lines = {
        token: spec
        for token, spec in registry[Sport.FOOTBALL].items()
        if spec.main_market in FOOTBALL_UMBRELLA_MARKETS.values()
    }

    assert lines
    assert {token: line_name_to_token(spec.main_market, spec.specific_market) for token, spec in lines.items()} == {
        token: token for token in lines
    }


def test_default_market_codes_name_sports_and_tab_codes():
    codes = BaseScraper._DEFAULT_MARKET_CODE_BY_SPORT
    assert set(codes) - {sport.value for sport in Sport} == set()
    assert set(codes.values()) - set(OddsPortalSelectors.MARKET_TAB_CODES.values()) == set()


@pytest.mark.parametrize("sport", list(Sport))
def test_each_sport_opens_on_a_tab_it_registers(sport, registry):
    """A sport left out of _DEFAULT_MARKET_CODE_BY_SPORT opens on 1X2, a tab two-outcome sports lack."""
    code = BaseScraper._DEFAULT_MARKET_CODE_BY_SPORT.get(sport.value, "1X2")
    assert code in {OddsPortalSelectors.MARKET_TAB_CODES[spec.main_market] for spec in registry[sport].values()}
