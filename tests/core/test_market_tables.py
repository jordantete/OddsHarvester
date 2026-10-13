"""The hand-kept market tables agree, sport by sport: enums, SPORT_MARKETS_MAPPING, registry, tab codes."""

import pytest

from oddsharvester.core.browser.hydration import DEFAULT_MARKET_CODE_BY_SPORT, default_market_code
from oddsharvester.core.market_extraction.line_tokens import line_name_to_token
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.sport_market_registry import SportMarketRegistrar, SportMarketRegistry
from oddsharvester.utils.sport_market_constants import UMBRELLA_MARKETS, Sport
from oddsharvester.utils.utils import get_supported_markets

# Measured before the duplicated rugby and ice hockey members went; a new market updates its sport's count.
ACCEPTED_TOKEN_COUNTS = {
    Sport.FOOTBALL: 66,
    Sport.TENNIS: 148,
    Sport.BASKETBALL: 426,
    Sport.RUGBY_LEAGUE: 328,
    Sport.RUGBY_UNION: 328,
    Sport.ICE_HOCKEY: 26,
    Sport.BASEBALL: 33,
    Sport.AMERICAN_FOOTBALL: 228,
    Sport.HANDBALL: 124,
    Sport.VOLLEYBALL: 113,
    Sport.CRICKET: 1,
}
RUGBY_TOKENS = {
    "1x2",
    "home_away",
    "dnb",
    "double_chance",
    *(f"over_under_{n}_5" for n in range(20, 91)),
    *(f"over_under_{n}_0" for n in range(21, 91)),
    *(f"handicap_{sign}{n}_5" for sign in "+-" for n in range(46)),
    *(f"handicap_{sign}{n}_0" for sign in "+-" for n in range(1, 46)),
    "handicap_0",
}
ICE_HOCKEY_TOKENS = {
    "1x2",
    "home_away",
    "dnb",
    "btts",
    "double_chance",
    *(f"over_under_{n}_5" for n in range(1, 12)),
    *(f"over_under_{n}_0" for n in range(2, 12)),
}


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
def test_rugby_and_ice_hockey_accept_exactly_their_tokens(sport, tokens):
    assert set(get_supported_markets(sport)) == tokens


@pytest.mark.parametrize("sport", list(Sport))
def test_every_main_market_has_a_tab_code(sport, registry):
    main_markets = {spec.main_market for spec in registry[sport].values()}
    assert main_markets, f"{sport.value} registers no market"
    assert main_markets - set(OddsPortalSelectors.MARKET_TAB_CODES) == set()


@pytest.mark.parametrize("sport", list(UMBRELLA_MARKETS))
def test_umbrella_line_tokens_round_trip(sport, registry):
    tabs = set(UMBRELLA_MARKETS[sport].values())
    lines = {token: spec for token, spec in registry[sport].items() if spec.main_market in tabs}

    assert {spec.main_market for spec in lines.values()} == tabs
    assert {
        token: line_name_to_token(sport.value, spec.main_market, spec.specific_market) for token, spec in lines.items()
    } == {token: token for token in lines}


@pytest.mark.parametrize("sport", list(UMBRELLA_MARKETS))
def test_an_umbrella_token_is_never_a_concrete_token(sport, registry):
    assert set(UMBRELLA_MARKETS[sport]) & set(registry[sport]) == set()


def test_every_umbrella_tab_has_a_tab_code():
    tabs = {tab for umbrellas in UMBRELLA_MARKETS.values() for tab in umbrellas.values()}
    assert tabs - set(OddsPortalSelectors.MARKET_TAB_CODES) == set()


@pytest.mark.parametrize("sport", [sport for sport in UMBRELLA_MARKETS if sport is not Sport.FOOTBALL])
def test_each_umbrella_ladder_steps_by_half_a_point(sport, registry):
    """An umbrella opens only lines that have a token, so a gap in a ladder is a line it skips."""
    for tab in UMBRELLA_MARKETS[sport].values():
        values = {
            float(spec.specific_market.rsplit(" ", 1)[-1])
            for spec in registry[sport].values()
            if spec.main_market == tab
        }
        lo, hi = min(values), max(values)
        expected = {lo + step / 2 for step in range(round((hi - lo) * 2) + 1)}
        assert sorted(expected - values) == [], f"{sport.value} {tab} misses lines"


def test_default_market_codes_name_sports_and_tab_codes():
    codes = DEFAULT_MARKET_CODE_BY_SPORT
    assert codes
    assert set(codes) - {sport.value for sport in Sport} == set()
    assert set(codes.values()) - set(OddsPortalSelectors.MARKET_TAB_CODES.values()) == set()


@pytest.mark.parametrize("sport", list(Sport))
def test_each_sport_opens_on_a_tab_it_registers(sport, registry):
    """A sport left out of DEFAULT_MARKET_CODE_BY_SPORT opens on 1X2, a tab two-outcome sports lack."""
    code = default_market_code(sport.value)
    assert code in {OddsPortalSelectors.MARKET_TAB_CODES[spec.main_market] for spec in registry[sport].values()}
