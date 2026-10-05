# Integration Test Fixtures

This directory contains the reference data of the integration tests. Each fixture is a pair: the JSON the CLI
wrote (the golden) and, next to it with the same stem, the `.har` the page was recorded into. The tests replay the
HAR (`ODDSHARVESTER_HAR_REPLAY`), so they run offline, and compare the output with the golden; `--live` skips the
HAR and loads the pages from OddsPortal.

## Structure

```
fixtures/
├── <sport>/<league>/<match-dir>/       one directory per match
│   ├── metadata.json
│   ├── <markets>_<period>_<bookies>.json
│   └── <markets>_<period>_<bookies>.har
├── baseball/mlb/
├── basketball/nba/
├── community/                          top predictions, the BLAPRO profile, two match-vote pages
├── cricket/one-day-international/
├── football/
│   ├── club-friendly/samgurali-spaeri-0nx5GXqB/   live_listing.json and .har, the live-now listing
│   ├── laliga/
│   ├── premier-league/
│   │   ├── historic-listing/                       historic_listing.json and .har, two pages of a season listing
│   │   └── upcoming-listing/                       upcoming_listing.json and .har, a league listing
│   └── super-cup-2025/
├── handball/germany-bundesliga/
├── team/                               teams.json and .har
├── tennis/australian-open/
└── volleyball/italy-superlega/
```

## File Naming Convention

Match fixture files follow this pattern:
```
{markets}_{period}_{bookies_filter}.json
```

with the markets sorted and joined by `_`, then `_odds_history` and `_preview` when the capture used
`--odds-history` or `--preview-only`. The HAR has the same name with `.har`.

Examples:
- `1x2_full_time_all.json`
- `1x2_btts_double_chance_full_time_all.json`
- `home_away_1st_half_all.json`
- `1x2_over_under_2_5_full_time_all_odds_history.json`

## Creating New Fixtures

Capture one match fixture, its golden and its HAR, with the capture helper (it needs the network):

```bash
uv run python -m tests.integration.helpers.capture \
    --sport football \
    --league premier-league \
    --match-url "https://www.oddsportal.com/football/h2h/<away>-<awayId>/<home>-<homeId>/#<eventId>" \
    --markets "1x2" \
    --period "full_time" \
    --bookies-filter "all" \
    --match-dir <home>-<away>-<eventId> \
    --capture-har
```

Run against an existing match directory with the same markets, period and filter, the helper replaces that
fixture's golden and HAR.

Without `--match-dir`, the directory is named after the URL's last path segment. Captures run the browser in
`UTC` unless given `--timezone`, the zone the replays run in.

## Updating Fixtures

`scripts/capture_all_hars.py` recaptures every fixture: match fixtures are derived from each `metadata.json` and
fixture name, and `SPECIAL_FIXTURES` holds the exact command of the others (community, team, the live-now listing,
the upcoming league listing, the historic season listing, odds history, preview).

```bash
# Every fixture
uv run python scripts/capture_all_hars.py

# One kind: matches, community, team, live or listing
uv run python scripts/capture_all_hars.py --only community

# One sport or one match directory (matches only)
uv run python scripts/capture_all_hars.py --sport football
uv run python scripts/capture_all_hars.py --match-id leicester-brentford-xQ77QTN0

# List each HAR and its command, no network
uv run python scripts/capture_all_hars.py --dry-run
```

Recapture on parsing changes, Playwright upgrades, or quarterly.

## metadata.json Format

Each match directory contains a `metadata.json`, written by the capture helper:

```json
{
    "match_id": "KrrdAMyI",
    "match_url": "https://www.oddsportal.com/football/h2h/brentford-xYe7DwID/leicester-KrrdAMyI/#xQ77QTN0",
    "sport": "football",
    "league": "premier-league",
    "home_team": "Leicester",
    "away_team": "Brentford",
    "final_score": {
        "home": "0",
        "away": "4"
    },
    "match_date": "2025-02-21 20:00:00 UTC",
    "notes": "",
    "captured_at": "2026-10-01T08:04:12.448518+00:00",
    "oddsharvester_version": "0.15.0",
    "available_fixtures": [
        "1x2_1st_half_all.json",
        "1x2_full_time_all.json"
    ]
}
```

## Important Notes

- Fixtures are committed to the repository
- Do NOT delete `helpers/capture.py` - it's needed for maintenance
- Historical match data on OddsPortal is immutable (scores, closing odds)
- Some bookmakers may disappear over time (handled as warnings, not errors)
