"""
League Season Aliases - for leagues that changed sponsor names.

Some leagues on OddsPortal change their URL slug when sponsors change.
For example, Czech Republic's top league was "fortuna-liga" until 2023-2024,
then became "chance-liga" from 2024-2025 onwards.

This module provides a mapping to resolve the correct slug for a given season.
"""

import re

from .sport_market_constants import Sport

# League Season Aliases
# Format: canonical_name -> {max_year: alias_slug}
# - canonical_name: The league name as defined in SPORTS_LEAGUES_URLS_MAPPING
# - max_year: The LAST season start year that uses this alias
# - alias_slug: The URL slug to use for seasons up to and including max_year
#
# Seasons after max_year use the canonical (default) slug from SPORTS_LEAGUES_URLS_MAPPING
LEAGUE_SEASON_ALIASES: dict[Sport, dict[str, dict[int, str]]] = {
    Sport.FOOTBALL: {
        # Czech Republic: fortuna-liga until 2023-2024, then chance-liga
        "czech-republic-chance-liga": {
            2023: "fortuna-liga",  # 2023-2024 and earlier use fortuna-liga
        },
        # Slovakia: fortuna-liga until 2023-2024, then nike-liga
        "slovakia-nike-liga": {
            2023: "fortuna-liga",  # 2023-2024 and earlier use fortuna-liga
        },
        # Serbia: super-liga is always mozzart-bet-super-liga on OddsPortal
        "serbia-super-liga": {
            2099: "mozzart-bet-super-liga",  # Always use mozzart-bet prefix
        },
        # Hungary: otp-bank-liga until some season, then different name
        # Note: Need to verify exact transition year
        "hungary-nb-i": {
            2023: "otp-bank-liga",  # 2023-2024 and earlier use otp-bank-liga
        },
        # Cyprus: cyta-championship until 2023-2024, then cyprus-league
        "cyprus-league": {
            2023: "cyta-championship",  # 2023-2024 and earlier use cyta-championship
        },
        # Israel: ligat-ha-al (with hyphen, not ligat-haal)
        "israel-ligat-ha-al": {
            2099: "ligat-ha-al",  # Always use ligat-ha-al
        },
    },
}


def get_league_slug_for_season(sport: Sport, league: str, season: str | None) -> str:
    """
    Get the actual OddsPortal URL slug for a league, considering season-based aliases.

    Some leagues change names due to sponsor changes (e.g., Czech fortuna-liga -> chance-liga).
    This function returns the correct slug for the given season.

    Args:
        sport: The sport enum
        league: The canonical league name (as defined in SPORTS_LEAGUES_URLS_MAPPING)
        season: The season string (e.g., "2023-2024" or "2023" or None for current)

    Returns:
        The actual slug to use in the URL (may differ from canonical name for old seasons)

    Examples:
        >>> get_league_slug_for_season(Sport.FOOTBALL, "czech-republic-chance-liga", "2023-2024")
        'fortuna-liga'
        >>> get_league_slug_for_season(Sport.FOOTBALL, "czech-republic-chance-liga", "2024-2025")
        'chance-liga'
    """
    # If no aliases defined for this sport or league, return canonical name
    if sport not in LEAGUE_SEASON_ALIASES:
        return league
    if league not in LEAGUE_SEASON_ALIASES[sport]:
        return league

    aliases = LEAGUE_SEASON_ALIASES[sport][league]

    # Parse season to get start year
    if not season:
        return league  # Current season uses canonical name

    # Extract start year from season
    if re.match(r"^\d{4}-\d{4}$", season):
        start_year = int(season.split("-")[0])
    elif re.match(r"^\d{4}$", season):
        start_year = int(season)
    else:
        return league  # Unknown format, use canonical

    # Find applicable alias: use the alias where start_year <= max_year
    for max_year, alias_slug in sorted(aliases.items()):
        if start_year <= max_year:
            return alias_slug

    # No alias applies, use canonical name
    return league
