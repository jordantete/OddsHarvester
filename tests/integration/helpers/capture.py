#!/usr/bin/env python3
"""
Script to capture new fixtures from live scraping.

Usage:
    python -m tests.integration.helpers.capture \\
        --sport football \\
        --league premier-league \\
        --match-url "https://www.oddsportal.com/football/england/premier-league/leicester-brentford-xQ77QTN0" \\
        --markets "1x2" \\
        --period "full_time" \\
        --bookies-filter "all"

This will:
1. Run the scraper against the specified match
2. Save the output as a new fixture
3. Generate metadata.json
"""

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse

# Project paths
SCRIPT_DIR = Path(__file__).parent
INTEGRATION_DIR = SCRIPT_DIR.parent
FIXTURES_DIR = INTEGRATION_DIR / "fixtures"
PROJECT_ROOT = INTEGRATION_DIR.parent.parent


def get_version() -> str:
    """Get OddsHarvester version."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        from oddsharvester import __version__

        return __version__
    except ImportError:
        return "unknown"


def extract_match_id_from_url(url: str) -> str:
    """Extract match ID from OddsPortal URL."""
    path = urlparse(url).path.rstrip("/")
    last_segment = path.split("/")[-1]

    # Match ID is the last part after the last hyphen
    parts = last_segment.rsplit("-", 1)
    if len(parts) == 2 and len(parts[1]) >= 6:
        return parts[1]

    return last_segment


def build_fixture_filename(
    markets: list[str],
    period: str,
    bookies_filter: str,
) -> str:
    """Build fixture filename from parameters."""
    markets_str = "_".join(sorted(markets))
    return f"{markets_str}_{period}_{bookies_filter}.json"


def _alias_fragmented_redirect_targets(har_path: Path) -> None:
    """Add aliased entries for fragmented redirect targets so HAR replay can resolve them.

    OddsPortal H2H pages use URL fragments (`#match_id`) to select which match in the
    H2H series to display. Match URLs 301-redirect to `/h2h/<teams>/#match_id`. Playwright's
    `route_from_har` with `not_found="abort"` looks up the fragmented redirect target
    against HAR entries verbatim; since HAR records the bare URL (HTTP fragments never
    reach the wire), the fragmented lookup fails and the navigation aborts. We can't
    simply strip the fragment from the Location header — JS reads `location.hash` to
    pick the right match, so dropping it shows the wrong match.

    The fix: for each Location header with a fragment, duplicate the bare-URL entry as
    an alias at the fragmented URL. The redirect chain now resolves, and the browser's
    `location.hash` is preserved (Playwright sets it from the redirect target), so JS
    renders the intended match.
    """
    har = json.loads(har_path.read_text())
    entries = har.get("log", {}).get("entries", [])
    url_to_entry = {entry["request"]["url"]: entry for entry in entries if "request" in entry}

    fragmented_targets: set[str] = set()
    for entry in entries:
        for header in entry.get("response", {}).get("headers", []):
            if header.get("name", "").lower() == "location":
                value = header.get("value", "")
                if "#" in value:
                    fragmented_targets.add(value)

    new_entries = []
    for fragmented_url in fragmented_targets:
        bare_url = fragmented_url.split("#", 1)[0]
        if bare_url in url_to_entry and fragmented_url not in url_to_entry:
            alias = json.loads(json.dumps(url_to_entry[bare_url]))
            alias["request"]["url"] = fragmented_url
            new_entries.append(alias)

    if new_entries:
        entries.extend(new_entries)
        har_path.write_text(json.dumps(har))


def capture_fixture(
    sport: str,
    league: str,
    match_url: str,
    markets: list[str],
    period: str = "full_time",
    bookies_filter: str = "all",
    output_format: str = "json",
    headless: bool = True,
    timeout: int = 300,
    season: str = "current",
    capture_har: bool = False,
    proxy_url: str | None = None,
) -> Path:
    """
    Capture a new fixture from live scraping.

    Returns the path to the created fixture file.
    """
    match_id = extract_match_id_from_url(match_url)

    # Determine match directory name (use last URL segment)
    url_path = urlparse(match_url).path.rstrip("/")
    match_dir_name = url_path.split("/")[-1]

    # Create output directory
    output_dir = FIXTURES_DIR / sport / league / match_dir_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build command
    markets_str = ",".join(markets)
    fixture_filename = build_fixture_filename(markets, period, bookies_filter)
    output_path = output_dir / fixture_filename

    cmd = [
        "uv",
        "run",
        "oddsharvester",
        "historic",
        "--sport",
        sport,
        "--match-link",
        match_url,
        "--market",
        markets_str,
        "--format",
        output_format,
        "--bookies-filter",
        bookies_filter,
        "--season",
        season,
        "--output",
        str(output_path.with_suffix("")),  # Extension added automatically
    ]

    if period:
        cmd.extend(["--period", period])

    if proxy_url:
        cmd.extend(["--proxy-url", proxy_url])

    if headless:
        cmd.append("--headless")

    har_path = output_path.with_suffix(".har")

    # Run scraper
    print(f"Running scraper for {match_url}...")
    print(f"Command: {' '.join(cmd)}")
    print()

    env = os.environ.copy()
    if capture_har:
        env["ODDSHARVESTER_HAR_RECORD"] = str(har_path)
        print(f"Recording HAR to: {har_path}")

    result = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=timeout, env=env
    )

    if result.returncode != 0:
        print(f"Scraper failed with exit code {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
        raise RuntimeError("Scraper failed")

    print("Scraper succeeded!")
    if result.stdout:
        print(f"Output: {result.stdout.strip()}")

    # Verify output file exists
    if not output_path.exists():
        raise RuntimeError(f"Output file not created: {output_path}")

    if capture_har and not har_path.exists():
        raise RuntimeError(f"HAR file not created: {har_path}")

    if capture_har:
        _alias_fragmented_redirect_targets(har_path)

    # Load scraped data to extract metadata
    with open(output_path) as f:
        scraped_data = json.load(f)

    match_data = scraped_data[0] if isinstance(scraped_data, list) and scraped_data else scraped_data

    # Update or create metadata.json
    metadata_path = output_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
    else:
        metadata = {
            "match_id": match_id,
            "match_url": match_url,
            "sport": sport,
            "league": league,
            "home_team": match_data.get("home_team", ""),
            "away_team": match_data.get("away_team", ""),
            "final_score": {
                "home": match_data.get("home_score", ""),
                "away": match_data.get("away_score", ""),
            },
            "match_date": match_data.get("match_date", ""),
            "notes": "",
        }

    # Update metadata with this fixture
    metadata["captured_at"] = datetime.now(UTC).isoformat()
    metadata["oddsharvester_version"] = get_version()

    if "available_fixtures" not in metadata:
        metadata["available_fixtures"] = []

    if fixture_filename not in metadata["available_fixtures"]:
        metadata["available_fixtures"].append(fixture_filename)
        metadata["available_fixtures"].sort()

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)

    print()
    print(f"Fixture created: {output_path}")
    print(f"Metadata updated: {metadata_path}")

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Capture new fixtures for integration testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Football - basic 1x2 market
  python -m tests.integration.helpers.capture \\
      --sport football \\
      --league premier-league \\
      --match-url "https://www.oddsportal.com/football/england/premier-league/leicester-brentford-xQ77QTN0" \\
      --markets "1x2"

  # Basketball - with period
  python -m tests.integration.helpers.capture \\
      --sport basketball \\
      --league nba \\
      --match-url "https://www.oddsportal.com/basketball/usa/nba/los-angeles-lakers-boston-celtics-0fwUQJEk/" \\
      --markets "home_away" \\
      --period "1st_half"

  # Tennis - multiple markets
  python -m tests.integration.helpers.capture \\
      --sport tennis \\
      --league australian-open \\
      --match-url "https://www.oddsportal.com/tennis/australia/atp-australian-open-2024/..." \\
      --markets "match_winner,over_under_sets_2_5"
        """,
    )

    parser.add_argument("--sport", required=True, help="Sport (e.g., football, basketball, tennis)")
    parser.add_argument(
        "--league", required=True, help="League slug for fixture organization (e.g., premier-league, nba)"
    )
    parser.add_argument("--match-url", required=True, help="Full OddsPortal match URL")
    parser.add_argument("--markets", required=True, help="Comma-separated markets (e.g., 1x2,btts)")
    parser.add_argument("--period", default="full_time", help="Period (default: full_time)")
    parser.add_argument("--bookies-filter", default="all", choices=["all", "classic", "crypto"], help="Bookies filter")
    parser.add_argument("--no-headless", action="store_true", help="Run browser with GUI (for debugging)")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default: 300)")
    parser.add_argument("--season", default="current", help="Season (default: current, e.g., 2024-2025)")
    parser.add_argument(
        "--capture-har",
        action="store_true",
        help="Record a HAR file (snapshot.har) alongside the JSON fixture.",
    )
    parser.add_argument(
        "--proxy-url",
        default=None,
        help="Proxy URL (e.g. http://host:port). Needed to capture geo-gated sports such as cricket.",
    )

    args = parser.parse_args()

    markets = [m.strip() for m in args.markets.split(",")]

    try:
        capture_fixture(
            sport=args.sport,
            league=args.league,
            match_url=args.match_url,
            markets=markets,
            period=args.period,
            bookies_filter=args.bookies_filter,
            headless=not args.no_headless,
            timeout=args.timeout,
            season=args.season,
            capture_har=args.capture_har,
            proxy_url=args.proxy_url,
        )
        print()
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
