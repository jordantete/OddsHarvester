# Volleyball Support — Design Spec

**Date:** 2026-05-18
**Status:** Approved (design), pending implementation plan
**Branch:** `feat/volleyball-support`

## Goal

Add volleyball as a supported sport, following the integration checklist established
by the recent handball integration, but modelling the market registry and enums on
the existing **Tennis** implementation (structurally near-identical to volleyball).
No regression to existing sports; additive changes only.

## OddsPortal Live Exploration (verified 2026-05-18)

Source: `oddsportal.com/volleyball/`, Italian SuperLega 2024/2025 finished matches.

- **Sport slug:** `volleyball`; base `https://www.oddsportal.com/volleyball/`
- **Match URL pattern:** H2H fragmented — `/volleyball/h2h/teamA-<id>/teamB-<id>/#<hash>`.
  Same family as basketball NBA / real-madrid-barcelona fixtures that CLAUDE.md
  documents as a HAR-replay limitation (fragment + runtime cache-buster).
- **Market tabs:** `Home/Away`, `Over/Under`, `Asian Handicap`, `Correct Score`.
  No `1X2` / `DNB` / `Double Chance` — volleyball has no draws.
- **Period selector:** `Full Time`, `1st Set`, `2nd Set`, `3rd Set`, `4th Set`, `5th Set`.
  Correct Score is `Full Time` only.
- **Over/Under has two axes:**
  - `Over/Under +{N}.5 Sets` (observed +3.5, +4.5)
  - `Over/Under +{N}.5 Points` (observed +184.5, +185.5)
- **Asian Handicap has two axes:**
  - `Asian Handicap {±N}.5 Sets` (observed -2.5, +2.5)
  - `Asian Handicap {±N}.5 Points` (observed +2.5 … +7.5)
- **Correct Score outcomes:** `3:0, 3:1, 3:2, 0:3, 1:3, 2:3` (best-of-5).

The finished off-season matches inspected exposed only a partial O/U/AH band, so the
exact numeric band must be reconciled against a live, fully-populated match during
the capture/verify pass (mirrors handball reconcile commit `70dbd17`).

## Precedent: Tennis, not Handball

Tennis already implements every structural element volleyball needs — Home/Away
winner, O/U Sets + O/U (Games), AH Sets + AH (Games), Correct Score, set-based
periods — in `register_tennis_markets()` and the `Tennis*Market` enums. Volleyball
maps onto this with `Points` substituted for `Games` and 5 sets instead of 2.

The **handball commits** define *which files to touch and in what order*; the
**tennis code** defines *the registry/enum shape*.

## Changes

### 1. `src/oddsharvester/utils/sport_market_constants.py`
- Add `VOLLEYBALL = "volleyball"` to `Sport`.
- New enums:
  - `VolleyballMarket`: `HOME_AWAY = "home_away"`
  - `VolleyballOverUnderSetsMarket`: `over_under_sets_2_5`, `_3_5`, `_4_5`
  - `VolleyballOverUnderPointsMarket`: `over_under_points_{N}_5`, band **150.5–230.5**
    (final band confirmed during live verify)
  - `VolleyballAsianHandicapSetsMarket`: `asian_handicap_-2_5_sets` … `+2_5_sets`
  - `VolleyballAsianHandicapPointsMarket`: `asian_handicap_{±N}_5_points`,
    band **±1.5–±9.5** (final band confirmed during live verify)
  - `VolleyballCorrectScoreMarket`: `correct_score_3_0, _3_1, _3_2, _0_3, _1_3, _2_3`

### 2. `src/oddsharvester/utils/utils.py`
- Import the six volleyball enums.
- `SPORT_MARKETS_MAPPING[Sport.VOLLEYBALL] = [VolleyballMarket,
  VolleyballOverUnderSetsMarket, VolleyballOverUnderPointsMarket,
  VolleyballAsianHandicapSetsMarket, VolleyballAsianHandicapPointsMarket,
  VolleyballCorrectScoreMarket]`

### 3. `src/oddsharvester/utils/period_constants.py`
- `VolleyballPeriod`: `FULL_TIME, FIRST_SET, SECOND_SET, THIRD_SET, FOURTH_SET, FIFTH_SET`
  - display: `"Full Time"`, `"1st Set"` … `"5th Set"`
  - internal: `"FullTime"`, `"FirstSet"` … `"FifthSet"`

### 4. `src/oddsharvester/core/sport_period_registry.py`
- `SportPeriodRegistry.register(sport=Sport.VOLLEYBALL, period_enum=VolleyballPeriod,
  default_period=VolleyballPeriod.FULL_TIME)`

