"""
League season aliases for leagues whose URL slug changed mid-history.

Some leagues on OddsPortal change their URL slug, usually when sponsors change.
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
#
# Read from the season selector on each <league>/results/ page, which lists every season
# with the slug it actually lives under (verified 2026-09-03).
LEAGUE_SEASON_ALIASES: dict[Sport, dict[str, dict[int, str]]] = {
    Sport.FOOTBALL: {
        "argentina-liga-profesional": {
            2016: "primera-division",
            2019: "superliga",
            2023: "liga-profesional",
        },
        "argentina-primera-nacional": {
            2018: "primera-b-nacional",
        },
        "austria-2-liga": {
            2007: "adeg-erste-liga",
            2017: "erste-liga",
        },
        "austria-bundesliga": {
            2002: "max-bundesliga",
            2007: "t-mobile-bundesliga",
            2013: "tipp3-bundesliga",
            2020: "tipico-bundesliga",
        },
        "belgium-challenger-pro-league": {
            2011: "exqi-league",
            2013: "belgacom-league",
            2019: "proximus-league",
            2021: "1b-pro-league",
        },
        "brazil-serie-a": {
            2023: "serie-a",
        },
        "brazil-serie-b": {
            2024: "serie-b",
        },
        "bulgaria-parva-liga": {
            2015: "a-pfg",
            2024: "parva-liga",
        },
        "chile-primera-division": {
            2024: "primera-division",
        },
        "colombia-primera-a": {
            2014: "liga-postobon",
            2019: "liga-aguila",
        },
        "concacaf-champions-cup": {
            2023: "concacaf-champions-league",
        },
        "conference-league": {
            2023: "europa-conference-league",
        },
        "croatia-hnl": {
            2021: "1-hnl",
        },
        "czech-republic-chance-liga": {
            2013: "gambrinus-liga",
            2015: "synot-liga",
            2017: "1-liga",
            2023: "fortuna-liga",
        },
        "denmark-1st-division": {
            2014: "nordicbet-ligaen",
            2015: "bet25-liga",
        },
        "ecuador-liga-pro": {
            2018: "serie-a",
        },
        "england-national-league": {
            2006: "nationwide-conference",
            2009: "blue-square-premier",
            2012: "blue-square-bet-premier",
            2013: "the-skrill-premier",
            2014: "vanarama-conference",
        },
        "europa-league": {
            2008: "uefa-cup",
        },
        "france-ligue-1": {
            2001: "division-1",
        },
        "france-ligue-2": {
            2001: "division-2",
        },
        "hungary-nb-i": {
            2024: "otp-bank-liga",
        },
        "indonesia-super-league": {
            2015: "super-liga",
            2016: "isc",
            2024: "liga-1",
        },
        "japan-j1-league": {
            2014: "j-league",
        },
        "jupiler-pro-league": {
            2020: "jupiler-league",
        },
        "liga-portugal": {
            2020: "primeira-liga",
        },
        "liga-portugal-2": {
            2011: "liga-de-honra",
            2015: "segunda-liga",
            2019: "ligapro",
        },
        "mexico-liga-de-expansion": {
            2018: "liga-de-ascenso",
            2019: "ascenso-mx",
        },
        "mexico-liga-mx": {
            2018: "primera-division",
        },
        "morocco-botola-pro": {
            2013: "botola",
        },
        "northern-ireland-nifl-premiership": {
            2012: "ifa-premiership",
        },
        "norway-eliteserien": {
            2016: "tippeligaen",
        },
        "paraguay-copa-de-primera": {
            2024: "primera-division",
        },
        "peru-liga-1": {
            2018: "primera-division",
        },
        "romania-superliga": {
            2023: "liga-1",
        },
        "scotland-championship": {
            2012: "division-1",
        },
        "scotland-premiership": {
            2012: "premier-league",
        },
        "serbia-super-liga": {
            2024: "super-liga",
        },
        "slovakia-nike-liga": {
            2001: "mars-superliga",
            2002: "1-liga",
            2013: "corgon-liga",
            2022: "fortuna-liga",
        },
        "south-africa-premiership": {
            2023: "premier-league",
        },
        "south-korea-k-league-1": {
            2012: "k-league",
            2017: "k-league-classic",
        },
        "spain-laliga": {
            2015: "primera-division",
        },
        "spain-laliga2": {
            2015: "segunda-division",
        },
        "thailand-thai-league-1": {
            2016: "thai-premier-league",
        },
        "turkey-1-lig": {
            2011: "bank-asya-1-lig",
            2015: "ptt-1-lig",
            2016: "tff-1-lig",
        },
        "ukraine-premier-league": {
            2016: "pari-match-league",
        },
        "uruguay-liga": {
            2024: "primera-division",
        },
        "usa-usl-championship": {
            2018: "usl",
        },
        "uzbekistan-super-league": {
            2017: "professional-football-league",
        },
        "wales-cymru-premier": {
            2013: "premier",
            2018: "premier-league",
        },
        "world-cup": {
            2022: "world-cup",
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
