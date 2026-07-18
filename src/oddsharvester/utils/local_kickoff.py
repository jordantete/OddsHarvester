"""Convert a stored UTC match_date to the venue's local kickoff time."""

from datetime import UTC, datetime
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from oddsharvester.utils.venue_timezone_constants import resolve_venue_timezone

logger = logging.getLogger(__name__)

_UTC_MATCH_DATE_FORMAT = "%Y-%m-%d %H:%M:%S %Z"
_LOCAL_OUTPUT_FORMAT = "%Y-%m-%d %H:%M:%S %Z%z"


def compute_local_kickoff(
    match_date_utc: str | None,
    country: str | None,
    town: str | None,
) -> tuple[str | None, str | None]:
    """Return (venue_timezone, match_date_venue_local).

    venue_timezone is the resolved IANA id (or None). match_date_venue_local
    is the kickoff rendered in that zone with an explicit offset, or None when
    the venue is unresolved or match_date_utc cannot be parsed. Never raises.

    A missing (falsy) match_date_utc short-circuits to (None, None) before
    venue resolution; an unparseable but present date yields (venue_timezone, None).
    """
    if not match_date_utc:
        return None, None

    venue_timezone = resolve_venue_timezone(country, town)
    if venue_timezone is None:
        return None, None

    try:
        naive = datetime.strptime(match_date_utc, _UTC_MATCH_DATE_FORMAT)
        aware_utc = naive.replace(tzinfo=UTC)
        local_dt = aware_utc.astimezone(ZoneInfo(venue_timezone))
        return venue_timezone, local_dt.strftime(_LOCAL_OUTPUT_FORMAT)
    except (ValueError, ZoneInfoNotFoundError) as e:
        logger.warning(f"Could not convert match_date '{match_date_utc}' to {venue_timezone}: {e}")
        return venue_timezone, None
