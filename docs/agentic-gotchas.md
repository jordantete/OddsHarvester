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
- **§7** — Regional mirror domains and the `--base-url` option.
- **§8** — Volleyball O/U and AH each split into a Sets axis and a Points axis.

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
| **c.** The current season URL has **no year suffix** (`/football/england/premier-league/results/`) while historic seasons do (`/premier-league-2024-2025/results/`) | URL builder for `--season current` (or implicit current season) | Builder appends a `-YYYY-YYYY` suffix → 404 / empty page | PR #50 first dropped the suffix when `end_year == current calendar year`; that heuristic silently sent a *finished* season to the base URL once OddsPortal rolled it over to the next season (issue #71). **Corrected:** the no-suffix URL is reserved for `current`/None; every explicit `YYYY`/`YYYY-YYYY` always carries the suffix |

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
  `-YYYY-YYYY/results/`). The no-suffix form serves *whatever season is
  currently live* and rolls over without notice, so it is reserved for an
  explicit `current`/None request; a named season (`YYYY` or `YYYY-YYYY`)
  must always use its suffixed form. Do **not** re-derive the choice from the
  calendar year — that is exactly what sent finished-season scrapes to the
  rolled-over season (issue #71).

### Fix pattern

1. Identify the "happy default" the rendered DOM gives you, and challenge it.
   - Pagination → don't trust the rendered list; compute the range.
   - Scroll → don't trust `scrollHeight`; iterate.
   - URL builder → reserve the no-suffix base URL for `current`/None; a named
     `YYYY`/`YYYY-YYYY` season always keeps its suffix. Don't re-derive the
     choice from the calendar year (that reinstates the issue #71 rollover bug).
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

### Renames are not always sponsor-driven (handball, May 2026)

Slug drift also happens without a title sponsor, and the OddsPortal
**localized results listing lies about the real slug**. While validating the
7 configured handball leagues against `https://www.oddsportal.com/results/#handball`:

| Configured slug (key kept) | Old/dead URL | Correct canonical URL |
|---|---|---|
| `ehf-champions-league` | `…/handball/europe/ehf-champions-league/` | `…/handball/europe/champions-league/` |
| `ehf-european-league` | `…/handball/europe/ehf-european-league/` | `…/handball/europe/european-league/` |
| `france-lnh` | `…/handball/france/lnh/` | `…/handball/france/starligue/` |
| `denmark-handboldligaen` | `…/handball/denmark/handboldligaen/` | `…/handball/denmark/herre-handbold-ligaen/` |

Two non-obvious traps here:

1. **Localized listing alias ≠ real slug.** The `/results/#handball` page is
   served Italian-localized; its href for the men's EHF Champions League was
   `…/europe/champions-league-uomini/…`, but that slug renders **0 match
   links**. The actual working slug is the un-suffixed `champions-league`.
   Always confirm a slug harvested from the listing by loading
   `<url>results/` and checking for match links — never trust the listing
   href alone.
2. **HTTP 200 is not validation.** Every dead URL above still returned 200
   with a valid-looking `<title>`; only the absence of `eventRow` match
   links revealed they were dead. Off-season leagues legitimately have no
   *upcoming* fixtures, so the canonical validation target is the
   `<league>/results/` sub-page (past matches), exactly what
   `validate_league.py` checks.

Dictionary **keys were intentionally left unchanged** (`france-lnh`,
`denmark-handboldligaen`, `ehf-champions-league`) to preserve backward-compatible
CLI slugs and existing tests — only the URL *values* were corrected. No
`LEAGUE_SEASON_ALIASES` entries were added because handball historic seasons
were not in scope; if a user reports historic-season breakage, add aliases
per the fix pattern above.

Validate handball slugs with `uv run python scripts/validate_league.py -s
handball --all` (the project's hardened `PlaywrightManager` gets past the
anti-bot layer that blocks a vanilla browser).

**Reference commits/PRs:** `708a8cf` (Brazil Serie A → Betano), PR #43
(Czech / Mexico / Serbia aliases). Handball URL audit: this change.

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

## §7 — Regional OddsPortal mirrors: domain swap, not a different site

**Severity:** Low (informational) — relevant when extending `--base-url` support
or debugging region-specific bookmaker availability.

OddsPortal serves region-specific mirror domains (e.g. `centroquote.it` for
Italy, `cuotasahora.com` for LATAM/Spanish, `oddsagora.com.br` for Brazil) whose
DOM **structure** (selectors, JSON shapes, `data-testid`s) is identical to
`www.oddsportal.com`; only the scheme + host differ. The motivation is that the
bookmaker set exposed per region varies — users previously worked around this
with a VPN (issue #45).

### …but the structure is identical, the *labels* are not (issue #70)

The page structure matches, but all **user-visible text is localized** per
domain — and the language is **server-bound to the domain**, not switchable via
`Accept-Language`, the Playwright context `locale`, or a `lang` cookie/localStorage
(all verified ineffective on `cuotasahora.com`; `html lang="es"` is forced). The
English-only mirror *is* `www.oddsportal.com`, which is exactly the domain a LATAM
user gets geo-redirected away from.

This breaks any code that matches DOM elements by their **visible text**. The
market-tab navigator (`MarketTabNavigator`) matched tab labels against English
strings (`"Over/Under"`), so on the Spanish mirror the `Más/Menos de` /
`Hándicap asiático` / `Ambos equipos marcan` tabs were never found → the market
silently returned `[]`.

**The fix — match the language-independent market code, not the label.** When a
market tab is clicked, OddsPortal writes a stable, language-independent code into
the URL fragment: `#<match_id>:<code>;<scope>` (e.g. `#4pPp9nn3:over-under;2`).
These codes are identical across every mirror **and** across sports. Verified
live: `1X2`, `home-away`, `over-under`, `ah`, `eh`, `bts`, `cs`, `double`, `dnb`
(plus out-of-scope `ht-ft`, `odd-even`). The map lives in
`OddsPortalSelectors.MARKET_TAB_CODES`, keyed by the English `main_market` label.

`MarketTabNavigator.navigate_to_tab` keeps label matching as the fast path
(unchanged on `.com`) and, only when it fails, falls back to `_navigate_by_code`:
click each tab, read `location.hash`, match the code. The `More` overflow button
is opened via `data-testid="more-button"` (its text is localized too: `Más`),
and its expanded state is detected via the `.drop-arrow-hide` arrow element, not
text. `NavigationManager.wait_for_market_switch` likewise confirms the active
market via the URL code first, falling back to label text.

Two non-obvious traps for the next contributor:

1. **You cannot navigate markets by setting `location.hash` directly.** The SPA's
   market router ignores a synthetic `hashchange` for market switching (unlike the
   match-id resync trick in §1 / issue #60). Only a real tab **click** drives it —
   which is why the fallback clicks tabs and *reads* the resulting code rather than
   writing it.
2. **`main_market="Handicap"` (rugby) has no matching tab.** OddsPortal only has
   `Asian Handicap`/`European Handicap`. The old substring match resolved
   `"Handicap"` to the first tab containing it (`Asian Handicap`); the code map
   pins `"Handicap" → "ah"` to preserve that exact behaviour. Revisit if rugby
   handicap is ever meant to be European (`eh`).

### The label trap recurs below the tab — submarket lines (issue #70 follow-up)

Fixing the **tab** is not enough: the same localization breaks the **submarket
line** selection one layer down, and the URL-code trick does *not* apply there
(submarket lines carry no per-line code in the fragment). After #70 the tab
resolved correctly but `over_under` markets still returned `[]` on
`cuotasahora.com`, because `NavigationManager.select_specific_market` matched the
full English label `"Over/Under +20.5 Games"` and the row reads
`"Más/Menos de +20.5 Games"`.

**The fix — match the untranslated tail, not the full label.** Only the
main-market *prefix* is translated (`Over/Under` → `Más/Menos de`); the numeric
line and axis word (`+20.5 Games`, `-2.5 Sets`) are byte-identical across mirrors
(verified: the `Games`/`Sets` suffix stays English on the Spanish mirror).
`OddsPortalSelectors.submarket_match_text(specific_market, main_market)` strips
the English `main_market` prefix and the substring matcher in
`PageScroller.scroll_until_visible_and_click_parent` finds the row on every
mirror. The retained leading `+`/`-`/`:` is load-bearing: it stops `+2.5` from
matching `+20.5`. The submarket option box also carries a language-independent
`data-testid="<code>-collapsed-option-box"` (e.g. `over-under-collapsed-option-box`)
if a future change needs to scope by market rather than by label tail.

### The period selector has the same trap — fixed via the fragment scope code

The `kickoff-events-nav` tabs (`Full Time` → `Final del partido`, `1st Set` →
`1er set`) expose only `data-testid="sub-nav-active-tab"`/`sub-nav-inactive-tab`
— **no per-period code on the tab itself** — so the old label-based
`SelectionManager`/`PERIOD_STRATEGY` logged `period target element not found for:
Full Time` on every mirror. Non-fatal for the default period (Full Time is the
active tab and the extractor ignores the return), but a **non-default** period
(e.g. tennis `1st Set`) silently fell back to Full Time data — a §1-class
silent-wrong-data risk.

**The fix — select by the fragment scope, like the market tab.** The active
period is the `;<scope>` segment of the fragment (`…:over-under;2`). Scope ids
are **global OddsPortal period ids, identical across mirrors and across sports**
(verified live: `FullTime`=2 on football/tennis/baseball, `1st Set`=12 on `.com`
*and* `cuotasahora.com`, football `1st Half`=3 / `2nd Half`=4, baseball
`FT incl. OT`=1). `PeriodSelector.select_by_scope` reads the current scope
(no click if already correct — the common Full-Time case) else clicks each period
tab and re-reads the scope until it matches. It returns `True` **only on an exact
scope match**, so a wrong period is never silently selected; `None` when the
`(sport, period)` scope is not in the verified map, which makes the extractor
fall back to the old label matching (unchanged on `.com`).

Two traps when extending the scope map (`OddsPortalSelectors.PERIOD_SCOPE_CODES_*`):

1. **Scope is keyed by period *concept*, not by enum name.** Baseball's
   `FirstHalf` enum renders as `1st Inning` = scope **17**, not the football half
   = scope 3. So `FirstHalf`/`SecondHalf`/`FirstSet` live in the per-sport map,
   not the universal one. Only `FullTime`=2 is universal (verified across three
   disparate sports).
2. **Only add scopes you verify live.** Do not guess the remaining ones
   (quarters, later sets, hockey periods, `FT incl. OT` on basketball/amfootball):
   the `/results/` listings lazy-load match links, so capture from an in-play or
   finished match detail page and read `location.hash` after clicking each tab.
   Unverified periods stay on the label fallback — correct on `.com`, no silent
   wrong data on mirrors thanks to the exact-match rule.

### The odds-history tooltip header has the same trap (issue #70 follow-up)

`--odds-history` hovers each bookmaker odds cell to open the "Odds movement"
tooltip, then reads `h3 → parentElement` to capture the modal. The old selector
`h3:text('Odds movement')` matched the **localized** header (`$t("odds_movement")`
in the Vue bundle), so on `cuotasahora.com` the `wait_for_selector` timed out:
no modal captured → **both odds history and opening odds silently empty**, while
closing odds (parsed from the main row, hover-independent) still came through.
This is the reported "only closing odds" symptom.

**The fix — match the header by its stable class, not its text.**
`ODDS_MOVEMENT_HEADER = "h3.font-semibold.uppercase.leading-6"`. Verified in the
`Event-*.js` bundle: the match page contains exactly two `<h3>` elements, both
the odds-movement tooltip header (bookmaker variant `HistoryBackAndLayTooltip`
and exchange variant), sharing class `text-sm font-semibold uppercase leading-6
text-[#2F2F2F]`. No section-title `<h3>` exists, so the class match is unambiguous
and only one tooltip is shown per hover.

**The dates inside the tooltip are *not* localized** — do not "fix" the
`"%d %b, %H:%M"` parse. The client renders them via `phpJsDate("d M, H:i", …)`,
whose month/day arrays are hardcoded English in the bundle, so `"10 Jun, 14:30"`
is emitted on every mirror regardless of `html lang`.

### How `--base-url` works

`--base-url` accepts a mirror root (e.g. `https://www.centroquote.it`) and
swaps the scheme + host at runtime via `rebase_url()` in `url_builder.py`. The
100+ league URLs stored in `sport_league_constants.py` remain absolute
`.com` addresses (canonical default); the swap is applied just before each
network request. No changes to league constants are needed when targeting a
mirror.

### Detection signal

If results return 0 bookmakers or fewer bookmakers than expected from a given
region, and the scraper is pointing at `www.oddsportal.com`, the user may be
hitting the `.com` bookmaker set instead of their regional set. The fix is
`--base-url <regional-mirror>` paired with `--locale`/`--timezone` matching
that region.

### HAR-replay limitation

Integration tests under `tests/integration/` record against `www.oddsportal.com`
and replay against `.com` URLs only. `--base-url` is therefore a **live-only
feature**: there are no HAR fixtures for any mirror domain, and running the
integration suite in replay mode will not exercise this code path. Do not add
HAR fixtures for mirror domains — replay them as `.com` and test the
`rebase_url` logic unit-level instead.

### Fix pattern / when extending this feature

1. Validate the mirror's page structure manually before adding support for a
   new domain: confirm CSS selectors and JSON shapes match `.com`.
2. Keep `sport_league_constants.py` `.com`-canonical — never store mirror URLs
   there.
3. Unit-test `rebase_url()` in `test_url_builder.py` for any new URL shape
   (trailing slash, path-only, etc.).

**Reference:** PR implementing `--base-url` (`feat/regional-base-url`), issue #45.

---

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
(`/volleyball/h2h/<t1-id>/<t2-id>/#<hash>`). Unlike the NBA/real-madrid-barcelona
H2H pages, a *historic finished* volleyball match captured via `--match-link`
+ `--season` replays cleanly from its HAR (no runtime-cache-buster redirect
chain), so `tests/integration/test_volleyball.py` runs deterministically in
default HAR-replay mode — it is NOT marked `live_only`. The H2H fragment is
still why a fixture must be *captured* (not hand-written): only a real capture
resolves the fragment to the intended match.

---

## §9 — Listing pages return started/finished matches under "upcoming"

**Severity:** Medium — `upcoming -d <today>` historically returned matches
already in play or finished, polluting the "upcoming" semantics promised by
the CLI (GitHub issue #58, point 2).

`/matches/<sport>/<date>/` returns *every* match scheduled for that day, in
all three states: upcoming, live, finished. **Per-row state is split across
two elements** — there is no single source-of-truth field:

| Match state | `[data-testid="time-item"]` `<p>` text | `[data-testid="game-status-box"]` text |
|---|---|---|
| Upcoming (not yet started) | `HH:MM` (kick-off clock) | **empty** (`<!---->` placeholders only) |
| Live | period marker (`1S`, `4S`, `HT`, `1H`, `65'`) — note the live `<p>` carries class `text-red-dark` | **empty** (still!) |
| Finished | unchanged kick-off clock (or empty) | `FinishedFIN` |
| Postponed / Cancelled | unchanged kick-off clock | `Postponed` / `Canceled` |

### Why both signals are needed

The first wrong hypothesis to avoid: **`game-status-box` does not flip when
a match goes live.** It only flips at FT (or for postponed/cancelled). During
play, OddsPortal mutates `time-item` instead (the kick-off clock is replaced
by a period marker, with `text-red-dark` class for visual emphasis).

A status-box-only check passes live matches through — exactly the bug
verified on volleyball 2026-05-20 (live `4S` and `1S` rows leaked through
until the helper was extended to also check `time-item`).

### Detection signal

- `game-status-box` non-empty → finished/postponed/cancelled → drop.
- `time-item` `<p>` text does **not** match `^\d{1,2}:\d{2}$` → live → drop.
- Both empty/match `HH:MM` → upcoming → keep.

Don't match on the `text-red-dark` Tailwind class for live state — class
names churn on React rebuilds (see §1 / set_odds_format). Match on the
text content shape, which is what OddsPortal renders for users to read.

### Fix pattern

`base_scraper._row_has_started(row)` combines both checks. Wired through
`extract_match_links(skip_started=…)` → `scrape_upcoming(include_started=…)`
→ CLI `--include-started/--no-include-started` (default no = filter out
started/finished). The helper is fail-safe: a row missing both elements
(future DOM rename) is kept rather than silently dropped.

### When OddsPortal renames either testid

The filter degrades open: missing testid → helper returns False → started
rows leak through. Symptom mirrors the original issue #58 bug. Recapture
listing HAR fixtures and inspect the DOM before touching the helper.

---

## §10 — Listing date-headers are grouped in the browser's timezone

**Severity:** Medium — `upcoming -l <league> -d <date>` silently returned 0
matches for South American leagues (GitHub issue #58 follow-up).

OddsPortal renders the `[data-testid="date-header"]` groups on a league
listing page using the **browser context's timezone** — not UTC, and not the
competition's local time. A match kicks off at a single instant, but which
date-header it appears under depends entirely on the timezone the page was
rendered in.

This bites cross-timezone competitions hardest: a Copa Libertadores match
kicking off 21:30 in Argentina (UTC-3) renders under the **22 May** header in
`Europe/Paris` (UTC+2). A user requesting `-d 20260521` then gets 0 results —
the match is real and upcoming, just filed under the next calendar day.

### Detection signal

- The browser timezone is whatever `--timezone` / `OH_TIMEZONE` sets, and it
  **falls back to the host system timezone** when unset — *not* UTC.
- Two timezones must agree or dates drift: the one the browser **renders** in,
  and the one `_parse_date_header` **resolves** "Today"/"Tomorrow" in. When
  `timezone_id` is unset, `PlaywrightManager.initialize` resolves the effective
  browser timezone (`Intl.DateTimeFormat().resolvedOptions().timeZone`) so both
  sides share one zone.
- Symptom: `upcoming -l … -d …` returns 0 matches while the league page
  visibly has fixtures. `extract_match_links` emits a WARNING listing the date
  headers actually seen when a filter matches nothing.

### Fix pattern

- Keep parsing and rendering on the same zone (resolve the effective tz once,
  at context creation).
- There is no "competition-local date" the scraper can infer — the user
  expresses intent with `--timezone`. Don't try to guess it per league.

### References

- `core/playwright_manager.py` — effective-timezone resolution.
- `base_scraper._parse_date_header` / `_resolved_browser_timezone`.
- GitHub issue #58 follow-up.

---

## §11 — Multi-proxy contexts each need their own warm-up (odds format + cookie consent are per-`BrowserContext`)

**Severity:** High — silently wrong odds values, not a crash or empty result.

Odds format (`Decimal Odds` vs `Fractional`/`American`) and cookie-consent
acknowledgement are **`BrowserContext`-scoped state** on OddsPortal, not
domain-wide. The single-proxy flow sets both once, at startup, before any
match is scraped. Multi-proxy rotation breaks that assumption: each
`--proxy-url` gets **its own** `BrowserContext` (Playwright configures a
proxy at context-creation time, not per-request), so a context that is
never warmed renders match pages in OddsPortal's default (non-decimal) odds
format — and odds values parsed from it are silently wrong, with no
exception raised.

### Detection signal

- Symptom: with `--proxy-url` passed more than once, some scraped matches
  have odds values off by a format conversion (e.g. fractional `5/2`
  parsed as if it were decimal `2.5`, or vice versa) while others from the
  same run are correct.
- No parsing exception is raised — the DOM is well-formed, just in the
  wrong format, so extraction "succeeds" with corrupted numbers.
- Only reproduces with 2+ proxies; single-proxy (or no-proxy) runs warm
  the one context they use at startup and never hit this.

### Fix pattern

`base_scraper._warm_proxy_contexts()` navigates each non-default proxy
context to `ODDSPORTAL_BASE_URL`, dismisses the cookie banner
(`CookieDismisser.dismiss`), then calls `set_odds_format` — once per
context, before that context scrapes any match. It's called from
`extract_match_odds` before match links are dispatched round-robin across
the proxy pool, and tracks already-warmed contexts in `_warmed_proxy_keys`
so each proxy is only warmed once per run. Any future per-context setup
(locale-dependent state, new format/consent flags) must go through this
same warm-once-per-context path — don't assume a page inherits state from
another context on the same proxy pool.

### References

- `core/base_scraper.py` — `_warm_proxy_contexts`, `_warmed_proxy_keys`.
- `core/playwright_manager.py` — `non_default_context_keys`,
  `new_page_on_key` (one `BrowserContext` per proxy).
- `core/browser/cookies.py` — `CookieDismisser`.

---

## §12 — OddsPortal match pages expose no average odds to scrape

**Severity:** Medium — kills any "average odds" feature idea before it starts; must be discovered before implementation, not during.

There is no "Average" or "Highest" aggregate row anywhere in a rendered
OddsPortal match-detail page. Verified three ways on 2026-07-06:

1. Live render of a current match (desktop viewport, cookie dismissed,
   fully scrolled) — the string "average" appears nowhere in the DOM.
2. HAR replay of two captured markets (1X2 + Over/Under) — same result.
3. The `Odds.vue` bundle (`build/assets/Odds-*.js`) does declare
   `oddsAvgOdds`/`oddsMaxOdds` props, but their render path only fires for
   listing `pageName`s (`inplay-live`, `tournament-next-matches`,
   `outrights`) — never the match/event page.

On the tested line (Over/Under +0.5), the **collapsed submarket row was
observed to be the HIGHEST odds across bookmakers, not the average** — the
collapsed "under" odd (9.50) equalled the bookmaker maximum, not the mean
(8.12). Reading that row (what `--preview-only` does) yields best odds,
not an average, at least on the tested line.

The README and docstrings previously described `--preview-only` as an
"average odds" mode — that was inaccurate and has been corrected to
"best/highest odds" wording (see `README.md`'s Advanced Options table and
the `preview_submarkets_only` docstrings in `base_scraper.py` /
`odds_portal_market_extractor.py`).

The odds feed (`/match-event/*.dat`) is also a dead end for this: it's an
encrypted base64 blob decrypted client-side, so no average can be read
from the raw response either.

### Detection signal

- A feature request asks for "average odds" or "average line" and the
  instinct is to find a DOM node or feed field to scrape for it.
- Grepping rendered match-page HTML/JSON for "average"/"avg" comes back
  empty, or a `oddsAvgOdds` prop is found in the bundle but never reached
  from an event page's `pageName`.

### Implication

An "average odds" feature must **compute the mean from the per-bookmaker
rows the scraper already parses** — there is nothing labeled "average" to
scrape on match pages. This is why the average-odds half of the
umbrella/average-odds feature was dropped after a feasibility spike; only
the umbrella market tokens (`over_under`, `asian_handicap` expanding to all
rendered lines) shipped. See issue #71.

---

## §13 — Community Top Predictions: parse the DOM, not the AJAX feed; community data is pre-match only

**Severity:** Medium — the obvious data sources are either encrypted or absent, and the visible percentages are not authoritative.

The `community` command scrapes the Top Predictions page
(`/predictions/#sport/<sport>/`). Several instincts lead nowhere here; record
them before the next contributor re-discovers each one.

### The AJAX feed is a dead end — parse the rendered DOM

The Top Predictions page and the community homepage widgets are fed by
`ajax-topPredictions/<sport>/` and `ajax-top-predictions/homepage/`, whose
payloads are obfuscated and decoded client-side by `lscompressor.min.js`. Do
not try to read the XHR. Parse the rendered DOM instead: the community pages
reuse the same `data-testid` vocabulary as match pages (`game-row`,
`event-participants`, `odd-container-default`, `prediction-container`,
`betting-tip-header`, `sport-country-league-item`).

### Sport switching is fragment-routed — the scraper needs a sport guard

The page switches sport via the URL fragment. Direct fragment navigation is
**not guaranteed** to load the requested sport for non-default sports (the SPA
may keep serving the default sport's rows). The scraper therefore drops any row
whose `match_url` path does not start with the requested sport slug — a §1-class
guard against silently mislabeling one sport's picks as another's. Note
`ice-hockey` maps to the site slug `hockey` in that path check.

### Match pages: `pageVar` holds raw vote counts, but it is null on finished matches

Each match page embeds a `var pageVar` JSON blob whose
`predictionData.communityData` holds **raw per-outcome vote counts for every
market without any tab click** (keys of the form
`E-<eventId>_<bettingTypeId>_<scopeId>_?_<handicap>`). Two traps:

1. `communityData` is `null` on **finished** matches — OddsPortal drops
   community data once a match ends. This is why the feature is pre-match only:
   there is no way to backfill; build longitudinal datasets by scraping while
   matches are upcoming.
2. The visible `user-predictions-row` percentages can **lag** `pageVar` by a
   server-cache snapshot (they come from different caches; observed 11/16/74 in
   the row vs 10/15/75 in `pageVar` on the same page load). Neither is "wrong";
   don't assert the two agree.

### Percentages are rounded — never assert an exact 100 total

Community vote percentages are rounded and may sum to 99–101. Never assert an
exact 100 total.

### Community date tokens use a `/` + trailing-comma form base_scraper rejects

Non-today community rows carry date tokens like `19/Jul,` (slash separator,
trailing comma) which `base_scraper._parse_date_header` does **not** accept. The
community parser normalizes the token locally before delegating to
`_parse_date_header`. Unparseable kickoffs yield `kickoff = None` (the raw label
is kept in `kickoff_text`), so a token-format drift degrades to a null kickoff,
not a crash.

### Match-page community votes: raw counts exist, but outcome labels don't

`--match-url` reuses the same `pageVar.predictionData.communityData = {total, count,
group}` blob described above, but here the labels matter and most of them are
unrecoverable. `total[E-<eventId>_<bettingTypeId>_<scopeId>_<col>_<handicap>]` is the
per-market vote total; `group[encodedOutcomeId] -> marketKey` and
`count[encodedOutcomeId] -> votes` give the per-outcome split. **Outcome labels are NOT
recoverable**: the `encodedOutcomeId`s are `lscompressor`-obfuscated and only appear
inside the React hydration `data` blob, never on the odds cells themselves. Betting-type
and scope ids are canonical and stable (`community_constants.py`: `1`=1X2, `2`=O/U,
`4`=DoubleChance, `5`=AsianHandicap, `6`=DNB, `13`=BTTS; scope `2`=FT, `3`=1H, `4`=2H).
`communityData` is `null` on finished matches, same as the Top Predictions page; teams,
`isStarted`, `isFinished`, and `startDate` come from the `#react-event-header` `data`
JSON instead. `[data-testid="match-facts-prediction"]` holds the one aggregate pick that
does come with a label.

### User profiles: header always renders, stats/predictions only when public

`/profile/<username>/` always renders the header (`username`, `user-roi`, `member-info`
with `Profile Privacy: Public|Private`), even for a private profile. The monthly stats
table (siblings of `stats-table-header-line`, **not** inside `stats-table-box`) and the
predictions list render only when the profile is public: **most profiles are private**,
so `--user` frequently returns header-only records with empty stats/predictions. Public
profiles are hard to find via the ROI leaderboard (every sampled leader was private); the
`/users/` list and `community/feed` are mostly private too. Profile prediction rows reuse
match-row testids (`game-row` etc.) but have **no `betting-tip-header`**: outcomes are
positional, with no 1/X/2 labels, and there is no reliable per-row win/loss signal, so
use the stats table for win/loss instead of trying to infer it per prediction.

### References

- `core/community/` — parser + scraper/runner.
- `cli/commands/community.py` — the `community` command.
- `tests/integration/test_community_predictions.py` — HAR-replay coverage.

---

## §14 (Cricket): one market, one period, and no per-bookmaker odds on detail pages

**Severity:** Medium (sets expectations: cricket scraping yields metadata only, and shapes the integration test).

Cricket on OddsPortal exposes a single market tab: `Home/Away`, a 2-way match
winner with no draw outcome, for limited-overs formats (T20, ODI). There is no
`Over/Under` tab or any other market. Registered market key is `home_away`.

There is also a single period tab, labelled `FT including OT` (OddsPortal
reuses the same label baseball uses, even though cricket has no overtime
concept). It maps to `CricketPeriod.FULL_INCLUDING_OT`, scope code 1 (same
scope id as baseball's `FT incl. OT`, per §7's period-scope map).

### No per-bookmaker odds on cricket detail pages (any region)

Cricket match-detail pages carry no per-bookmaker odds table. `home_away_market`
comes back empty on every match tested, including marquee internationals
(verified: England vs India, One Day International) and through a non-France
proxy. The detail page itself renders "No odds available for this match". The
listing pages show an aggregate teaser price per side, but that value is not
exposed in the per-bookmaker detail table the scraper reads. Scraping cricket
therefore yields correct match metadata (teams, league, score, result) with an
empty odds list, which is what `tests/integration/test_cricket.py` asserts.

Separately, from a France IP the cricket results LISTINGS are geo-filtered to
empty ("no odds available from your selected bookmakers") while the market and
period tabs still render. A non-France IP restores the listings, so the HAR
fixture had to be proxy-captured, but a non-France IP does not restore the
missing detail odds because those do not exist for cricket in any region.

### Detection signal

- A cricket scrape returns populated metadata (teams, league) with an empty
  `home_away_market`. This is expected for cricket, not a parsing bug.
- The detail page shows "No odds available for this match" regardless of the
  scraping IP's geography.

### Open item: multi-day formats may expose a `1X2` market (unverified)

Multi-day formats (Test matches, Sheffield Shield, Ford Ranger Cup) can end in
a draw, which limited-overs cricket cannot, so they likely expose a separate
`1X2`-style market (win/draw/win). This is unverified (checked during the
off-season with the France geo-filter also hiding odds) and is deferred as a
follow-up rather than guessed at. See the "Follow-up" section of the cricket
support task notes for the drop-in shape (`CricketMarket.ONE_X_TWO`) once this
is confirmed live.

### References

- `utils/sport_market_constants.py`: `CricketMarket.HOME_AWAY`.
- `utils/period_constants.py`: `CricketPeriod.FULL_INCLUDING_OT`.

---

## Adding a new gotcha

When a fix lands that exposes an OddsPortal-specific behaviour an agent
couldn't deduce by reading the code, add it here. Criteria:

- The pattern has appeared **more than once**, OR is likely to recur
  (sponsor changes, SPA-vs-SSR mismatches, anti-bot tweaks, format
  variations across geographies).
- The fix is non-obvious from the code alone: the reader needs to know
  *why* the defensive check exists, not just that it does.
- The signal is describable: a future agent must be able to recognize the
  shape of the problem in new code.

Do **not** add: one-off bugs, fixes whose context is fully captured in the
commit message, generic Python/Playwright tips, or anything already covered
in `CLAUDE.md`.
