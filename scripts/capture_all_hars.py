"""
Capture the HAR and golden of every integration fixture from the live site.

Match fixtures (tests/integration/fixtures/<sport>/<league>/<match-id>/) are derived from their
metadata.json and their JSON file names ({markets}_{period}_{bookies}.json), one capture per file,
through tests.integration.helpers.capture. SPECIAL_FIXTURES holds the exact command of every
fixture a file name cannot describe.

Usage:
    uv run python scripts/capture_all_hars.py
    uv run python scripts/capture_all_hars.py --only community
    uv run python scripts/capture_all_hars.py --sport football
    uv run python scripts/capture_all_hars.py --match-id leicester-brentford-xQ77QTN0
    uv run python scripts/capture_all_hars.py --dry-run

--only takes matches, community, team or live. --sport and --match-id select matches only.
--dry-run prints each HAR and its command without running anything.
Exit code: 0 when every selected capture succeeded, 1 otherwise.
"""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "integration" / "fixtures"
KINDS = ("matches", "community", "team", "live")
CAPTURE_MODULE = ("uv", "run", "python", "-m", "tests.integration.helpers.capture")
ODDSHARVESTER = ("uv", "run", "oddsharvester")

from oddsharvester.cli.options import _get_all_periods  # noqa: E402
from oddsharvester.utils.utils import SPORT_MARKETS_MAPPING  # noqa: E402


@dataclass(frozen=True)
class SpecialFixture:
    """A fixture whose capture command cannot be derived from its file name."""

    kind: str
    har: str  # relative to FIXTURES_DIR; the golden is the same path with a .json suffix
    argv: tuple[str, ...]  # capture.py arguments for "matches", oddsharvester arguments otherwise


ODDS_HISTORY_MATCH = "football/premier-league/manchester-city-chelsea-lMp9YMye"

SPECIAL_FIXTURES = (
    SpecialFixture(
        kind="matches",
        har=f"{ODDS_HISTORY_MATCH}/1x2_over_under_2_5_full_time_all_odds_history.har",
        argv=(
            "--sport",
            "football",
            "--league",
            "premier-league",
            "--match-url",
            "https://www.oddsportal.com/football/h2h/chelsea-4fGZN2oK/manchester-city-Wtn9Stg0/#lMp9YMye",
            "--match-dir",
            "manchester-city-chelsea-lMp9YMye",
            "--markets",
            "1x2,over_under_2_5",
            "--period",
            "full_time",
            "--bookies-filter",
            "all",
            "--season",
            "2025-2026",
            "--odds-history",
            "--timezone",
            "Europe/London",
            "--locale",
            "en-GB",
            "--request-delay",
            "2",
            "--concurrency",
            "3",
            "--capture-har",
        ),
    ),
    SpecialFixture(
        kind="community",
        har="community/top_predictions_football.har",
        argv=("community", "-s", "football"),
    ),
    SpecialFixture(
        kind="community",
        har="community/user_profile_blapro.har",
        argv=("community", "--user", "BLAPRO"),
    ),
    SpecialFixture(
        kind="community",
        har="community/match_community_fulham_chelsea.har",
        argv=(
            "community",
            "--match-url",
            "https://www.oddsportal.com/football/h2h/chelsea-4fGZN2oK/fulham-69ZiU2Om/#C2Nfvg77",
        ),
    ),
    # The wrong id in the middle keeps the failure path in the replay.
    SpecialFixture(
        kind="team",
        har="team/teams.har",
        argv=("team", "--team", "lId4TMwf,zzzzzzzz,WGt8En5I"),
    ),
    SpecialFixture(
        kind="live",
        har="football/club-friendly/samgurali-spaeri-0nx5GXqB/live_listing.har",
        argv=("live", "--sport", "football", "--links-only"),
    ),
)


def _all_market_values() -> tuple[str, ...]:
    seen: set[str] = set()
    for enum_classes in SPORT_MARKETS_MAPPING.values():
        for enum_class in enum_classes:
            for m in enum_class:
                seen.add(m.value)
    return tuple(sorted(seen, key=lambda s: -len(s)))


_KNOWN_PERIODS: tuple[str, ...] = tuple(sorted(_get_all_periods(), key=lambda s: -len(s)))
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


