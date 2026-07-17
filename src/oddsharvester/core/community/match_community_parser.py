"""Pure parser for a match page's embedded community vote data.

Input is the single dict evaluated in the browser by MatchCommunityScraper:
pageVar.predictionData.communityData ({total, count, group}) plus teams / start /
status read from the #react-event-header data JSON, and the aggregate pick text.

communityData decode:
- total[marketKey] = total votes for that market (denominator).
- group[encodedOutcomeId] = marketKey; count[encodedOutcomeId] = that outcome's votes.
  Inverting group yields, per market, the list of per-outcome counts.
Outcome LABELS (1/X/2, Over/Under) are not recoverable — the encoded ids are
obfuscated (gotchas §13) — so outcome_counts is emitted unlabeled, sorted desc.
"""

from datetime import UTC, datetime
import logging
import re

from oddsharvester.core.community.community_constants import BETTING_TYPE_NAMES, SCOPE_NAMES

logger = logging.getLogger(__name__)

# marketKey = E-<eventId>_<bettingTypeId>_<scopeId>_<col>_<handicap>
_MARKET_KEY_RE = re.compile(r"^E-(\d+)_(\d+)_(\d+)_\d+_(-?[\d.]+)$")


def parse_match_community(raw: dict, match_url: str) -> dict:
    community = raw.get("communityData") or {}
    totals = community.get("total") or {}
    counts = community.get("count") or {}
    groups = community.get("group") or {}

    # Invert group -> marketKey: [per-outcome vote counts]
    per_market_counts: dict[str, list[int]] = {}
    for enc_id, market_key in groups.items():
        votes = counts.get(enc_id)
        if isinstance(votes, int):
            per_market_counts.setdefault(market_key, []).append(votes)

    event_id: str | None = None
    markets: list[dict] = []
    for market_key, total_votes in totals.items():
        m = _MARKET_KEY_RE.match(market_key)
        if m is None:
            logger.warning("Skipping unrecognized community market key: %s", market_key)
            continue
        event_id = event_id or m.group(1)
        betting_type_id = int(m.group(2))
        scope_id = int(m.group(3))
        handicap = m.group(4)
        markets.append(
            {
                "market": BETTING_TYPE_NAMES.get(betting_type_id, f"betting_type_{betting_type_id}"),
                "scope": SCOPE_NAMES.get(scope_id, f"scope_{scope_id}"),
                "handicap": handicap,
                "betting_type_id": betting_type_id,
                "scope_id": scope_id,
                "total_votes": total_votes,
                "outcome_counts": sorted(per_market_counts.get(market_key, []), reverse=True),
            }
        )
    markets.sort(key=lambda x: x["total_votes"], reverse=True)

    start = raw.get("startDate")
    kickoff = datetime.fromtimestamp(start, UTC).isoformat() if isinstance(start, int | float) else None

    return {
        "mode": "match",
        "match_url": match_url,
        "event_id": event_id,
        "home_team": raw.get("home_team"),
        "away_team": raw.get("away_team"),
        "kickoff": kickoff,
        "is_prematch": bool(community) and not raw.get("is_started", False),
        "top_community_pick": raw.get("pick_text"),
        "markets": markets,
    }
