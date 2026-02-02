# Integration Test Fixtures

This directory contains reference data (fixtures) for integration tests.

## Structure

```
fixtures/
├── football/
│   ├── premier-league/
│   │   └── {match-slug}/
│   │       ├── metadata.json
│   │       └── {markets}_{period}_{bookies}.json
│   └── super-cup-2025/
│       └── ...
├── basketball/
│   └── nba/
│       └── ...
└── tennis/
    └── australian-open/
        └── ...
```

## File Naming Convention

Fixture files follow this pattern:
```
{markets}_{period}_{bookies_filter}.json
```

Examples:
- `1x2_full_time_all.json`
- `1x2_btts_double_chance_full_time_all.json`
- `home_away_1st_half_all.json`
- `match_winner_1st_set_classic.json`

## Creating New Fixtures

Use the capture script:

```bash
python -m tests.integration.helpers.capture \
    --sport football \
    --league premier-league \
    --match-url "https://www.oddsportal.com/..." \
    --markets "1x2,btts" \
    --period "full_time" \
    --bookies-filter "all"
```

## metadata.json Format

Each match directory contains a `metadata.json` with:

```json
{
    "match_id": "xQ77QTN0",
    "match_url": "https://...",
    "sport": "football",
    "league": "premier-league",
    "home_team": "Leicester",
    "away_team": "Brentford",
    "final_score": {"home": "0", "away": "4"},
    "match_date": "26 Jan 2025, 15:00",
    "captured_at": "2026-02-02T10:30:00Z",
    "oddsharvester_version": "0.1.0",
    "available_fixtures": [
        "1x2_full_time_all.json",
        "1x2_1st_half_all.json"
    ],
    "notes": ""
}
```

## Updating Fixtures

If OddsHarvester's output format changes, re-run the capture script for affected fixtures:

```bash
# Re-capture all fixtures for a match
python -m tests.integration.helpers.capture \
    --sport football \
    --league premier-league \
    --match-url "https://www.oddsportal.com/football/england/premier-league/leicester-brentford-xQ77QTN0" \
    --markets "1x2"
```

## Important Notes

- Fixtures are committed to the repository
- Do NOT delete `helpers/capture.py` - it's needed for maintenance
- Historical match data on OddsPortal is immutable (scores, closing odds)
- Some bookmakers may disappear over time (handled as warnings, not errors)