def match_captures(match_dir: Path) -> tuple[list[tuple[Path, list[str]]], int]:
    """(HAR, command) per JSON fixture SPECIAL_FIXTURES does not own, and the count of fixtures with no command."""
    owned = {(FIXTURES_DIR / special.har).with_suffix(".json") for special in SPECIAL_FIXTURES}
    fixtures = sorted(p for p in match_dir.glob("*.json") if p.name != "metadata.json" and p not in owned)
    if not fixtures:
        return [], 0
    metadata_path = match_dir / "metadata.json"
    if not metadata_path.exists():
        print(f"  FAILED {match_dir}: no metadata.json")
        return [], len(fixtures)

    metadata = json.loads(metadata_path.read_text())
    permutations: dict[tuple[tuple[str, ...], str, str], Path] = {}
    underivable = 0
    for fixture_file in fixtures:
        parsed = parse_fixture_filename(fixture_file.name)
        if parsed is None:
            print(f"  FAILED {fixture_file}: no command derivable from the name, add it to SPECIAL_FIXTURES")
            underivable += 1
            continue
        markets, period, bookies = parsed
        permutations[(tuple(markets), period, bookies)] = fixture_file.with_suffix(".har")

    captures = []
    for (markets, period, bookies), har in sorted(permutations.items()):
        cmd = [
            *CAPTURE_MODULE,
            "--sport",
            metadata["sport"],
            "--league",
            metadata["league"],
            "--match-url",
            metadata["match_url"],
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
        captures.append((har, cmd))
    return captures, underivable


def special_command(special: SpecialFixture, staging: Path) -> tuple[list[str], dict[str, str]]:
    """The command and extra environment of a special capture; a CLI capture writes into staging."""
    if special.kind == "matches":
        return [*CAPTURE_MODULE, *special.argv], {}
    har = Path(special.har)
    output = staging / har.with_suffix(".json").name
    env = {"ODDSHARVESTER_HAR_RECORD": str(staging / har.name)}
    return [*ODDSHARVESTER, *special.argv, "--headless", "-o", str(output)], env


def capture_special(special: SpecialFixture) -> bool:
    """Run one special capture; a CLI capture replaces the committed files only when it wrote both."""
    print(f"\n=== {special.kind}: {special.har} ===")
    har = FIXTURES_DIR / special.har
    golden = har.with_suffix(".json")
    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp)
        cmd, env = special_command(special, staging)
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, env={**os.environ, **env})  # noqa: S603
        if special.kind == "matches":
            return result.returncode == 0
        staged_har, staged_golden = staging / har.name, staging / golden.name
        if result.returncode != 0 or not staged_har.exists() or not _has_records(staged_golden):
            print(f"     exit {result.returncode}, nothing replaced: {special.har} and its golden are unchanged")
            return False
        shutil.move(staged_har, har)
        shutil.move(staged_golden, golden)
    return True


def _has_records(path: Path) -> bool:
    if not path.exists():
        return False
    data = json.loads(path.read_text())
    return isinstance(data, list) and bool(data)


def _special_selected(special: SpecialFixture, only: str | None, sport: str | None, match_id: str | None) -> bool:
    if only and special.kind != only:
        return False
    if special.kind != "matches":
        return not sport and not match_id
    sport_name, _league, match_name, _file = special.har.split("/")
    return (not sport or sport == sport_name) and (not match_id or match_id == match_name)


def _command_line(what: list[str] | SpecialFixture) -> str:
    if not isinstance(what, SpecialFixture):
        return shlex.join(what)
    cmd, env = special_command(what, Path("<tmp>"))
    return " ".join([*(f"{key}={shlex.quote(value)}" for key, value in env.items()), shlex.join(cmd)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture the HARs and goldens of the integration fixtures.")
    parser.add_argument("--only", choices=KINDS, default=None, help="Capture one kind of fixture.")
    parser.add_argument("--sport", default=None, help="Limit the matches to one sport (e.g., football).")
    parser.add_argument("--match-id", default=None, help="Limit the matches to one match dir name.")
    parser.add_argument("--dry-run", action="store_true", help="List each HAR and its command; run nothing.")
    args = parser.parse_args(argv)

    units: list[tuple[str, Path, list[str] | SpecialFixture]] = []
    failures = 0
    if args.only in (None, "matches"):
        for match_dir in discover_matches(args.sport, args.match_id):
            captures, underivable = match_captures(match_dir)
            failures += underivable
            units += [("matches", har, cmd) for har, cmd in captures]
    units += [
        (special.kind, FIXTURES_DIR / special.har, special)
        for special in SPECIAL_FIXTURES
        if _special_selected(special, args.only, args.sport, args.match_id)
    ]

    if not units:
        print("Nothing to capture.")
        return 1

    if args.dry_run:
        for kind, har, what in units:
            print(f"{kind:<10}{har.relative_to(PROJECT_ROOT)}")
            print(f"{'':<10}{_command_line(what)}")
        print(f"\nHAR files: {len(units)}")
        return 1 if failures else 0

    for kind, har, what in units:
        if isinstance(what, SpecialFixture):
            ok = capture_special(what)
        else:
            print(f"\n=== {kind}: {har.relative_to(FIXTURES_DIR)} ===")
            ok = subprocess.run(what, cwd=PROJECT_ROOT).returncode == 0  # noqa: S603
        if not ok:
            print("     FAILED")
            failures += 1

    print(f"\nDone. {len(units) - failures}/{len(units)} succeeded.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
