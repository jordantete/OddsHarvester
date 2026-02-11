"""
League season aliases for leagues that changed sponsor names.

Some leagues on OddsPortal change their URL slug when sponsors change.
For example, Czech Republic's top league was "fortuna-liga" until 2023-2024,
then became "chance-liga" from 2024-2025 onwards.

This module provides a mapping to resolve the correct URL slug for a given season.
"""

import re

from .sport_market_constants import Sport

# League Season Aliases
# Format: canonical_league_key -> {max_year: url_slug}
# - canonical_league_key: The league key as defined in SPORTS_LEAGUES_URLS_MAPPING
# - max_year: The LAST season start year that uses this alias
# - url_slug: The URL slug to use for seasons up to and including max_year
#
# Seasons after max_year use the canonical (default) slug from SPORTS_LEAGUES_URLS_MAPPING
LEAGUE_SEASON_ALIASES: dict[Sport, dict[str, dict[int, str]]] = {
    Sport.FOOTBALL: {
        # Czech Republic: fortuna-liga until 2023-2024, then chance-liga
        "czech-republic-chance-liga": {
            2023: "fortuna-liga",
        },
        # Slovakia: fortuna-liga until 2023-2024, then nike-liga
        "slovakia-nike-liga": {
            2023: "fortuna-liga",
        },
        # Hungary: otp-bank-liga until 2023-2024, then nb-i
        "hungary-nb-i": {
            2023: "otp-bank-liga",
        },
        # Cyprus: cyta-championship until 2023-2024, then 1st-division
        "cyprus-first-division": {
            2023: "cyta-championship",
        },
    },
}


def get_league_slug_for_season(sport: Sport, league: str, season: str | None) -> str | None:
    """
    Get the aliased URL slug for a league if it differs from the canonical one for the given season.

    Some leagues change URL slugs due to sponsor changes (e.g., Czech fortuna-liga -> chance-liga).
    This function returns the correct slug for the given season, or None if no alias applies.

    Args:
        sport: The sport enum.
        league: The canonical league key (as defined in SPORTS_LEAGUES_URLS_MAPPING).
        season: The season string (e.g., "2023-2024" or "2023" or None for current).

    Returns:
        The aliased URL slug to use, or None if no alias applies for this league/season.
    """
    if sport not in LEAGUE_SEASON_ALIASES or league not in LEAGUE_SEASON_ALIASES[sport]:
        return None

    if not season:
        return None

    if re.match(r"^\d{4}-\d{4}$", season):
        start_year = int(season.split("-")[0])
    elif re.match(r"^\d{4}$", season):
        start_year = int(season)
    else:
        return None

    aliases = LEAGUE_SEASON_ALIASES[sport][league]
    for max_year, alias_slug in sorted(aliases.items()):
        if start_year <= max_year:
            return alias_slug

    return None
