"""Maps rendered Over/Under and Asian Handicap line names back to their CLI market tokens.

Inverts the formatting `SportMarketRegistry.register_football_markets` applies when building
`specific_market` for each token (see `sport_market_registry.py`).
"""

from enum import Enum
import re

from oddsharvester.utils.sport_market_constants import FootballAsianHandicapMarket, FootballOverUnderMarket

_LINE_NUMBER_RE = re.compile(r"[+-]?\d+(?:\.\d+)?")

# main_market -> (token prefix, enum whose .value set is authoritative, whether the token keeps the sign)
_MARKET_CONFIG: dict[str, tuple[str, type[Enum], bool]] = {
    "Over/Under": ("over_under_", FootballOverUnderMarket, False),
    "Asian Handicap": ("asian_handicap_", FootballAsianHandicapMarket, True),
}


def line_name_to_token(main_market: str, line_name: str) -> str | None:
    """Map a rendered line name (e.g. "Over/Under +2.5") to its CLI token (e.g. "over_under_2_5").

    The line is the name's last whitespace token, so a localized name ("Más/Menos de +2.5")
    maps to the same token. Returns None if `main_market` is not a recognized umbrella market,
    the name does not end with a number, or the resulting token isn't a valid enum value.
    """
    config = _MARKET_CONFIG.get(main_market)
    words = line_name.split()
    if config is None or not words or not _LINE_NUMBER_RE.fullmatch(words[-1]):
        return None

    token_prefix, enum_cls, keep_sign = config
    number = words[-1] if keep_sign else words[-1].removeprefix("+")
    token = token_prefix + number.replace(".", "_")
    valid_values = {member.value for member in enum_cls}
    return token if token in valid_values else None
