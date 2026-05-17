# Regional OddsPortal domain support (`--base-url`)

**Date:** 2026-05-17
**Branch:** `feat/regional-base-url` (off `master`, independent of `feat/handball-support`)
**Notion task:** Support multi-domaine régional OddsPortal (base_url paramétrable) — `361ebd78-e2ee-81ed-af10-fd3a9ea9407a`
**Origin:** GitHub discussion #24; related issue #45 (VPN-for-bookmaker-coverage)

## Objective

Let a user target a regional OddsPortal mirror (e.g. `centroquote.it`) instead of the
hardcoded `www.oddsportal.com`, via a single CLI option. The page structure across
regional mirrors is identical — only the scheme+host differ. Regional domains expose
a different (often larger) set of bookmakers, which today users only reach via VPN.

## Non-goals (YAGNI)

- No `--region` presets / named-mirror table.
- No TLD→locale/timezone inference table.
- No rewrite of the 100+ absolute URLs in `sport_league_constants.py`.
- No parameterization of the HAR replay URL pattern.
- No auto-adjustment of locale/timezone.

## Decisions (from brainstorming)

1. **CLI surface:** raw `--base-url <url>` (no presets to curate).
2. **League URLs:** runtime domain swap. The 100+ absolute `.com` entries in
   `sport_league_constants.py` stay untouched (`.com` is the canonical default);
   the domain is substituted at runtime. This also avoids a diff collision with the
   in-progress `feat/handball-support` branch, which edits that same file.
3. **Locale/timezone:** stay independent of `--base-url`; emit a single
   non-blocking warning on a likely mismatch (no auto-derive).

## Chosen approach: explicit threading through a single normalizer

Rejected alternatives:
- **Mutable module global** (overwrite `ODDSPORTAL_BASE_URL` / config singleton):
  hidden global state, order-dependent, clashes with static `URLBuilder` methods,
  hard to test in parallel.
- **Environment variable** read at each construction point: even more implicit;
  a clean kwargs path already exists for `proxy`/`locale`.

The chosen approach mirrors how `proxy` and `browser_locale_timezone` are already
plumbed (`run_scraper` kwarg → scraper constructor) and keeps `URLBuilder` pure.

## Design

### 1. Core helper — `rebase_url`

New pure function `rebase_url(url: str, base_url: str | None) -> str` in
`src/oddsharvester/core/url_builder.py`.

- `base_url` is `None` or empty → return `url` unchanged (zero behavior change for
  the default `.com` path).
- Otherwise: replace **scheme + netloc** of `url` with those parsed from `base_url`,
  preserving path, query, and fragment exactly.
- Idempotent; no trailing-slash mutation; works for `http` and `https`.
- Implemented with `urllib.parse.urlsplit` / `urlunsplit`.

### 2. `URLBuilder` methods

Add `base_url: str | None = None` keyword arg to:
- `get_historic_matches_url`
- `get_upcoming_matches_url`
- `get_league_url`

Each returns `rebase_url(<existing computed result>, base_url)`. All existing
season/baseball/alias logic is unchanged — the swap is applied to the final string.
`sport_league_constants.py` is **not modified**.

### 3. Match-link join in `base_scraper.py`

The line `full_url = f"{ODDSPORTAL_BASE_URL}{href}"` (currently `base_scraper.py:312`)
builds absolute match URLs from relative `href`s on listing pages. It must use the
configured base. `base_url` is stored on the scraper instance via a constructor
parameter, defaulting to `None` → falls back to `ODDSPORTAL_BASE_URL`. The join
becomes `f"{self._base_url or ODDSPORTAL_BASE_URL}{href}"` (host-only base, no path).

### 4. Plumbing

`--base-url` Click option added to `common_options` in `src/oddsharvester/cli/options.py`
(so both `historic` and `upcoming` commands inherit it) → `kwargs` →
`run_scraper(base_url=...)` → `OddsPortalScraper(base_url=...)` → forwarded into the
two `URLBuilder` call sites in `odds_portal_scraper.py` (lines ~101 and ~170) and the
`base_scraper` href join.

`run_scraper` gains a `base_url: str | None = None` parameter.

### 5. Validation

A validator in `src/oddsharvester/cli/validators.py` ensures `--base-url`:
- parses to a URL with a scheme in `{http, https}` **and** a non-empty host,
- has no path/query/fragment (host-only; e.g. `https://www.centroquote.it`),

and otherwise raises a `click.BadParameter` with a clear message. Empty/unset →
valid (feature off).

### 6. Locale mismatch warning

In `run_scraper`, after config resolution: if `base_url` is set and its host is not
`*.oddsportal.com`, while both `browser_locale_timezone` and `browser_timezone_id`
are unset/default, emit one non-blocking `logger.warning` recommending the user pass
`--locale`/`--timezone` matching the region (rationale: issue #45). No behavior
change, no auto-derive. Fires at most once per run.

### 7. HAR / testing implication (known limitation, not a blocker)

`HAR_REPLAY_URL_PATTERN = "**oddsportal.com/**"` in `playwright_manager.py` governs
integration HAR replay only; every fixture is `.com`. `--base-url` is a live-only
feature and is never exercised under HAR replay. This is documented as a limitation;
the HAR pattern is unchanged.

## Testing plan

Unit tests (mirror source structure under `tests/`):

- `rebase_url`: `None`/empty passthrough; scheme+host swap; path/query/fragment
  preserved; trailing-slash neutrality; `http` vs `https`; idempotence.
- `URLBuilder.{get_historic_matches_url,get_upcoming_matches_url,get_league_url}`
  with and without `base_url`, including season variants and the baseball special
  case, asserting only the domain changes.
- `--base-url` validator: valid host-only URL; missing scheme; URL with a path;
  empty/unset; non-http scheme.
- Locale-mismatch warning: fires only when `base_url` is non-`.com` and
  locale/timezone unset; silent otherwise (`caplog`).
- base_scraper match-link join honors the configured base (default unchanged).

Docs:

- README + `--help`: document `--base-url` and recommend pairing with
  `--locale`/`--timezone`.
- If regional-domain scraping surfaces new OddsPortal parsing behavior, append an
  entry to `docs/agentic-gotchas.md` (per CLAUDE.md gotchas rule).

## Success criterion

Scraping a league from a regional mirror (e.g. an `.it` domain) returns coherent
data — ideally more bookmakers than `.com` for the same match — with no regression
to the default `.com` path (all existing tests green, `rebase_url(url, None) == url`).
