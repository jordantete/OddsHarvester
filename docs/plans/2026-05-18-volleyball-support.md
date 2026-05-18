# Volleyball Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add volleyball as a fully supported sport (markets, periods, leagues, tests, docs) without regressing existing sports.

**Architecture:** Additive only. New `VOLLEYBALL` Sport enum member, six new market enums, a `VolleyballPeriod` enum, a `register_volleyball_markets()` registry method, and a 10-league URL mapping. The market registry is modelled line-for-line on the existing, tested `register_tennis_markets()` (volleyball is structurally near-identical to tennis: Home/Away winner, O/U Sets + O/U Points, AH Sets + AH Points, Correct Score, set-based periods). The file checklist mirrors the recent handball integration.

**Tech Stack:** Python 3.12, `uv`, pytest, Ruff. Spec: `docs/specs/2026-05-18-volleyball-support-design.md`.

**Branch:** `feat/volleyball-support` (already created).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/oddsharvester/utils/sport_market_constants.py` | `Sport.VOLLEYBALL` + 6 volleyball market enums | Modify |
| `src/oddsharvester/utils/utils.py` | `SPORT_MARKETS_MAPPING` entry | Modify |
| `src/oddsharvester/utils/period_constants.py` | `VolleyballPeriod` enum | Modify |
| `src/oddsharvester/core/sport_period_registry.py` | Register `VolleyballPeriod` | Modify |
| `src/oddsharvester/core/sport_market_registry.py` | `register_volleyball_markets()` + wire into `register_all_markets` | Modify |
| `src/oddsharvester/utils/sport_league_constants.py` | `Sport.VOLLEYBALL` league dict | Modify |
| `tests/utils/test_sport_market_constants.py` | Volleyball enum guard | Modify |
| `tests/utils/test_period_constants.py` | `VolleyballPeriod` guard | Modify |
| `tests/utils/test_period_registry.py` | Volleyball period registration guard | Modify |
| `tests/core/test_sport_market_registry.py` | `register_volleyball_markets` guard | Modify |
| `tests/utils/test_sport_league_constants.py` | Volleyball league mapping guard | Modify |
| `tests/utils/test_utils.py` | `get_supported_markets("volleyball")` guard | Modify |
| `tests/core/test_url_builder.py` | Volleyball league URL param | Modify |
| `tests/integration/test_volleyball.py` | Live-only integration regression | Create |
| `README.md` | Supported sports table row | Modify |
| `CLAUDE.md` | Sport list in Project Overview | Modify |
| `docs/agentic-gotchas.md` | §8 volleyball Sets/Points dual-axis gotcha | Modify |

---

## Task 1: Sport enum + volleyball market constants

**Files:**
- Modify: `src/oddsharvester/utils/sport_market_constants.py`
- Test: `tests/utils/test_sport_market_constants.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/utils/test_sport_market_constants.py`. First add these names to the existing import block from `oddsharvester.utils.sport_market_constants`:
`VolleyballMarket, VolleyballOverUnderSetsMarket, VolleyballOverUnderPointsMarket, VolleyballAsianHandicapSetsMarket, VolleyballAsianHandicapPointsMarket, VolleyballCorrectScoreMarket`.

Then add this test method inside the `TestSportEnums` class:

```python
    def test_volleyball_market_enums(self):
        """Verify volleyball markets (Home/Away, O/U Sets+Points, AH Sets+Points, Correct Score)."""
        assert Sport.VOLLEYBALL.value == "volleyball"

        market_values = [m.value for m in VolleyballMarket]
        ou_sets = [m.value for m in VolleyballOverUnderSetsMarket]
        ou_points = [m.value for m in VolleyballOverUnderPointsMarket]
        ah_sets = [m.value for m in VolleyballAsianHandicapSetsMarket]
        ah_points = [m.value for m in VolleyballAsianHandicapPointsMarket]
        cs = [m.value for m in VolleyballCorrectScoreMarket]

        assert "home_away" in market_values
        assert "over_under_sets_3_5" in ou_sets
        assert "over_under_sets_4_5" in ou_sets
        assert "over_under_points_184_5" in ou_points
        assert "asian_handicap_-2_5_sets" in ah_sets
        assert "asian_handicap_+2_5_sets" in ah_sets
        assert "asian_handicap_+2_5_points" in ah_points
        assert "asian_handicap_-9_5_points" in ah_points
        assert set(cs) == {
            "correct_score_3_0",
            "correct_score_3_1",
            "correct_score_3_2",
            "correct_score_0_3",
            "correct_score_1_3",
            "correct_score_2_3",
        }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_sport_market_constants.py::TestSportEnums::test_volleyball_market_enums -q`
Expected: FAIL with `ImportError: cannot import name 'VolleyballMarket'`

- [ ] **Step 3: Add `VOLLEYBALL` to the `Sport` enum**

In `src/oddsharvester/utils/sport_market_constants.py`, in `class Sport(Enum)`, add after `HANDBALL = "handball"`:

```python
    VOLLEYBALL = "volleyball"
