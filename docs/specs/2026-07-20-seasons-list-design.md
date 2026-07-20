# Seasons list (`--season` as a comma list)

**Date:** 2026-07-20
**Branch:** `feat/seasons-list` (off `master`)
**Origin:** GitHub issue #78, raised from #75. A bulk user needs several seasons
in one command. The motivating pain point: leagues that switched season format
mid-history (Russia moved to autumn-spring in 2011-2012, several South American
leagues went the other way), so the "one run per format" workaround from #75
does not cover them cleanly.

## Objective

Let `--season` accept a comma-separated list on `historic`, scraped as the
cartesian product with the existing `--league` list. One command covers N
leagues by M seasons, results merged into a single output through the normal
storage layer.

## Non-goals (YAGNI)

- No range syntax (`2015-2016..2020-2021`). Explicit lists only.
- No per-league table of which season format applies when. Invalid combos are
  simply attempted and report zero links (see decision 2).
- No automatic format fallback (retrying `2011` as `2011-2012`). Rejected as
  scope creep and because a legitimately empty season is indistinguishable from
  a wrong-format one.
- No concurrency across combos. The traversal stays sequential.
- No `--season` on `upcoming` (it has no season concept and passes `season=None`
  today).

## Decisions (from brainstorming)

1. **CLI shape:** `--season` becomes `COMMA_LIST`, stays `required=True`. A
   single value keeps working identically. Chosen over a separate `--seasons`
   flag for symmetry with `--league`, which is already `COMMA_LIST`.
2. **Mixed formats:** raw cartesian product. Each `(league, season)` pair is
   attempted as given. An invalid pair returns zero links, is reported, and the
   run continues. The user can pass both formats in one list and let the
   invalid pairs fall through.
3. **Output schema:** a `season` column on every row of every command, empty
   when there is no season. This is a **breaking schema change** (see below).
4. **Traversal:** sequential, league outer and season inner, so output stays
   grouped and deterministic.
5. **Reporting:** a per-combo summary table at end of run when more than one
   combo ran; single-combo runs keep today's one-line output.

## Breaking change

Inserting a `season` column mid-row changes the CSV schema for every command.
Any `--append` onto a file produced by an earlier version yields a
heterogeneous file, and positional downstream parsers break.

This differs deliberately from `--local-kickoff` (issue #76), which was made
opt-in specifically to keep existing schemas untouched. Here the column is
unconditional, so it must be called out in the README and in the release notes,
not only in the changelog.

## CLI behavior

- `--season 2022-2023` behaves exactly as today.
- `--season 2021-2022,2022-2023` scrapes both, in listed order.
- Duplicates are removed while preserving order, so `--season 2020,2020` runs
  one pass. `--league` does not deduplicate today, but here a duplicate costs a
  full listing pass with its pagination.
- `current` remains usable inside the list (`--season 2021-2022,current`). Each
  element is validated in isolation, so this falls out with no special case.
- `--max-pages` applies **per combo**, not across the run. Documented, since it
  is an obvious source of misunderstanding on bulk runs.
- Existing per-element error messages are preserved verbatim.

Examples:

```bash
# Several seasons, one league
oddsharvester historic --sport football --league england-premier-league \
    --season 2020-2021,2021-2022,2022-2023 --links-only --format csv --output links.csv

# Cartesian product with several leagues
oddsharvester historic --sport football \
    --league england-premier-league,spain-laliga \
    --season 2021-2022,2022-2023 --links-only

# League that switched format: pass both, let the invalid pairs report zero
oddsharvester historic --sport football --league russia-premier-league \
    --season 2010,2010-2011,2011,2011-2012 --links-only
```

## Core changes

### `cli/validators.py`

- Current `validate_season` body becomes `_validate_one_season(value)`,
  unchanged.
- New `validate_seasons(ctx, param, value)` maps it over the list and
  deduplicates with `dict.fromkeys` ordering.

### `cli/commands/historic.py`

- `--season` gains `type=COMMA_LIST` and `callback=validate_seasons`; the
  destination becomes `seasons`.
- End-of-run reporting renders the combo table when more than one combo ran.

### `core/scraper_app.py`

- `run_scraper(..., seasons: list[str] | None = None)`.
- The single-call shortcut becomes `len(leagues) == 1 and len(seasons) == 1`.
- `_scrape_multiple_leagues` is generalized to
  `_scrape_league_season_combos(scraper, scrape_func, leagues, seasons, sport, **kwargs)`,
  iterating `[(lg, s) for lg in leagues for s in (seasons or [None])]`.
  `upcoming` calls it with `seasons=None`, which degenerates to exactly today's
  behavior, so no separate branch is needed.
- `retry_scrape` wraps each combo. A combo that raises is collected as a failure
  and does not abort the run, matching today's `failed_leagues` handling.
- The helper populates `combo_stats` on the merged result.

### `core/scrape_result.py`

- `ScrapeResult` gains `combo_stats: list[dict] = field(default_factory=list)`,
  one entry per combo: league, season, successful count, failed count, and an
  errored flag distinguishing a combo that raised from one that returned
  nothing.
- `merge` leaves it alone; only the combo helper writes it.

### `core/base_scraper.py`

- The `details` literal gains `"season": None`, positioned right after
  `match_date`. This gives every row the column, at a stable position, for every
  command.

### `core/odds_portal_scraper.py`

- `scrape_historic` stamps the season onto its rows after `extract_match_odds`
  returns, since the per-match extraction has no knowledge of the season:

  ```python
  result = await self.extract_match_odds(...)
  for row in result.success:
      row["season"] = season
  return result
  ```

- `--links-only` rows already carry `season` through `_links_only_result` and
  need no change.

## Error handling

Unchanged contract. Operation-level retry with backoff per combo, failed listing
pages tracked without failing the run, exit code 1 only when nothing was
collected across all combos.

A combo returning zero links is **not** an error. It appears in the summary
table with a count of zero and does not affect the exit code.

A combo that raises after retries is distinct: it also appears in the table, but
marked as errored rather than as a zero count, so the two cases are not
conflated. The distinction matters for the "re-run just those" workflow, since a
zero-link combo is usually a deliberate wrong-format pair while an errored combo
is worth retrying.

## Tests

- **CLI** (`tests/cli/`):
  - `validate_seasons`: valid list, ordered deduplication, `current` mixed with
    explicit seasons, invalid element raises `BadParameter` with the existing
    message.
  - `--season` parsed as a list and forwarded to `run_scraper`.
  - Combo table rendered only when more than one combo ran.
- **Core** (`tests/core/`):
  - Combo generation order is league-outer, season-inner.
  - `seasons=None` degenerates to the current `upcoming` behavior.
  - Single league plus single season does not take the combo path.
  - Season stamping: `historic` rows carry their season, `upcoming` and
    `--match-link` rows carry `None`.
  - `combo_stats` includes a zero-link combo, and distinguishes it from a combo
    that raised.
- **Integration:** the existing single-season `historic` HAR replay must still
  pass, as the backward-compatibility guard. No multi-season HAR is captured;
  covering the product in unit tests was judged sufficient against the fixture
  volume it would cost.
- `uv run pytest tests/ -q` passes before and after.

## Docs

- README: `--season` documented as a list, cartesian product with `--league`,
  the mixed-format recipe for switched leagues, `--max-pages` per-combo note.
- Release notes: the `season` column schema break, called out explicitly for
  `--append` users.
