"""Maps a rendered line name back to its CLI market token by inverting the sport's registry labels."""

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.sport_market_registry import SportMarketRegistry


def line_name_to_token(sport: str, main_market: str, line_name: str) -> str | None:
    """Map a rendered line name (e.g. "Over/Under +2.5") to its CLI token (e.g. "over_under_2_5").

    The line is the name's last whitespace token, so a localized name ("Más/Menos de +2.5") maps to the
    same token. Returns None when no token of `sport` under `main_market` has that line, when two do, or
    when the name is a bare number (a row's bookmaker count).
    """
    words = line_name.split()
    if not words or line_name.strip().isdigit():
        return None
    return _tokens_by_line(sport, main_market).get(words[-1])


def _tokens_by_line(sport: str, main_market: str) -> dict[str, str]:
    """The tab's lines, each keyed by the text the row click matches, without the lines two tokens share."""
    tokens: dict[str, list[str]] = {}
    for token, spec in SportMarketRegistry.get_market_mapping(sport).items():
        if spec.main_market == main_market and spec.specific_market is not None:
            line = OddsPortalSelectors.submarket_match_text(spec.specific_market, main_market)
            tokens.setdefault(line, []).append(token)
    return {line: shared[0] for line, shared in tokens.items() if len(shared) == 1}
