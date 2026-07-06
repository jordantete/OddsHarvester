"""Maps rendered Over/Under and Asian Handicap line names back to their CLI market tokens.

Inverts the formatting `SportMarketRegistry.register_football_markets` applies when building
`specific_market` for each token (see `sport_market_registry.py`).
"""

from enum import Enum

from oddsharvester.utils.sport_market_constants import FootballAsianHandicapMarket, FootballOverUnderMarket

# main_market -> (line_name prefix to strip, token prefix, enum whose .value set is authoritative)
_MARKET_CONFIG: dict[str, tuple[str, str, type[Enum]]] = {
    "Over/Under": ("Over/Under +", "over_under_", FootballOverUnderMarket),
    "Asian Handicap": ("Asian Handicap ", "asian_handicap_", FootballAsianHandicapMarket),
}


def line_name_to_token(main_market: str, line_name: str) -> str | None:
    """Map a rendered line name (e.g. "Over/Under +2.5") to its CLI token (e.g. "over_under_2_5").

    Returns None if `main_market` is not a recognized umbrella market, `line_name` doesn't match
    the expected format, or the resulting token isn't a valid enum value.
    """
    config = _MARKET_CONFIG.get(main_market)
    if config is None:
        return None

    prefix, token_prefix, enum_cls = config
    if not line_name.startswith(prefix):
        return None

    remainder = line_name[len(prefix) :]
    if not remainder:
        return None

    token = token_prefix + remainder.replace(".", "_")
    valid_values = {member.value for member in enum_cls}
    return token if token in valid_values else None
