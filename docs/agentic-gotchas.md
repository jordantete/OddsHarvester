# OddsPortal Scraping Gotchas

Reusable patterns extracted from past bugs. Read this **before** working on
anything that touches DOM parsing, league configuration, CLI options, or
Playwright config — these traps are not deducible from the code alone because
they describe *OddsPortal server behaviour*, not our code.

Each gotcha is structured as: **the trap → the detection signal → the fix
pattern → references**.

The gotchas are grouped by theme:

- **§1–§3** — OddsPortal serves untrustworthy data (correctness, completeness, format).
- **§4** — OddsPortal renames things over time (league slugs).
- **§5** — Our own code architecture (where logic belongs).
- **§6** — Operational: anti-bot detection symptoms.

---

## §1 — SSR ships stale or phantom data that contradicts the requested URL

**Severity:** High — has produced silent data corruption three times under
three different shapes.

OddsPortal's server-rendered HTML cannot be trusted as a source of truth for
the match the URL is requesting. The page is built around a React SPA that
mutates the visible content client-side based on URL fragments or AJAX calls,
and the SSR payload is whatever was convenient for the server (the latest
match, a phantom hidden duplicate, etc.).

### Three observed shapes

| Shape | Where | Symptom | Fix commit |
|---|---|---|---|
| **a.** Embedded `react-event-header` JSON returns the most-recent matchup, not the requested historic match | `<div id="react-event-header" data='…'>` on H2H detail pages | All fields (teams, date, scores) belong to a different match | `cef2bf3` — DOM-first extraction with per-field JSON fallback |
| **b.** DOM **and** JSON both wrong because the SSR for `/sport/h2h/home/away/#fragment` renders the *upcoming* matchup, the SPA hasn't swapped yet | H2H pages where teams play each other repeatedly (MLB, NBA, ATP) | `match_date` is in the future on a historic scrape | Issue #60 — force `hashchange` via `page.evaluate`, wait for `eventData.id === fragment` |
| **c.** League listings include duplicate "phantom" event rows hidden in CSS, whose href points to a corrupted slug that 301-redirects to an unrelated match | `<tr style="left:-9999px">` (also `display:none`, `visibility:hidden`, `top:-9999px`) on `/results/` listings | Random unrelated matches scraped from a league listing | `f7c6ee4` — `_is_offscreen_row` helper, skip before processing |

### Detection signal (general rule)

**Never trust the first thing you parse.** Cross-reference with at least one
independent signal:

- **URL fragment vs `eventData.id`** — if both exist and differ, the embedded
  JSON is *not* the requested match. But this signal alone is **necessary, not
  sufficient**: cases **a** and **b** both trip it yet need opposite handling.
  In case **a** (PR #54: stale *recent* match) the SPA *has* hydrated the DOM to
  the correct fragment match and `eventData.id` **never** updates — resyncing is
  impossible and dropping regresses PR #54. In case **b** (issue #60: *upcoming*
  match) the DOM is still the wrong match too. **Discriminate by DOM-vs-JSON
  date**, not by `eventData.id` alone: if the DOM date differs from the JSON
  date, the DOM resolved independently → trust DOM (case a); if DOM date equals
  the stale JSON date or is absent → SPA not reconciled → resync or drop
  (case b). Gating purely on `fragment != eventData.id` shipped a regression
  that dropped every PR #54-class historic H2H match (see issue #60 follow-up).
- **CSS visibility** — for any row/element you iterate over on a listing page,
  check `style` for `left:-9999px`, `top:-9999px`, `display:none`,
  `visibility:hidden` (markers live in `_OFFSCREEN_STYLE_MARKERS` in
  `base_scraper.py`). These are not user-visible and should be skipped.
- **DOM vs JSON** — when both exist for the same field (team names, date,
  scores), prefer the DOM (`data-testid` attributes) and use JSON only as
  fallback. The DOM is what the user sees; the embedded JSON may be stale.

### Fix pattern

