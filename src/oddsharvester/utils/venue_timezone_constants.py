"""Venue country/town to IANA timezone resolution for local kickoff times.

Keys match the raw strings OddsPortal emits in venueCountry / venueTown
(e.g. "England", not an ISO code). Single-timezone countries live in
COUNTRY_TIMEZONES; countries with several zones need a per-town lookup in
MULTI_TZ_CITY_TIMEZONES. Resolution never guesses: an unknown country or an
unmatched town in a multi-timezone country returns None.
"""

# Single-timezone countries seen in the supported leagues. Extend as new
# leagues are added; unresolved venues are logged at scrape time.
COUNTRY_TIMEZONES: dict[str, str] = {
    "England": "Europe/London",
    "Scotland": "Europe/London",
    "Wales": "Europe/London",
    "Northern Ireland": "Europe/London",
    "Ireland": "Europe/Dublin",
    "France": "Europe/Paris",
    "Germany": "Europe/Berlin",
    "Spain": "Europe/Madrid",
    "Italy": "Europe/Rome",
    "Portugal": "Europe/Lisbon",
    "Netherlands": "Europe/Amsterdam",
    "Belgium": "Europe/Brussels",
    "Switzerland": "Europe/Zurich",
    "Austria": "Europe/Vienna",
    "Greece": "Europe/Athens",
    "Turkey": "Europe/Istanbul",
    "Poland": "Europe/Warsaw",
    "Czech Republic": "Europe/Prague",
    "Croatia": "Europe/Zagreb",
    "Serbia": "Europe/Belgrade",
    "Denmark": "Europe/Copenhagen",
    "Norway": "Europe/Oslo",
    "Sweden": "Europe/Stockholm",
    "Japan": "Asia/Tokyo",
    "Qatar": "Asia/Qatar",
    "Saudi Arabia": "Asia/Riyadh",
}

# Countries spanning multiple zones: resolve by host city. Town keys are
# stored pre-normalized (lowercased) and looked up via _normalize_town.
MULTI_TZ_CITY_TIMEZONES: dict[str, dict[str, str]] = {
    "USA": {
        "atlanta": "America/New_York",
        "boston": "America/New_York",
        "miami": "America/New_York",
        "new york": "America/New_York",
        "philadelphia": "America/New_York",
        "washington": "America/New_York",
        "chicago": "America/Chicago",
        "dallas": "America/Chicago",
        "houston": "America/Chicago",
        "kansas city": "America/Chicago",
        "denver": "America/Denver",
        "phoenix": "America/Phoenix",
        "los angeles": "America/Los_Angeles",
        "san francisco": "America/Los_Angeles",
        "seattle": "America/Los_Angeles",
    },
    "Canada": {
        "toronto": "America/Toronto",
        "montreal": "America/Toronto",
        "vancouver": "America/Vancouver",
        "calgary": "America/Edmonton",
        "edmonton": "America/Edmonton",
        "winnipeg": "America/Winnipeg",
    },
    "Mexico": {
        "mexico city": "America/Mexico_City",
        "guadalajara": "America/Mexico_City",
        "monterrey": "America/Monterrey",
    },
    "Brazil": {
        "rio de janeiro": "America/Sao_Paulo",
        "sao paulo": "America/Sao_Paulo",
        "belo horizonte": "America/Sao_Paulo",
        "porto alegre": "America/Sao_Paulo",
        "salvador": "America/Bahia",
        "manaus": "America/Manaus",
    },
    "Russia": {
        "moscow": "Europe/Moscow",
        "saint petersburg": "Europe/Moscow",
        "st petersburg": "Europe/Moscow",
        "kazan": "Europe/Moscow",
        "yekaterinburg": "Asia/Yekaterinburg",
    },
    "Australia": {
        "sydney": "Australia/Sydney",
        "melbourne": "Australia/Melbourne",
        "brisbane": "Australia/Brisbane",
        "perth": "Australia/Perth",
        "adelaide": "Australia/Adelaide",
    },
}


def _normalize_town(town: str) -> str:
    return town.strip().casefold()


def resolve_venue_timezone(country: str | None, town: str | None) -> str | None:
    """Return an IANA timezone id for a venue, or None when unresolved.

    Never raises. Single-timezone countries resolve from country alone;
    multi-timezone countries require a matching town.
    """
    if not country:
        return None

    if country in COUNTRY_TIMEZONES:
        return COUNTRY_TIMEZONES[country]

    city_map = MULTI_TZ_CITY_TIMEZONES.get(country)
    if city_map and town:
        return city_map.get(_normalize_town(town))

    return None
