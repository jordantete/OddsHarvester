"""
Bulk-capture HARs for every match that already has JSON fixtures.

For each match directory under tests/integration/fixtures/<sport>/<league>/<match-id>/:
  1. Read existing *.json fixture filenames (skip metadata.json).
  2. Parse (markets, period, bookies-filter) from each filename.
  3. Aggregate into a deduplicated list of permutations.
  4. Run capture.py --capture-har with those permutations to populate the same snapshot.har.

Usage:
    uv run python scripts/capture_all_hars.py
    uv run python scripts/capture_all_hars.py --sport football
    uv run python scripts/capture_all_hars.py --match-id leicester-brentford-xQ77QTN0
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "integration" / "fixtures"

from oddsharvester.utils.period_constants import (  # noqa: E402
    AmericanFootballPeriod,
    BaseballPeriod,
    BasketballPeriod,
    FootballPeriod,
    IceHockeyPeriod,
    RugbyLeaguePeriod,
    RugbyUnionPeriod,
    TennisPeriod,
)
from oddsharvester.utils.utils import SPORT_MARKETS_MAPPING  # noqa: E402


def _all_period_values() -> tuple[str, ...]:
    classes = (
        AmericanFootballPeriod,
        BaseballPeriod,
        BasketballPeriod,
        FootballPeriod,
        IceHockeyPeriod,
        RugbyLeaguePeriod,
        RugbyUnionPeriod,
        TennisPeriod,
    )
    seen: set[str] = set()
    for cls in classes:
        for member in cls:
            seen.add(member.value)
    return tuple(sorted(seen, key=lambda s: -len(s)))


def _all_market_values() -> tuple[str, ...]:
    seen: set[str] = set()
    for enum_classes in SPORT_MARKETS_MAPPING.values():
        for enum_class in enum_classes:
            for m in enum_class:
                seen.add(m.value)
    return tuple(sorted(seen, key=lambda s: -len(s)))


_KNOWN_PERIODS: tuple[str, ...] = _all_period_values()
_KNOWN_MARKETS: tuple[str, ...] = _all_market_values()


def parse_fixture_filename(name: str) -> tuple[list[str], str, str] | None:
    """Reverse build_fixture_filename: {markets}_{period}_{bookies}.json -> (markets, period, bookies)."""
    if not name.endswith(".json") or name == "metadata.json":
        return None
    stem = name[:-5]
    parts = stem.split("_")
    if len(parts) < 3:
        return None
    # The bookies filter is always a single token (no underscores) at the end.
    bookies = parts[-1]
    prefix = "_".join(parts[:-1])  # everything before the bookies token

    # Match the period (longest-first).
    matched_period = None
    for period in _KNOWN_PERIODS:
        if prefix.endswith("_" + period) or prefix == period:
            matched_period = period
            break
    if matched_period is None:
        return None

    if prefix == matched_period:
        # No markets — invalid.
        return None
    markets_str = prefix[: -(len(matched_period) + 1)]

    # Greedy-match markets (longest-first), peeling tokens off the start.
    markets: list[str] = []
    remaining = markets_str
    while remaining:
        matched = False
        for m in _KNOWN_MARKETS:
            if remaining == m:
                markets.append(m)
                remaining = ""
                matched = True
                break
            if remaining.startswith(m + "_"):
                markets.append(m)
                remaining = remaining[len(m) + 1 :]
                matched = True
                break
        if not matched:
            # Unknown market token in filename — bail out.
            return None

    if not markets:
        return None
    return markets, matched_period, bookies


def discover_matches(sport_filter: str | None, match_filter: str | None) -> list[Path]:
    matches = []
    if not FIXTURES_DIR.exists():
        return matches
    for sport_dir in sorted(FIXTURES_DIR.iterdir()):
        if not sport_dir.is_dir():
            continue
        if sport_filter and sport_dir.name != sport_filter:
            continue
        for league_dir in sorted(sport_dir.iterdir()):
            if not league_dir.is_dir():
                continue
            for match_dir in sorted(league_dir.iterdir()):
                if not match_dir.is_dir():
                    continue
                if match_filter and match_dir.name != match_filter:
                    continue
                matches.append(match_dir)
    return matches


def capture_match(match_dir: Path) -> bool:
    """Capture HAR + fixtures for a single match. Returns True on success."""
    metadata_path = match_dir / "metadata.json"
    if not metadata_path.exists():
        print(f"  SKIP {match_dir} — no metadata.json")
        return False

    metadata = json.loads(metadata_path.read_text())
    match_url = metadata["match_url"]
    sport = metadata["sport"]
    league = metadata["league"]

    permutations: set[tuple[tuple[str, ...], str, str]] = set()
    for fixture_file in match_dir.glob("*.json"):
        parsed = parse_fixture_filename(fixture_file.name)
        if parsed is None:
            continue
        markets, period, bookies = parsed
        permutations.add((tuple(markets), period, bookies))

    if not permutations:
        print(f"  SKIP {match_dir.name} — no JSON fixtures to derive permutations from")
        return False

    print(f"\n=== {sport}/{league}/{match_dir.name} — {len(permutations)} permutations ===")

    success = True
    for markets, period, bookies in sorted(permutations):
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "tests.integration.helpers.capture",
            "--sport",
            sport,
            "--league",
            league,
            "--match-url",
            match_url,
            "--markets",
            ",".join(markets),
            "--period",
            period,
            "--bookies-filter",
            bookies,
            "--match-dir",
            match_dir.name,
            "--capture-har",
        ]
        print(f"  -> {' '.join(markets)} / {period} / {bookies}")
        result = subprocess.run(cmd, cwd=PROJECT_ROOT)  # noqa: S603
        if result.returncode != 0:
            print("     FAILED")
            success = False

    return success


def main():
    parser = argparse.ArgumentParser(description="Bulk-capture HARs for existing match fixtures.")
    parser.add_argument("--sport", default=None, help="Limit to one sport (e.g., football).")
    parser.add_argument("--match-id", default=None, help="Limit to one match dir name.")
    args = parser.parse_args()

    matches = discover_matches(args.sport, args.match_id)
    if not matches:
        print("No matches found.")
        return 1

    print(f"Found {len(matches)} matches.")
    failures = 0
    for match_dir in matches:
        if not capture_match(match_dir):
            failures += 1

    print(f"\nDone. {len(matches) - failures}/{len(matches)} succeeded.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