```

- [ ] **Step 4: Append the six volleyball market enums at end of file**

Append to the end of `src/oddsharvester/utils/sport_market_constants.py`:

```python


class VolleyballMarket(Enum):
    """Volleyball-specific markets (no draw outcome)."""

    HOME_AWAY = "home_away"


class VolleyballOverUnderSetsMarket(Enum):
    """Over/Under total sets betting markets for volleyball (best-of-5)."""

    OVER_UNDER_2_5 = "over_under_sets_2_5"
    OVER_UNDER_3_5 = "over_under_sets_3_5"
    OVER_UNDER_4_5 = "over_under_sets_4_5"


class VolleyballOverUnderPointsMarket(Enum):
    """Over/Under total points betting markets for volleyball."""

    pass


class VolleyballAsianHandicapSetsMarket(Enum):
    """Asian Handicap (sets) betting markets for volleyball."""

    HANDICAP_MINUS_2_5 = "asian_handicap_-2_5_sets"
    HANDICAP_MINUS_1_5 = "asian_handicap_-1_5_sets"
    HANDICAP_PLUS_1_5 = "asian_handicap_+1_5_sets"
    HANDICAP_PLUS_2_5 = "asian_handicap_+2_5_sets"


class VolleyballAsianHandicapPointsMarket(Enum):
    """Asian Handicap (points) betting markets for volleyball."""

    pass


class VolleyballCorrectScoreMarket(Enum):
    """Correct Score (set score) markets for volleyball (best-of-5)."""

    CORRECT_SCORE_3_0 = "correct_score_3_0"
    CORRECT_SCORE_3_1 = "correct_score_3_1"
    CORRECT_SCORE_3_2 = "correct_score_3_2"
    CORRECT_SCORE_0_3 = "correct_score_0_3"
    CORRECT_SCORE_1_3 = "correct_score_1_3"
    CORRECT_SCORE_2_3 = "correct_score_2_3"
```

- [ ] **Step 5: Generate the Points-band members programmatically**

The `VolleyballOverUnderPointsMarket` and `VolleyballAsianHandicapPointsMarket` bodies must replace the `pass` placeholder with explicit members (enums cannot use loops). Generate them with this throwaway command, then paste the output into the two classes (replacing each `pass`):

Run:
```bash
python3 - <<'EOF'
print("# --- VolleyballOverUnderPointsMarket members ---")
for x in range(1505, 2310, 10):
    n = x / 10
    name = "OVER_UNDER_%d_5" % int(n)
    print('    %s = "over_under_points_%d_5"' % (name, int(n)))
print()
print("# --- VolleyballAsianHandicapPointsMarket members ---")
for half in range(15, 100, 10):
    n = half / 10
    pos = "%.1f" % n
    print('    HANDICAP_PLUS_%d_5 = "asian_handicap_+%s_points"' % (int(n), pos))
for half in range(15, 100, 10):
    n = half / 10
    pos = "%.1f" % n
    print('    HANDICAP_MINUS_%d_5 = "asian_handicap_-%s_points"' % (int(n), pos))
EOF
```

Expected: O/U Points members from `OVER_UNDER_150_5 = "over_under_points_150_5"` through `OVER_UNDER_230_5 = "over_under_points_230_5"`; AH Points members `asian_handicap_+1_5_points` … `asian_handicap_+9_5_points` then the matching `-` members. Paste each block in place of the corresponding `pass`. (Exact band reconciled against live odds in Task 7.)

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_sport_market_constants.py::TestSportEnums::test_volleyball_market_enums -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/oddsharvester/utils/sport_market_constants.py tests/utils/test_sport_market_constants.py
git commit -m "feat: add volleyball sport enum and market constants"
```

---

## Task 2: SPORT_MARKETS_MAPPING entry

**Files:**
- Modify: `src/oddsharvester/utils/utils.py`
- Test: `tests/utils/test_utils.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/utils/test_utils.py`:

```python
def test_get_supported_markets_volleyball():
    """Volleyball returns its full market union (Home/Away, O/U+AH Sets/Points, Correct Score)."""
    markets = get_supported_markets("volleyball")
    assert "home_away" in markets
    assert "over_under_sets_3_5" in markets
    assert "over_under_points_184_5" in markets
    assert "asian_handicap_+2_5_sets" in markets
    assert "asian_handicap_+2_5_points" in markets
    assert "correct_score_3_0" in markets
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_utils.py::test_get_supported_markets_volleyball -q`
Expected: FAIL (volleyball not in `SPORT_MARKETS_MAPPING`)

- [ ] **Step 3: Add imports and mapping entry**