1. Add a detection step that produces a boolean "trust signal".
2. If untrustworthy, either:
   - Skip the row (when there's nothing to recover — case c).
   - Force a reconciliation step (case b: drive the SPA via `page.evaluate`
     and `page.wait_for_function`, then re-parse).
   - Drop the match with an ERROR log (better than emitting wrong data).
3. Add a HAR replay test that captures the *wrong* SSR payload so the
   regression is locked down without needing the live site.

### Before adding new extraction code

Ask: "what would I see if OddsPortal sent me a different match's data here?"
If the answer is "nothing — I'd just emit wrong data silently", you need a
trust signal. The cost of an extra DOM check is far lower than the cost of a
silent data-quality bug that ships for weeks.

---

## §2 — Client-side rendering silently truncates listings and URLs

**Severity:** High — caused EPL season scrapes to return ~60 matches instead
of ~380 (≈84% data loss) without any error.

OddsPortal optimizes initial page weight by relying on the client (browser
behaviour, ellipsis-style pagination widgets, URL conventions) to fill in
information that isn't present in the SSR HTML. Naively reading the rendered
DOM gives you an incomplete view — and there are no errors raised, just
fewer results than expected.

### Three observed shapes

| Shape | Where | Symptom | Fix commit |
|---|---|---|---|
| **a.** Pagination widget collapses long ranges with an ellipsis (e.g. `[1, 2, 3, …, 28]`); only the visible page numbers exist in the HTML | League `/results/` listings beyond ~5 pages | Scraper visits 3–5 pages instead of 28; ≈85% of season missing | PR #50 — `_fill_pagination_gaps` generates the full `1..max_page` range |
| **b.** `window.scrollTo(0, document.body.scrollHeight)` jumps past lazy-loader trigger points without firing the IntersectionObserver | League listings, market dropdowns | ~5 event rows loaded instead of ~50 per page | PR #50 — `scroll_until_loaded` now steps incrementally (500px) |
| **c.** The current season URL has **no year suffix** (`/football/england/premier-league/results/`) while historic seasons do (`/premier-league-2024-2025/results/`) | URL builder for `--season current` (or implicit current season) | Builder appends a `-YYYY-YYYY` suffix → 404 / empty page | PR #50 — `URLBuilder` detects when requested season's end year is the current calendar year and omits the suffix |

### Detection signal (general rule)

**Compare what you got against what you expected.** Most of these bugs slip
through because the scraper "succeeded": no error raised, just less data.
Build sanity checks:

- **Counts** — if the page advertises N pages, the scraper must visit N
  pages. If a page lists "showing 1–50 of 142", we must end up with ~50
  rows per page. Log discrepancies as WARNING.
- **URL convention** — when generating URLs from templates, verify the
  produced URL exists in a browser before shipping the change. OddsPortal
  has at least three URL conventions (`/results/`, `-YYYY/results/`,
  `-YYYY-YYYY/results/`) and the choice depends on the season's relationship
  to *today*, not on the season string alone.

### Fix pattern

1. Identify the "happy default" the rendered DOM gives you, and challenge it.
   - Pagination → don't trust the rendered list; compute the range.
   - Scroll → don't trust `scrollHeight`; iterate.
   - URL builder → don't trust the year-suffix template; check whether the
     season is the current one.
2. When you fix a "silent truncation" bug, add a regression test asserting
   the **count**, not just the structure. A test that asserts "we got at
   least one row" is what allowed the bug to ship in the first place.

### Heuristic for spotting future variants

Any place where we use a DOM measurement (`length`, `scrollHeight`, last
visible element) as a stopping condition is a candidate. OddsPortal's React
app is built to defer work; assume any "edge of the rendered tree" is a lie.

---

## §3 — Per-bookmaker / per-geography data formats require fallback chains

**Severity:** Medium — silently discarded ~19K odds history records per EPL
season scrape from UK IPs.

OddsPortal's data shape varies depending on the bookmaker and the user's
geographic context. A field that is a string for one bookmaker may be missing
entirely for another, or in a completely different format. Single-selector
extraction or naive type conversion drops data with no error.

### Two observed shapes

| Shape | Where | Symptom | Fix commit |
|---|---|---|---|
| **a.** Some UK bookmakers (Betfred, BetVictor, bwin) return fractional odds (`4/5`) even when `--odds-format "Decimal Odds"` is requested | Odds history rows on detail pages | `ValueError` from `float("4/5")` → all odds history for that bookmaker silently discarded; ≈19K errors per EPL season | PR #49 — `parse_odds_value()` detects `N/M`, returns `N/M + 1`; fallback `float()` |
| **b.** Bookmaker name resolution depended only on `<img class="bookmaker-logo" title="…">`, which is absent for some bookmakers; CTA-style `<a title>` ("Go to Betfair Exchange website!") leaked through as the name | Bookmaker columns in odds tables | Rows labelled "Unknown" or dropped entirely | PR #49 — 3-step fallback chain: `img[title]` → `a[title]` → `img[alt]`, with CTA-text normalisation |

### Detection signal

When you write code that reads a single attribute or applies a single type
conversion to OddsPortal-sourced data, ask:

1. Is this format identical for **every bookmaker** (UK, Asian, US, exchange)?
2. Is this attribute present for **every row**?
3. Does the parser have a sensible default when the value is missing or in
   an unexpected format?

If any answer is "no" or "I don't know", you need a fallback chain.

### Fix pattern

1. Define an ordered list of selectors / parsers, most preferred first.
2. Walk the list, return on first success.
3. Return `None` when nothing resolves, and let the caller decide whether to
   skip the row, log a WARNING, or substitute a default.
4. **Skip silently → log loudly**: `WARNING` for fallback usage (so we
   notice when "fallback" becomes "primary"); `DEBUG` for per-row noise.
5. Add a regression test for the unusual case — without it, the fallback
   will rot.

### Anti-pattern: catching `ValueError` and pretending the row didn't exist

The original fractional-odds bug existed for months because the
`float()` exception was caught and logged at DEBUG with no aggregation. Per-row
DEBUG noise hides systemic failures. Aggregate counts at INFO ("dropped 19,332
rows due to parse errors") so the next contributor sees the problem.

---

## §4 — League slugs change when sponsorship deals change

**Severity:** Medium — recurs every time a league signs a new title sponsor.

OddsPortal renames league URL slugs to reflect title sponsors:
`brazil/serie-a` became `brazil/serie-a-betano` in 2024; Czech `fortuna-liga`
became `chance-liga` in 2024–2025; Serbia `super-liga` became
`mozzart-bet-super-liga`. Historic seasons keep the **old** URL; only the
current season uses the new slug. Naively patching the slug in
`SPORTS_LEAGUES_URLS_MAPPING` breaks every historic scrape for older seasons.

### Detection signal

A `validate_league.py` run returns 404 for a league that previously worked, or
the URL on oddsportal.com no longer matches the entry in
`sport_league_constants.py`. Also worth watching: sports business news
(title-sponsor announcements for major leagues).

### Fix pattern

1. Update `SPORTS_LEAGUES_URLS_MAPPING` to the **new** (current) slug.
2. Add an entry to `LEAGUE_SEASON_ALIASES` in
   `src/oddsharvester/utils/league_aliases.py` mapping the season *cutoff
   year* to the **old** slug:
   ```python
   "brazil-serie-a": {
       2023: "serie-a",   # seasons ≤ 2023 use this slug
   },
   ```
3. Add a `URLBuilder` test that verifies both old and new seasons resolve to
   the right URL.
4. Add a `LEAGUE_SEASON_ALIASES` unit test asserting the mapping.

### When adding a brand-new league

Before adding the entry, manually visit a historic season page on
oddsportal.com (e.g., `…/serie-a-2021-2022/results/`). If the slug differs
from the current season, set up the alias *immediately* — don't wait for the
first user to file an issue.

**Reference commits/PRs:** `708a8cf` (Brazil Serie A → Betano), PR #43
(Czech / Mexico / Serbia aliases).

---

## §5 — CLI options need normalization at the lowest layer, never in the CLI

**Severity:** Medium — causes inconsistent behaviour across sports / commands.

`--season current` was initially normalized in the CLI command
(`historic.py`) using a hardcoded whitelist of "sports that support
'current'": `{"tennis", "football", "baseball", "ice-hockey", "rugby-league",
"rugby-union"}`. Sports outside the whitelist hit `URLBuilder` which raised
`ValueError` for `"current"`. Result: `--season current` worked for some
sports and crashed for others.

### Detection signal

Any time you see a hardcoded list of "sports/markets/leagues that support
feature X" *inside the CLI layer*, that's the smell. The CLI should be a
thin pass-through; behaviour-defining logic belongs in the layer that knows
the domain.

### Fix pattern

1. Move the normalization to the lowest layer that owns the domain knowledge.
   For URL-shape decisions, that's `URLBuilder`. For market resolution,
   that's `SportMarketRegistry`. Etc.
2. Delete the CLI-side whitelist.
3. Make the lower-layer behaviour explicit in the docstring (e.g., "Accepts
   `'current'` (case-insensitive), `None`, or empty string for the current
   season").
4. Add tests at the lower layer covering all sports — not just the ones the
   CLI used to whitelist.

### Rule of thumb

The CLI parses arguments and dispatches. It should not encode business rules
about which combinations are valid for which sport. If you find yourself
writing `if sport in {...}` inside a CLI handler, stop and push the logic
down.

**Reference commit:** `915df2f` (`current` season normalization centralized
in `URLBuilder`).

---

## §6 — Anti-bot detection: distinguish symptom from cause

**Severity:** Operational — burns hours debugging the wrong layer.

OddsPortal periodically tightens its anti-bot detection. When triggered, the
visible symptom is *almost always* the same: pages load but contain **0
event rows**, sometimes with a cookie banner timeout. The scraper completes
"successfully" with no parsing error.

Common triggers observed:

- **Headless mode in Docker/server environments without anti-detection flags**
  — `--disable-blink-features=AutomationControlled` is critical; Docker
  defaults to a narrower flag set than local (`7e199bd`).
- **VPN endpoints flagged after a few minutes** — same IP works initially,
  then gets challenged (issue #45).
- **OddsPortal rolling out a new anti-bot script** — symptom is sudden
  across-the-board failure with no code change (issue #29).

### Detection signal

The triage rule before touching parsing code:

```
0 event rows + 0 parse errors → suspect anti-bot, NOT parsing
```

Quick checks (in order):

1. Run the same command with `--headless=false`. If you see a Cloudflare
   challenge or a blank page, it's anti-bot.
2. Manually load the same URL in a normal browser from the same IP. If it
   works there but not from the scraper, it's anti-bot or stealth-script
   regression.
3. Check the `STEALTH_SCRIPT` and `PLAYWRIGHT_BROWSER_ARGS_DOCKER` /
   `PLAYWRIGHT_BROWSER_ARGS` constants in `playwright_manager.py` for
   divergence between local and Docker.

### Fix pattern

- For new Playwright/browser flags, add them to **both** local and Docker
  arg lists. The Docker list has been the source of multiple regressions
  because it lags behind local.
- When a user reports "scraping returns 0 results", request the output of
  `--headless=false` before assuming a parsing bug.
- Treat anti-bot fixes as urgent: a silent 0-results scrape that succeeds
  is worse than one that errors out, because users don't notice for days.

**Reference:** `7e199bd` (PR #38 — Docker anti-detection args), issues #29,
#45.

---

## Adding a new gotcha

When a fix lands that exposes an OddsPortal-specific behaviour an agent
couldn't deduce by reading the code, add it here. Criteria:

- The pattern has appeared **more than once**, OR is likely to recur
  (sponsor changes, SPA-vs-SSR mismatches, anti-bot tweaks, format
  variations across geographies).
- The fix is non-obvious from the code alone — the reader needs to know
  *why* the defensive check exists, not just that it does.
- The signal is describable: a future agent must be able to recognize the
  shape of the problem in new code.

Do **not** add: one-off bugs, fixes whose context is fully captured in the
commit message, generic Python/Playwright tips, or anything already covered
in `CLAUDE.md`.
