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
        # Czech Republic: synot-liga until 2015/2016 ,1-liga for 2016/2018, then fortuna-liga until 2023-2024, and chance-liga
        "czech-republic-chance-liga": {
            2023: "fortuna-liga",
            2017: "1-liga",
            2015: "synot-liga",
        },
        # Slovakia: fortuna-liga until 2022-2023, then nike-liga
        "slovakia-nike-liga": {
            2022: "fortuna-liga",
        },
        # Romania: liga-1 until 2023-2024, then superliga
        "romania-superliga": {
            2023: "liga-1",
        },
        # Norway: tippeligaen until 2016, then eliteserien
        "norway-eliteserien": {
            2016: "tippeligaen",
        },
        # Hungary: otp-bank-liga until 2023-2024, then nb-i
        "hungary-nb-i": {
            2023: "otp-bank-liga",
        },
        # Chile: primera-division until 2024, then liga-de-primera from 2025
        "chile-primera-division": {
            2024: "primera-division",
        },
        # Brazil: serie-a until 2023, then serie-a-betano from 2024
        "brazil-serie-a": {
            2023: "serie-a",
        },
        # Brazil: serie-b until 2024, then serie-b-superbet from 2025
        "brazil-serie-b": {
            2024: "serie-b",
        },
        # Spain: primera-division until 2015, then laliga from 2016
        "spain-laliga": {
            2015: "primera-division",
        },
        # Spain2: segunda-division until 2015, then laliga2 from 2016
        "spain-laliga2": {
            2015: "segunda-division",
        },
        # Mexico: primera-division until 2018, then liga-mx from 2019
        "mexico-liga-mx": {
            2018: "primera-division",
        },
        # Europe: europa-conference-league until 2023, then conference-league from 2024
        "conference-league": {
            2023: "europa-conference-league",
        },
        # Portugal: primeira-liga until 2020, then liga-portugal from 2021
        "liga-portugal": {
            2020: "primeira-liga",
        },
        # Colombia: primera-liga until 2020, then liga-aguila up to 2019, then liga-postobon from 2014
        "colombia-primera-a": {
            2019: "liga-aguila",
            2014: "liga-postobon",
        },
        # South Africa: premier-league until 2023-2024, then betway-premiership
        "south-africa-premiership": {
            2023: "premier-league",
        },
        # Bulgaria: parva-liga until 2024-2025, then efbet-league from 2025-2026
        # (also a-pfg until 2015-2016, but parva-liga alias covers the more recent range)
        "bulgaria-parva-liga": {
            2024: "parva-liga",
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