In `src/oddsharvester/utils/utils.py`, add to the import block from `oddsharvester.utils.sport_market_constants` (keep alphabetical grouping consistent with the file):

```python
    VolleyballAsianHandicapPointsMarket,
    VolleyballAsianHandicapSetsMarket,
    VolleyballCorrectScoreMarket,
    VolleyballMarket,
    VolleyballOverUnderPointsMarket,
    VolleyballOverUnderSetsMarket,
```

Then add to `SPORT_MARKETS_MAPPING`, after the `Sport.HANDBALL: [...]` line:

```python
    Sport.VOLLEYBALL: [
        VolleyballMarket,
        VolleyballOverUnderSetsMarket,
        VolleyballOverUnderPointsMarket,
        VolleyballAsianHandicapSetsMarket,
        VolleyballAsianHandicapPointsMarket,
        VolleyballCorrectScoreMarket,
    ],
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_utils.py::test_get_supported_markets_volleyball -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/utils/utils.py tests/utils/test_utils.py
git commit -m "feat: map volleyball markets in SPORT_MARKETS_MAPPING"
```

---

## Task 3: VolleyballPeriod + period registry

**Files:**
- Modify: `src/oddsharvester/utils/period_constants.py`
- Modify: `src/oddsharvester/core/sport_period_registry.py`
- Test: `tests/utils/test_period_constants.py`, `tests/utils/test_period_registry.py`

- [ ] **Step 1: Write the failing tests**

Add to the import block of `tests/utils/test_period_constants.py` the name `VolleyballPeriod`, then append:

```python
class TestVolleyballPeriod:
    """Tests for the VolleyballPeriod enum."""

    def test_enum_values(self):
        assert VolleyballPeriod.FULL_TIME.value == "full_time"
        assert VolleyballPeriod.FIRST_SET.value == "1st_set"
        assert VolleyballPeriod.FIFTH_SET.value == "5th_set"

    def test_get_display_label(self):
        assert VolleyballPeriod.get_display_label(VolleyballPeriod.FULL_TIME) == "Full Time"
        assert VolleyballPeriod.get_display_label(VolleyballPeriod.FIRST_SET) == "1st Set"
        assert VolleyballPeriod.get_display_label(VolleyballPeriod.FIFTH_SET) == "5th Set"

    def test_get_internal_value(self):
        assert VolleyballPeriod.get_internal_value(VolleyballPeriod.FULL_TIME) == "FullTime"
        assert VolleyballPeriod.get_internal_value(VolleyballPeriod.FIRST_SET) == "FirstSet"
        assert VolleyballPeriod.get_internal_value(VolleyballPeriod.FIFTH_SET) == "FifthSet"
```

Add `VolleyballPeriod` to the import block of `tests/utils/test_period_registry.py`, then append inside `TestSportPeriodRegistry`:

```python
    def test_volleyball_is_registered(self):
        """Test that volleyball is auto-registered."""
        assert SportPeriodRegistry.is_sport_registered("volleyball")
        assert SportPeriodRegistry.get_period_enum("volleyball") == VolleyballPeriod
        assert SportPeriodRegistry.get_default_period("volleyball") == VolleyballPeriod.FULL_TIME
```

and append inside `TestSportPeriodRegistryConversion`:

```python
    def test_from_internal_value_volleyball(self):
        """Test converting internal values to volleyball enum."""
        assert SportPeriodRegistry.from_internal_value("FullTime", "volleyball") == VolleyballPeriod.FULL_TIME
        assert SportPeriodRegistry.from_internal_value("FirstSet", "volleyball") == VolleyballPeriod.FIRST_SET
        assert SportPeriodRegistry.from_internal_value("FifthSet", "volleyball") == VolleyballPeriod.FIFTH_SET
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/utils/test_period_constants.py::TestVolleyballPeriod tests/utils/test_period_registry.py::TestSportPeriodRegistry::test_volleyball_is_registered -q`
Expected: FAIL with `ImportError: cannot import name 'VolleyballPeriod'`

- [ ] **Step 3: Add `VolleyballPeriod` enum**

Append to `src/oddsharvester/utils/period_constants.py`:

```python


class VolleyballPeriod(Enum):
    """Periods available for volleyball matches (best-of-5 sets)."""

    FULL_TIME = "full_time"
    FIRST_SET = "1st_set"
    SECOND_SET = "2nd_set"
    THIRD_SET = "3rd_set"
    FOURTH_SET = "4th_set"
    FIFTH_SET = "5th_set"

    @classmethod
    def get_display_label(cls, period: "VolleyballPeriod") -> str:
        """Get the display label for OddsPortal UI."""
        labels = {
            cls.FULL_TIME: "Full Time",
            cls.FIRST_SET: "1st Set",
            cls.SECOND_SET: "2nd Set",
            cls.THIRD_SET: "3rd Set",
            cls.FOURTH_SET: "4th Set",
            cls.FIFTH_SET: "5th Set",
        }
        return labels[period]

    @classmethod
    def get_internal_value(cls, period: "VolleyballPeriod") -> str:
        """Get the internal value used in scraper functions."""
        internal_values = {
            cls.FULL_TIME: "FullTime",
            cls.FIRST_SET: "FirstSet",
            cls.SECOND_SET: "SecondSet",
            cls.THIRD_SET: "ThirdSet",
            cls.FOURTH_SET: "FourthSet",
            cls.FIFTH_SET: "FifthSet",
        }
        return internal_values[period]
```