### 5. `src/oddsharvester/core/sport_market_registry.py`
- Import the six volleyball enums.
- `register_volleyball_markets()` modelled on `register_tennis_markets()`:
  - Home/Away → `create_market_lambda("Home/Away", odds_labels=["1", "2"])`
  - O/U Sets → `specific_market=f"Over/Under +{n} Sets"`, `odds_labels=["odds_over","odds_under"]`
  - O/U Points → `specific_market=f"Over/Under +{n} Points"`, same odds labels
  - AH Sets → `main_market="Asian Handicap"`, `f"Asian Handicap {n} Sets"`,
    `odds_labels=["sets_handicap_team_1","sets_handicap_team_2"]`
  - AH Points → `f"Asian Handicap {n} Points"`,
    `odds_labels=["points_handicap_team_1","points_handicap_team_2"]`
  - Correct Score → `main_market="Correct Score"`,
    `specific_market` = numeric `_`→`:` (e.g. `"3:0"`), `odds_labels=["correct_score"]`
- Append `cls.register_volleyball_markets()` to `register_all_markets()`.

### 6. `src/oddsharvester/utils/sport_league_constants.py`
- `Sport.VOLLEYBALL` dict with 10 verified slugs:
  - `italy-superlega` → `…/volleyball/italy/superlega/`
  - `poland-plusliga` → `…/volleyball/poland/plusliga/`
  - `russia-superliga` → `…/volleyball/russia/superliga/`
  - `france-ligue-a` → `…/volleyball/france/ligue-a/`
  - `germany-1-bundesliga` → `…/volleyball/germany/1-bundesliga/`
  - `turkey-efeler-ligi` → `…/volleyball/turkey/efeler-ligi/`
  - `brazil-superliga` → `…/volleyball/brazil/superliga/`
  - `japan-sv-league` → `…/volleyball/japan/sv-league/`
  - `cev-champions-league` → `…/volleyball/europe/liga-de-campeones/`
  - `nations-league` → `…/volleyball/world/nations-league/`
- `url_builder.py` handles registered sports generically (confirmed by handball
  commit `d78da7d`); no change expected. League slugs validated via
  `scripts/validate_league.py` during implementation.

### 7. Tests (mirror handball commits)
- `tests/utils/test_sport_market_constants.py` — volleyball enum members
- `tests/utils/test_period_constants.py` — `VolleyballPeriod` values/labels/internal
- `tests/utils/test_period_registry.py` — auto-registration + internal-value conversion
- `tests/core/test_sport_market_registry.py` — `register_volleyball_markets` +
  `register_all_markets` mock assertion + integration assertion
- `tests/utils/test_sport_league_constants.py` — volleyball league mapping guard
- `tests/utils/test_utils.py` — `get_supported_markets("volleyball")`
- `tests/core/test_url_builder.py` — volleyball league URL param + invalid-sport
  literal updated if needed
- `tests/integration/test_volleyball.py` — mirrors `test_handball.py`, but marked
  `@pytest.mark.live_only` (H2H fragmented URL → HAR replay cannot reproduce, per
  CLAUDE.md). JSON fixture + best-effort HAR captured via
  `tests.integration.helpers.capture`.

### 8. Docs
- `README` — supported sports line: 8 → 9 sports, add volleyball.
- `CLAUDE.md` — sport count in Project Overview.
- `docs/agentic-gotchas.md` — append §8: volleyball Sets-vs-Points dual-axis
  `specific_market` suffixes and the H2H-fragment `live_only` consequence
  (verified live, May 2026).

## Regression Safety

All changes are additive: new enum members, a new registry method, a new league
dict key. The only shared-code touches are one appended line in
`register_all_markets()` and one new `SPORT_MARKETS_MAPPING` key — both following
the handball precedent verbatim. Gate: `uv run pytest tests/ -q
--ignore=tests/integration/` stays green; `uv run ruff check`/`format` clean.

## Deferred to Implementation

- Confirm exact O/U Points and AH Points numeric bands against a live
  fully-populated match (capture/verify pass, mirrors handball `70dbd17`).
- Confirm AH/O/U Sets band (best-of-5 implies sets total 2.5/3.5/4.5 and
  set handicap ±1.5/±2.5).
- Capture integration fixture + HAR; confirm `live_only` marker behaviour.

## Out of Scope

- Women's leagues (men's top-10 only this iteration).
- Any shared "set-sport" abstraction across tennis/volleyball (no refactor of
  working tennis code).