- [ ] **Step 4: Register volleyball in the period registry**

In `src/oddsharvester/core/sport_period_registry.py`, add `VolleyballPeriod` to the import block from `oddsharvester.utils.period_constants` (keep alphabetical), then append at the end of the file (after the handball registration line):

```python
SportPeriodRegistry.register(
    sport=Sport.VOLLEYBALL, period_enum=VolleyballPeriod, default_period=VolleyballPeriod.FULL_TIME
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/utils/test_period_constants.py::TestVolleyballPeriod tests/utils/test_period_registry.py -q`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add src/oddsharvester/utils/period_constants.py src/oddsharvester/core/sport_period_registry.py tests/utils/test_period_constants.py tests/utils/test_period_registry.py
git commit -m "feat: add volleyball periods (full time + 5 sets)"
```

---

## Task 4: register_volleyball_markets()

**Files:**
- Modify: `src/oddsharvester/core/sport_market_registry.py`
- Test: `tests/core/test_sport_market_registry.py`

- [ ] **Step 1: Write the failing test**

In `tests/core/test_sport_market_registry.py`, add this method inside `TestSportMarketRegistrar` (next to `test_register_handball_markets`):

```python
    def test_register_volleyball_markets(self):
        """Test registering markets for volleyball (Home/Away, O/U+AH Sets/Points, Correct Score)."""
        SportMarketRegistrar.register_volleyball_markets()

        m = SportMarketRegistry.get_market_mapping(Sport.VOLLEYBALL.value)

        assert "home_away" in m
        assert "over_under_sets_3_5" in m
        assert "over_under_points_184_5" in m
        assert "asian_handicap_+2_5_sets" in m
        assert "asian_handicap_+2_5_points" in m
        assert "correct_score_3_0" in m
```

In the same file, find `test_register_all_markets`. It nests `with patch.object(...)` calls and ends with `SportMarketRegistrar.register_all_markets()` then `mock_*.assert_called_once()` lines. Add one more nested patch for handball's sibling — wrap the existing innermost `SportMarketRegistrar.register_all_markets()` call with:

```python
                                            with patch.object(
                                                SportMarketRegistrar, "register_volleyball_markets"
                                            ) as mock_volleyball:
                                                SportMarketRegistrar.register_all_markets()
```

(Add one indent level to the `register_all_markets()` call already there; do NOT remove the existing `mock_handball` wrapper.) Then add after the `mock_handball.assert_called_once()` line:

```python
        mock_volleyball.assert_called_once()
```

And in `test_register_all_markets_integration`, after the existing handball assertion, add:

```python
        assert "home_away" in SportMarketRegistry.get_market_mapping(Sport.VOLLEYBALL.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_sport_market_registry.py::TestSportMarketRegistrar::test_register_volleyball_markets -q`
Expected: FAIL with `AttributeError: ... has no attribute 'register_volleyball_markets'`

- [ ] **Step 3: Add imports**

In `src/oddsharvester/core/sport_market_registry.py`, add to the import block from `oddsharvester.utils.sport_market_constants` (keep alphabetical):

```python
    VolleyballAsianHandicapPointsMarket,
    VolleyballAsianHandicapSetsMarket,
    VolleyballCorrectScoreMarket,
    VolleyballMarket,
    VolleyballOverUnderPointsMarket,
    VolleyballOverUnderSetsMarket,
```

- [ ] **Step 4: Add `register_volleyball_markets` classmethod**

In `src/oddsharvester/core/sport_market_registry.py`, add this classmethod immediately before `register_all_markets` (mirrors `register_tennis_markets`):

```python
    @classmethod
    def register_volleyball_markets(cls):
        """Registers all volleyball betting markets.

        Modelled on register_tennis_markets: Home/Away winner, Over/Under and
        Asian Handicap each on a Sets axis and a Points axis, plus Correct Score.
        OddsPortal labels the handicap tab "Asian Handicap" and suffixes the
        submarket with " Sets" / " Points" (verified live, May 2026).
        """
        SportMarketRegistry.register(
            Sport.VOLLEYBALL,
            {
                "home_away": cls.create_market_lambda("Home/Away", odds_labels=["1", "2"]),
            },
        )

        # Over/Under Sets
        for over_under in VolleyballOverUnderSetsMarket:
            numeric_part = over_under.value.replace("over_under_sets_", "").replace("_", ".")
            SportMarketRegistry.register(
                Sport.VOLLEYBALL,
                {
                    over_under.value: cls.create_market_lambda(
                        main_market="Over/Under",
                        specific_market=f"Over/Under +{numeric_part} Sets",
                        odds_labels=["odds_over", "odds_under"],
                    )
                },
            )

        # Over/Under Points
        for over_under in VolleyballOverUnderPointsMarket:
            numeric_part = over_under.value.replace("over_under_points_", "").replace("_", ".")
            SportMarketRegistry.register(
                Sport.VOLLEYBALL,
                {
                    over_under.value: cls.create_market_lambda(
                        main_market="Over/Under",
                        specific_market=f"Over/Under +{numeric_part} Points",
                        odds_labels=["odds_over", "odds_under"],
                    )
                },
            )

        # Asian Handicap Sets
        for handicap in VolleyballAsianHandicapSetsMarket:
            numeric_part = handicap.value.replace("asian_handicap_", "").replace("_sets", "").replace("_", ".")
            SportMarketRegistry.register(
                Sport.VOLLEYBALL,
                {
                    handicap.value: cls.create_market_lambda(
                        main_market="Asian Handicap",
                        specific_market=f"Asian Handicap {numeric_part} Sets",
                        odds_labels=["sets_handicap_team_1", "sets_handicap_team_2"],
                    )
                },
            )

        # Asian Handicap Points
        for handicap in VolleyballAsianHandicapPointsMarket:
            numeric_part = handicap.value.replace("asian_handicap_", "").replace("_points", "").replace("_", ".")
            SportMarketRegistry.register(
                Sport.VOLLEYBALL,
                {
                    handicap.value: cls.create_market_lambda(
                        main_market="Asian Handicap",
                        specific_market=f"Asian Handicap {numeric_part} Points",
                        odds_labels=["points_handicap_team_1", "points_handicap_team_2"],
                    )
                },
            )

        # Correct Score
        for correct_score in VolleyballCorrectScoreMarket:
            numeric_part = correct_score.value.replace("correct_score_", "").replace("_", ":")
            SportMarketRegistry.register(
                Sport.VOLLEYBALL,
                {
                    correct_score.value: cls.create_market_lambda(
                        main_market="Correct Score",
                        specific_market=f"{numeric_part}",
                        odds_labels=["correct_score"],
                    )
                },
            )
```

Note: the `numeric_part` for `asian_handicap_+2_5_sets` becomes `+2.5` (the leading `+` is preserved; only `_` → `.`), yielding `Asian Handicap +2.5 Sets` — matching the live label. For `asian_handicap_-2_5_sets` it becomes `-2.5`.

- [ ] **Step 5: Wire into `register_all_markets`**

In `src/oddsharvester/core/sport_market_registry.py`, in `register_all_markets`, add after `cls.register_handball_markets()`:

```python
        cls.register_volleyball_markets()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_sport_market_registry.py -q`
Expected: PASS (all, including `test_register_all_markets` and `_integration`)

- [ ] **Step 7: Commit**

```bash
git add src/oddsharvester/core/sport_market_registry.py tests/core/test_sport_market_registry.py
git commit -m "feat: register volleyball markets (Sets/Points dual-axis + correct score)"
```

---

## Task 5: League URL mapping (with live validation/reconcile)

**Files:**
- Modify: `src/oddsharvester/utils/sport_league_constants.py`
- Test: `tests/utils/test_sport_league_constants.py`

> The handball commit `6d41c4a` proved the OddsPortal *results-listing* slug is NOT always the league *base* URL (e.g. handball `europe/ehf-champions-league` results page → base URL `europe/champions-league`). The base URLs below are best-effort starting points and MUST be validated/reconciled in Step 5 before the task is considered done.

- [ ] **Step 1: Write the failing test**

Append to `tests/utils/test_sport_league_constants.py`:

```python
class TestVolleyballLeagueConstants:
    """Guards the production volleyball league mapping."""

    def test_volleyball_sport_present(self, fresh_mapping):
        assert Sport.VOLLEYBALL in fresh_mapping

    def test_volleyball_expected_leagues(self, fresh_mapping):
        leagues = fresh_mapping[Sport.VOLLEYBALL]
        expected = {
            "italy-superlega",
            "poland-plusliga",
            "russia-superliga",
            "france-ligue-a",
            "germany-1-bundesliga",
            "turkey-efeler-ligi",
            "brazil-superliga",
            "japan-sv-league",
            "cev-champions-league",
            "nations-league",
        }
        assert expected.issubset(set(leagues.keys()))

    def test_volleyball_urls_well_formed(self, fresh_mapping):
        leagues = fresh_mapping[Sport.VOLLEYBALL]
        for slug, url in leagues.items():
            assert url.startswith("https://www.oddsportal.com/volleyball/"), f"{slug}: {url}"
            assert url.endswith("/"), f"{slug} URL must end with '/': {url}"

    def test_italy_superlega_url(self, fresh_mapping):
        assert (
            fresh_mapping[Sport.VOLLEYBALL]["italy-superlega"]
            == "https://www.oddsportal.com/volleyball/italy/superlega/"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_sport_league_constants.py::TestVolleyballLeagueConstants -q`
Expected: FAIL (`Sport.VOLLEYBALL` not in mapping)

- [ ] **Step 3: Add the league mapping**

In `src/oddsharvester/utils/sport_league_constants.py`, add to `SPORTS_LEAGUES_URLS_MAPPING` after the `Sport.HANDBALL: {...}` block:

```python
    Sport.VOLLEYBALL: {
        "italy-superlega": "https://www.oddsportal.com/volleyball/italy/superlega/",
        "poland-plusliga": "https://www.oddsportal.com/volleyball/poland/plusliga/",
        "russia-superliga": "https://www.oddsportal.com/volleyball/russia/superliga/",
        "france-ligue-a": "https://www.oddsportal.com/volleyball/france/ligue-a/",
        "germany-1-bundesliga": "https://www.oddsportal.com/volleyball/germany/1-bundesliga/",
        "turkey-efeler-ligi": "https://www.oddsportal.com/volleyball/turkey/efeler-ligi/",
        "brazil-superliga": "https://www.oddsportal.com/volleyball/brazil/superliga/",
        "japan-sv-league": "https://www.oddsportal.com/volleyball/japan/sv-league/",
        "cev-champions-league": "https://www.oddsportal.com/volleyball/europe/champions-league/",
        "nations-league": "https://www.oddsportal.com/volleyball/world/nations-league/",
    },
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_sport_league_constants.py::TestVolleyballLeagueConstants -q`
Expected: PASS

- [ ] **Step 5: Validate league URLs live and reconcile**

Run (requires internet):
```bash
uv run python scripts/validate_league.py -s volleyball --all
```

For every league the script reports as INVALID / no match links, open `https://www.oddsportal.com/volleyball/<country>/<results-slug>/results/` in a browser, click into a match, and read the canonical base-league URL from the breadcrumb / season links (the path segment without `-YYYY-YYYY`). Update the offending entry in `SPORTS_LEAGUES_URLS_MAPPING` AND the corresponding expected URL/slug in the test if a slug changes. Known likely adjustments: `cev-champions-league` (OddsPortal localizes the results path as `europe/liga-de-campeones`; the base URL may be `europe/champions-league` or `europe/liga-de-campeones`), `nations-league`. Re-run the validator until every kept league passes; drop any league that has no stable URL rather than shipping a broken one (and remove it from the test's `expected` set).

- [ ] **Step 6: Re-run the league test and commit**

Run: `uv run pytest tests/utils/test_sport_league_constants.py -q`
Expected: PASS

```bash
git add src/oddsharvester/utils/sport_league_constants.py tests/utils/test_sport_league_constants.py
git commit -m "feat: add volleyball league URL mapping (validated live)"
```

---

## Task 6: url_builder volleyball coverage

**Files:**
- Modify: `tests/core/test_url_builder.py`

- [ ] **Step 1: Add the failing test data**

In `tests/core/test_url_builder.py`, near the other per-sport `SPORTS_LEAGUES_URLS_MAPPING[Sport.X] = {...}` overrides at the top, add:

```python
SPORTS_LEAGUES_URLS_MAPPING[Sport.VOLLEYBALL] = {
    "italy-superlega": f"{ODDSPORTAL_BASE_URL}/volleyball/italy/superlega",
}
```

Then add to the parametrize list of `test_get_league_url` (next to the handball case):

```python
        ("volleyball", "italy-superlega", f"{ODDSPORTAL_BASE_URL}/volleyball/italy/superlega"),
```

- [ ] **Step 2: Run test to verify behaviour**

Run: `uv run pytest tests/core/test_url_builder.py -q`
Expected: PASS — `URLBuilder` resolves any registered sport generically (confirmed by handball commit `d78da7d`); the new parametrized case passes with no production change.

> If any existing `test_url_builder.py` test asserts an "invalid sport" using a literal that is now a real sport, it already uses `"cricket"` (changed during the handball work) — no edit needed. If a failure shows a stale literal, change that literal to an unsupported sport string (e.g. `"cricket"`).

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_url_builder.py
git commit -m "test: cover volleyball league URL in url_builder"
```

---

## Task 7: Integration test + live odds-band reconcile

**Files:**
- Create: `tests/integration/test_volleyball.py`
- Possibly modify: `src/oddsharvester/utils/sport_market_constants.py` (band reconcile)

- [ ] **Step 1: Create the live-only integration test**

Volleyball match pages use the H2H fragmented URL pattern (`/volleyball/h2h/<t1-id>/<t2-id>/#<hash>`) which HAR replay cannot reproduce (per `CLAUDE.md` — same as NBA/baseball). Mirror `tests/integration/test_handball.py` structure but mark `live_only`. Create `tests/integration/test_volleyball.py`:

```python
"""Integration tests for volleyball scraping.

Regression guard: volleyball must STORE ODDS, not just match metadata.
The home_away odds field must be non-empty.

NOTE: volleyball leagues on OddsPortal use H2H fragment URLs
(/volleyball/h2h/<team1-id>/<team2-id>/#<match-id>), which cannot be replayed
deterministically from HAR (same limitation as NBA/baseball/handball H2H tests).
This test is marked live_only and SKIPS in default HAR-replay mode. Run with
--live against a real H2H URL, or capture a fixture once a direct match URL is
available:

    uv run python -m tests.integration.helpers.capture --sport volleyball \
        --league italy-superlega \
        --match-url "<MATCH_URL>" \
        --markets "home_away" \
        --period "full_time" \
        --bookies-filter "all" \
        --capture-har
"""

import json

import pytest

from tests.integration.helpers.comparison import compare_match_data

SUPERLEGA_MATCH = {
    "sport": "volleyball",
    "league": "italy-superlega",
    "match_id": "PLACEHOLDER_CAPTURE_PENDING",
    "url": "https://www.oddsportal.com/volleyball/italy/superlega/",
}


@pytest.mark.integration
@pytest.mark.live_only
class TestVolleyballBasicMarkets:
    """Regression tests for volleyball odds extraction (home_away must be non-empty)."""

    def test_vb_001_home_away_full_time(
        self,
        run_scraper,
        load_fixture,
        temp_output_dir,
        fixture_exists,
        har_for_match,
    ):
        """VB-001: Volleyball home_away market, full time, all bookies — odds must be present."""
        fixture_name = "home_away_full_time_all.json"

        if not fixture_exists(
            SUPERLEGA_MATCH["sport"],
            SUPERLEGA_MATCH["league"],
            SUPERLEGA_MATCH["match_id"],
            fixture_name,
        ):
            pytest.skip(f"Fixture not yet captured: {fixture_name} — see module docstring")

        output_path = temp_output_dir / "output"

        exit_code, _stdout, stderr = run_scraper(
            sport="volleyball",
            match_link=SUPERLEGA_MATCH["url"],
            markets=["home_away"],
            output_path=output_path,
            period="full_time",
            bookies_filter="all",
            har_path=har_for_match(
                SUPERLEGA_MATCH["sport"],
                SUPERLEGA_MATCH["league"],
                SUPERLEGA_MATCH["match_id"],
                fixture_name,
            ),
        )

        assert exit_code == 0, f"Scraper failed: {stderr}"

        with open(f"{output_path}.json") as f:
            actual = json.load(f)

        assert actual[0].get("home_away") or (actual[0].get("odds") or {}).get(
            "home_away"
        ), "Volleyball regression: home_away odds missing — scraper stored metadata only"

        expected = load_fixture(
            SUPERLEGA_MATCH["sport"],
            SUPERLEGA_MATCH["league"],
            SUPERLEGA_MATCH["match_id"],
            fixture_name,
        )

        result = compare_match_data(actual[0], expected[0])
        assert result.passed, str(result)
```

- [ ] **Step 2: Verify the test is collected and SKIPS in default mode**

Run: `uv run pytest tests/integration/test_volleyball.py -q -m integration`
Expected: 1 skipped (live_only without `--live`, or fixture-pending skip). No errors/failures.

- [ ] **Step 3: Live-verify odds bands and reconcile enums**

Run a real live scrape against a current volleyball H2H match (find one via `https://www.oddsportal.com/volleyball/italy/superlega/results/` → click a finished match → copy the `/volleyball/h2h/...#...` URL):

```bash
uv run oddsharvester scrape-historic --sport volleyball --leagues italy-superlega \
    --season 2024-2025 --markets home_away --max-matches 1
```

Then open one match page in a browser and read the actual `Over/Under` and `Asian Handicap` submarket labels (the `+N.5 Sets` / `+N.5 Points` and `±N.5 Sets` / `±N.5 Points` rows). Compare the numeric ranges against `VolleyballOverUnderPointsMarket` and `VolleyballAsianHandicapPointsMarket`. If the live bands extend beyond or differ from 150.5–230.5 (points O/U) or ±1.5–±9.5 (points AH), adjust the enum members in `sport_market_constants.py` to cover the observed range (regenerate via the Task 1 Step 5 script with new bounds), and update the Task 1 enum guard test if a referenced member name changes. Re-run:

Run: `uv run pytest tests/utils/test_sport_market_constants.py -q && uv run pytest tests/core/test_sport_market_registry.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_volleyball.py src/oddsharvester/utils/sport_market_constants.py
git commit -m "test: add volleyball integration test (live_only) and reconcile odds bands"
```

---

## Task 8: Documentation

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `docs/agentic-gotchas.md`

- [ ] **Step 1: Update README supported-sports table**

In `README.md`, add a row after the Handball row in the Supported Sports table:

```
| 🏐 Volleyball        | `home_away` `total_sets_over/under` `total_points_over/under` `asian_handicap` `correct_score` |
```

- [ ] **Step 2: Update CLAUDE.md sport list**

In `CLAUDE.md` line 7 (Project Overview), change the sport list to include volleyball:

Find: `Supports multiple sports (football, tennis, basketball, rugby, ice hockey, baseball, American football, handball),`
Replace with: `Supports multiple sports (football, tennis, basketball, rugby, ice hockey, baseball, American football, handball, volleyball),`

- [ ] **Step 3: Append §8 gotcha**

In `docs/agentic-gotchas.md`, immediately before the `## Adding a new gotcha` section, insert:

```markdown
## §8 — Volleyball Over/Under and Asian Handicap each split into a Sets axis and a Points axis

**Severity:** High — registering only one axis silently drops half the volleyball O/U and AH submarkets.

Unlike handball (single goals axis), volleyball's `Over/Under` and `Asian Handicap`
tabs each contain TWO independent submarket families, disambiguated only by a
suffix word in the row label:

| Tab | Submarket label form | Example |
|---|---|---|
| Over/Under | `Over/Under +{N}.5 Sets` | `Over/Under +3.5 Sets` |
| Over/Under | `Over/Under +{N}.5 Points` | `Over/Under +184.5 Points` |
| Asian Handicap | `Asian Handicap {±N}.5 Sets` | `Asian Handicap -2.5 Sets` |
| Asian Handicap | `Asian Handicap {±N}.5 Points` | `Asian Handicap +5.5 Points` |

The `specific_market` string passed to the extractor MUST include the trailing
` Sets` / ` Points` word or the wrong family is matched. This mirrors tennis
(`Games` vs `Sets`), not handball. Verified live against Italian SuperLega,
May 2026.

Volleyball also has NO draw-based markets (no `1X2`, `DNB`, `Double Chance`) —
only `Home/Away`. Periods are `Full Time` + `1st`–`5th Set`. `Correct Score`
outcomes are exactly `3:0 3:1 3:2 0:3 1:3 2:3` and exist only at `Full Time`.

### HAR-replay consequence

All volleyball league match pages use the H2H fragment URL pattern
(`/volleyball/h2h/<t1-id>/<t2-id>/#<hash>`). Like NBA/baseball/handball, the
integration test (`tests/integration/test_volleyball.py`) is marked
`@pytest.mark.live_only` and skipped in default HAR-replay mode.

---
```

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md docs/agentic-gotchas.md
git commit -m "docs: document volleyball support and Sets/Points dual-axis gotcha"
```

---

## Task 9: Full regression gate

**Files:** none (verification only)

- [ ] **Step 1: Run the full unit suite**

Run: `uv run pytest tests/ -q --ignore=tests/integration/`
Expected: PASS — zero failures. If any prior-sport test fails, the change was not additive; investigate before proceeding.

- [ ] **Step 2: Run integration tests in default (replay) mode**

Run: `uv run pytest tests/integration/ -q -m integration`
Expected: existing fixtures pass; `test_volleyball.py` SKIPS (live_only). No failures.

- [ ] **Step 3: Lint and format**

Run: `uv run ruff format . && uv run ruff check --fix src/`
Expected: no remaining errors. Re-run `uv run pytest tests/ -q --ignore=tests/integration/` if Ruff changed any file.

- [ ] **Step 4: Final commit (only if Ruff changed files)**

```bash
git add -A
git commit -m "chore: volleyball lint/format cleanup"
```

---

## Self-Review Notes

- **Spec coverage:** Sport enum (T1), 6 market enums (T1), SPORT_MARKETS_MAPPING (T2), VolleyballPeriod + registry (T3), register_volleyball_markets with Sets/Points/Correct-Score (T4), 10-league mapping + live validation (T5), url_builder coverage (T6), live_only integration test + band reconcile (T7), README/CLAUDE/gotchas §8 (T8), regression gate (T9). All spec sections mapped.
- **Placeholders:** Points-band enum members are generated by an explicit, runnable script (T1 S5) and reconciled against live data (T7 S3); no `TODO`/`TBD` left for the engineer.
- **Type consistency:** Enum class names, `Sport.VOLLEYBALL`, and method names (`register_volleyball_markets`, `get_display_label`, `get_internal_value`) are used identically across T1–T8. odds_labels (`sets_handicap_team_1/2`, `points_handicap_team_1/2`, `odds_over/odds_under`, `correct_score`) are defined once in T4 and not referenced elsewhere.
