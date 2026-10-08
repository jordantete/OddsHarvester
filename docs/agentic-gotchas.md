# OddsPortal Scraping Gotchas

Reusable patterns extracted from past bugs. Read this **before** working on
anything that touches DOM parsing, league configuration, CLI options, or
Playwright config — these traps are not deducible from the code alone because
they describe *OddsPortal server behaviour*, not our code.

Each gotcha is structured as: **the trap → the detection signal → the fix
pattern → references**.

The gotchas, by section:

- **§1**: SSR ships stale or phantom data (historical since the 2026-08 redesign).
- **§2**: Client-side rendering silently truncates listings and URLs.
- **§3**: Per-bookmaker and per-geography data formats need fallback chains.
- **§4**: League slugs change over time; the season selector is the slug map.
- **§5**: CLI options are normalized at the lowest layer, never in the CLI.
- **§6**: Anti-bot detection: tell the symptom from the cause.
- **§7**: Regional mirrors and `--base-url`: the same structure, localized labels.
- **§8**: Volleyball O/U and AH each split into a Sets axis and a Points axis.
- **§9**: Listings return started and finished matches under "upcoming".
- **§10**: Listing dates and shown times follow the browser's timezone.
- **§11**: Each proxy context needs its own warm-up.
- **§12**: Match pages expose no average odds.
- **§13**: Community pages: the rendered DOM only, and a finished match can keep its votes.
- **§14**: Cricket: one market and one period.
- **§15**: The season/league product cannot pre-filter invalid pairs.
- **§16**: In-play pages: their own URL space, end-of-match signal and replay limit.
- **§17**: A listing can answer 200 with zero rows.
- **§18**: Struck-through odds are a real state.
- **§19**: The 2026-08 redesign: H2H links everywhere, hash-driven match views.
- **§20**: The data-testid attributes are gone; anchor on hrefs, semantics and text shape.
- **§21**: Team pages: the id is the only key, and the data is in the flight payload.
- **§22**: A listing keeps reflowing after `goto`; the row count is not final.
- **§23**: HTTP 429 hides inside a page that loads.
- **§24**: An unknown league path answers 200.
- **§25**: A sport's site path is not always its CLI name.
- **§26**: A market or period switch resets the bookies filter to Classic.
- **§27**: A market switch can show another market's odds under the requested tab.
- **§28**: An invisible anti-bot trap row clones a match link with invented team ids.
- **§29**: The search runs in two steps, and its data is in the flight payload.

---

## §1 — SSR ships stale or phantom data that contradicts the requested URL

> **2026-08 redesign note (§19):** the SSR no longer renders any match content
> and `react-event-header` is gone, so the case-a/case-b discrimination and the
> `eventData.id` resync below are historical. The lesson that survives: SSR
> payloads (now the JSON-LD) still describe the *next upcoming* matchup, never
> trust them for the fragment match.

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
| **c.** League listings include duplicate "phantom" event rows hidden in CSS, whose href points to a corrupted slug that 301-redirects to an unrelated match | `<tr style="left:-9999px">` (also `display:none`, `visibility:hidden`, `top:-9999px`) on `/results/` listings | Random unrelated matches scraped from a league listing | `f7c6ee4` — `_is_offscreen_row` helper, skip before processing (now `OddsPortalSelectors.is_hidden`, which also reads ancestors, §28) |

**Case b fails intermittently, and that is not a structure change.** The SPA
swap is a client-side render race: on a full Turkish Süper Lig season (issue
#83, 306 matches) 262 URLs tripped the fragment mismatch, 239 recovered via the
case-a DOM path and 23 timed out in the resync. Re-running the same URLs
succeeds. On that log the resync itself succeeded 0 times out of 23 attempts;
the other 239 mismatches recovered through the case-a DOM path without ever
entering the resync, so recovery on retry comes from landing on the case-a
path on a later page load, not from the resync eventually working. So a
resync timeout must be raised as a **retryable** error
(`H2HFragmentResolutionError`), never returned as `None` and never typed
`NAVIGATION`; instead it is typed `HEADER_NOT_FOUND`, since that type is
absent from `PROXY_ATTRIBUTABLE_ERROR_TYPES` in `core/retry.py`, so the
failure never counts against the proxy that served a perfectly good page.
Leagues where every team pair has one alphabetically normalized H2H URL, with
`#fragment` as the only discriminator between the two legs, hit this on
nearly every match.

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
  check the element and its ancestors for a `style` with `left:-9999px`,
  `top:-9999px`, `display:none` or `visibility:hidden`, and for the anti-bot
  trap attribute (`OddsPortalSelectors.is_hidden`, §28). These are not
  user-visible and should be skipped.
- **DOM vs JSON** — when both exist for the same field (team names, date,
  scores), prefer the DOM (hrefs, semantics and text shape since the testids
  went, §20) and use JSON only as fallback. The DOM is what the user sees; the embedded JSON may be stale.

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

### The season selector is the authoritative slug map (Sept 2026)

Don't guess season slugs one URL at a time. The season dropdown on
`<league>/results/` links every season the site has, each href carrying the
slug that season actually lives under. One page load per league gives the
whole history, renames included:

```bash
uv run python scripts/validate_league.py -s football -l spain-laliga --dump-seasons
```

Sweeping the 95 configured football leagues that way (issue #78) found **44
with an unrecorded rename**, and two `LEAGUE_SEASON_ALIASES` entries that were
off by one season (`hungary-nb-i`, `slovakia-nike-liga`) because they had been
written from a guess rather than from the selector. The whole table was
rebuilt from that sweep. Four leagues also had a stale *base* URL
(`brazil-serie-b`, `world-cup`, `argentina-liga-profesional`,
`chile-primera-division`): their old slug still renders as a landing page, so
nothing looked broken, while every per-season URL under it was wrong.

Two details when reading the dump: filter the hrefs to the league's own
country segment (the page also links to unrelated competitions), and expect
the ranges to be contiguous, one slug per era.

### A dead season URL can redirect to the current fixtures (Sept 2026)

Worse than a not-found page, and the reason the guard in `collect_historic_links`
exists. `mexico/liga-mx-2012-2013/results/` (right league, season that lives
under the old `primera-division` slug) **redirects to
`mexico/liga-mx/`**, the current fixtures listing. Before the guard, that run
collected 9 upcoming 2026 matches, stamped them `season: 2012-2013`, reported
`0 listing pages failed` and exited 0. Silent wrong data, not an empty result.

Spain answers the same class of URL with an `Offside — page not found` body
and 0 links, so the behaviour is per league and cannot be assumed either way.
`OddsPortalScraper._assert_season_page_reached` compares the landed
`page.url` path against the requested one after the first `goto` and raises
`PageNotFoundError` when they differ, which surfaces the combo as `error` in
the end-of-run summary. Keep that check ahead of any listing walk: it costs no
request, and §15's "wrong pairs come back empty" is only true once it runs.

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
(Czech / Mexico / Serbia aliases). Handball URL audit: May 2026. Season
selector sweep, the 44 missing aliases and the redirect guard: issue #78.

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
- **HTTP 429 from OddsPortal's rate limit**: a burst of page loads from one
  IP gets requests refused inside pages that still load, which also leaves
  views empty. The run logs `rate limited by OddsPortal` when it catches one;
  see §23.

### Detection signal

The triage rule before touching parsing code:

```
0 event rows + 0 parse errors → suspect anti-bot, NOT parsing
```

Quick checks (in order):

1. Run the same command with `--no-headless` (headed is the default, so
   dropping `--headless` does the same). If you see a Cloudflare challenge or
   a blank page, it's anti-bot.
2. Manually load the same URL in a normal browser from the same IP. If it
   works there but not from the scraper, it's anti-bot, or a change in
   what the scraper's browser sends (below).
3. Read the run's `Browser: Chromium <version>, user agent: <UA>` line, and
   check the `PLAYWRIGHT_BROWSER_ARGS` / `PLAYWRIGHT_BROWSER_ARGS_DOCKER`
   lists (`utils/constants.py`) for divergence between local and Docker.

### Fix pattern

- For new Playwright/browser flags, add them to **both** local and Docker
  arg lists. The Docker list has been the source of multiple regressions
  because it lags behind local.
- Never add a `--disable-features` switch to the arg lists: Chromium reads
  only the last one, and Playwright passes its own list first, so ours would
  replace it. That list changes with Playwright's version (1.63 dropped
  `AcceptCHFrame` and `RenderDocument` and added
  `BlockOriginHeaderModificationOnRedirect`), so it cannot be copied either.
  Until 2026-10 ours dropped it (`ThirdPartyStoragePartitioning` came back
  on); the offline test `tests/integration/test_browser_fingerprint.py`
  checks that Playwright's list still applies.
- When a user reports "scraping returns 0 results", request the output of
  `--no-headless` before assuming a parsing bug.
- Treat anti-bot fixes as urgent: a silent 0-results scrape that succeeds
  is worse than one that errors out, because users don't notice for days.

### What the browser tells the site

No script patches `navigator`: the stealth script, removed in 2026-10,
added tells of its own (an own `webdriver` property, `plugins` as numbers,
a stub `window.chrome`). Every request carries the launched browser's own
user agent with `HeadlessChrome/` renamed `Chrome/` (`headful_user_agent`
in `core/playwright_manager.py`), so its version follows the installed
Playwright and its platform is the host's, like `navigator.platform`;
`--user-agent` replaces it as given. The locale sets `Accept-Language` and
`navigator.languages`, `en-US` without `--locale` (the shell sent no
Accept-Language at all, and full Chromium would follow the host's
language). `navigator.webdriver` is `false` through
`--disable-blink-features=AutomationControlled`.

`--headless` runs launch full Chromium in its new headless mode
(`channel="chromium"`), not Playwright's headless shell, which names
`HeadlessChrome` in `sec-ch-ua` whatever the user agent and has no plugins
and no `window.chrome`. The full build takes about 2.2 to 2.7 times the
shell's memory (summed RSS on macOS, one context: 724 MiB against 270 with
one page, 980 against 440 with three).

Still visible: `sec-ch-ua` names `Chromium`, not `Google Chrome`; screen,
inner and outer window sizes all equal the viewport; WebGL is SwiftShader
or absent on a host without a GPU.
OddsPortal's first-party scripts read none of these (34 HARs, 2026-10), and
its rate limit keys on IP and volume (§23).

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

Since the 2026-08 redesign the fragment drives the tab bar itself (§19).
`MarketTabNavigator.navigate_to_tab` (`core/browser/market_navigation.py`)
tries two paths in order:

1. **Hash.** `_navigate_by_hash` reads the event id and the current `;<scope>`
   from the page URL and runs `HASH_SWITCH_JS`, which marks the current tabs
   (`data-oh-stale`), writes `#<id>:<code>;<scope>` into `location.hash` and
   dispatches a `HashChangeEvent`. The SPA tears the match view down and
   renders it again 0.1 to 0.4 s later, in one commit (tab bar, active tab,
   odds table; probe of 2026-10-01), and the period survives the market
   switch. `switch_view` waits for that view: unmarked tabs and the requested
   code and scope in the hash, at most 5.5 s, the three sleeps it replaced; at
   the cap it logs a warning and the path goes on with the URL check and the
   tab bar. A switch to the code and scope the URL already holds is skipped:
   writing the same hash renders nothing again (an umbrella's lines all sit on
   the tab already shown). The path is skipped on in-play pages
   (`/inplay-odds/`), which route their own codes (`O/U`, not `over-under`),
   and for a market missing from `MARKET_TAB_CODES`.
2. **Click.** `_click_tab_by_text` clicks the first `li.tab-item` whose text
   contains the English market name, waits for the bold (active) tab to carry
   that name, at most 5.5 s, then checks it. This path reads labels, so on a
   localized mirror only the hash path can reach a market.

One trap when extending the code map: **`main_market="Handicap"` (rugby) has no
matching tab.** OddsPortal only has `Asian Handicap`/`European Handicap`. The
old substring match resolved `"Handicap"` to the first tab containing it
(`Asian Handicap`); the code map pins `"Handicap" → "ah"` to preserve that exact
behaviour. Revisit if rugby handicap is ever meant to be European (`eh`).

### The label trap recurs below the tab — submarket lines (issue #70 follow-up)

Fixing the **tab** is not enough: the same localization breaks the **submarket
line** selection one layer down, and the URL-code trick does *not* apply there
(submarket lines carry no per-line code in the fragment). After #70 the tab
resolved correctly but `over_under` markets still returned `[]` on
`cuotasahora.com`, because `NavigationManager.select_specific_market` matched the
full English label `"Over/Under +20.5 Games"` and the row reads
`"Más/Menos de +20.5 Games"`.

**The fix: match the untranslated line, not the full label.** Only the
main-market *prefix* is translated (`Over/Under` → `Más/Menos de`); the line
(`+20.5`) is byte-identical across mirrors.
`OddsPortalSelectors.submarket_match_text(specific_market, main_market)` strips
the English `main_market` prefix, and `PageScroller.click_line_row` (called by
`NavigationManager.select_specific_market`) keeps a row only when the last
whitespace tokens of one of its label spans are the line
(`OddsPortalSelectors.line_label_matches`, mirrored in the page by
`_LINE_ROW_JS`, which waits for the row at most 20 s; nothing scrolls, since a
row below the fold is already in the DOM). A clicked row renders its bookmaker
rows in a nested table of the `<tr>` that follows it, 0.2 to 0.3 s after the
click; the read waits for them, and closing the row waits for them to go,
each at most 2 s. A substring match is not
enough: lines render in ascending order, so `-1` found `Asian Handicap -1.75`
first (the same for `-2`, `-3`, `-4`), and a missing `+2` would have opened
`+2.25` (probe of 2026-09-29). Two rules come with it:

- A span holding only a bare number never matches: every line row also carries
  its bookmaker count as a lone number span (`0`), which would pass for the
  `Asian Handicap 0` line.
- When two different rows end with the line, the selection fails with
  `Line '<line>' matches N different rows; refusing to pick one.` and the market
  comes back empty. ATP Beijing showed `+1.5` twice in its Asian Handicap list,
  a sets row and a games row, neither labelled (§8).

The umbrella tokens (`over_under`, `asian_handicap`) read their lines the same
way: `line_name_to_token` takes the last whitespace token of the rendered name
as the line, so `Más/Menos de +2.5` and `Over/Under +2.5` both give
`over_under_2_5`. It used to require the English prefix, and `-m over_under`
found no line at all on `cuotasahora.com`.

### The period selector has the same trap — fixed via the fragment scope code

The `kickoff-events-nav` tabs (`Full Time` → `Final del partido`, `1st Set` →
`1er set`) expose only `data-testid="sub-nav-active-tab"`/`sub-nav-inactive-tab`
— **no per-period code on the tab itself** — so the old label-based
`SelectionManager`/`PERIOD_STRATEGY` logged `period target element not found for:
Full Time` on every mirror. Non-fatal for the default period (Full Time is the
active tab and the extractor ignores the return), but a **non-default** period
(e.g. tennis `1st Set`) silently fell back to Full Time data — a §1-class
silent-wrong-data risk.

**The fix: select by the fragment scope, like the market tab, then check the
screen.** The active period is the `;<scope>` segment of the fragment
(`…:over-under;2`). Scope ids are **global OddsPortal period ids, identical
across mirrors and across sports**. Clicking every period tab of one match per
sport on 2026-09-29 gave:

| Scope | Tab | Internal period |
|---|---|---|
| 1 | FT including OT | `FullIncludingOT` |
| 2 | Full Time | `FullTime` |
| 3 | 1st Half | `FirstHalf` |
| 4 | 2nd Half | `SecondHalf` |
| 5 to 7 | 1st to 3rd Period | `FirstPeriod` to `ThirdPeriod` |
| 8 to 11 | 1st to 4th Quarter | `FirstQuarter` to `FourthQuarter` |
| 12 to 16 | 1st to 5th Set | `FirstSet` to `FifthSet` |
| 17 | 1st Inning (baseball) | none |

`OddsPortalSelectors.PERIOD_SCOPE_CODES_UNIVERSAL` holds codes 1 to 16 for every
sport; no period of ours maps to 17. `PeriodSelector.select_by_scope`
(`core/browser/selection.py`) rewrites the fragment to `#<id>:<code>;<target>`
with the same `HASH_SWITCH_JS` as the market switch, unless the target is
already there, then re-reads the scope.

**The URL is not enough for a period the match lacks.** Forcing a scope whose
tab the match does not have (NFL `;4`, baseball `;2`) puts the scope in the URL
while the page keeps its first tab, the sport's default period, active with the
same odds, so a URL check alone returned the default period's odds under the
requested label. For any period other than the sport's default
(`SportPeriodRegistry.get_default_period`), `select_by_scope` also reads the
period bar: the sub-nav button group after the bookies filter (both are
`div.no-scrollbar` groups of `main button[type='button']`, identical on `.com`
and `cuotasahora.com`). It returns `True` when the bold tab (`font-weight: 700`)
is not the bar's first tab, or, when the first tab is bold, after clicking tab 2
and then tab 1 the URL carries the target scope again (a tab click writes that
tab's own scope; probe of 2026-09-30 on baseball `1X2`, whose first tab is Full
Time, and `Home/Away`, whose first tab is FT including OT, identical on
`cuotasahora.com`). The clicks also replace the market code in the URL with the
page's own label (`Home/Away`, `Local/Visitante`), which only the scope parse
reads afterwards. It reads no label itself, so it holds on mirrors. The default
period keeps the URL check alone (the collector's path). After a `False`, the
extractor still tries the English tab label, which finds no tab for a period
the match lacks and fails on mirrors, and then returns the market empty.
`select_by_scope` also returns `None` on `/inplay-odds/` pages, like the market
navigator, so the period is chosen by its tab label there.

One trap when extending this: **the scope is keyed by period concept and is the
same on every sport.** Baseball shows `1st Half` (scope 3) and `1st Inning`
(scope 17) side by side; our `FirstHalf` is the half, as everywhere else (an
earlier version of this section said baseball `FirstHalf` rendered as
`1st Inning`; the probe of 2026-09-29 disproved it). Give a new period its code
by clicking its tab on a live, in-play or finished match detail page and
reading `location.hash`; the `/results/` listings lazy-load their match links.

### The odds-history tooltip header has the same trap (issue #70 follow-up)

`--odds-history` hovers each bookmaker odds cell to open the "Odds movement"
tooltip, then reads `h3 → parentElement` to capture the modal. The tooltip
renders in two steps (probe of 2026-10-01, 9 hovers out of 9): about 0.2 s
after the hover the header stands over a loading state (an `svg.animate-spin`,
a "Loading" label and the opening odds), and only after the
`/proxy/match-event-history/` response (0.25 to 0.5 s) does it hold the history
columns. The hover sometimes fires that request twice and goes back to the
spinner in between. A wait on the header alone reads the loading state, so
`OddsHistoryExtractor` waits for the response, then for the header's parent
without `.animate-spin` (a language-independent signal), and takes its HTML in
the same evaluation, within one 2 s cap. The old selector
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
tabs each hold two independent submarket families: sets and points. In May 2026
a suffix word told them apart (`Over/Under +3.5 Sets`, `Over/Under +184.5 Points`).
On 2026-09-29 the rows carry no such word: Perugia - Piacenza showed `+3.5`,
`+4.5` and `+184.5` in one O/U list and `+2.5` twice in the AH list. Tennis is
the same (`Games` / `Sets` gone): ATP Beijing mixed the sets line `+2.5` with the
games lines `+21` to `+24`, and showed `+1.5` twice in AH.

So the registry builds labels without the axis word, and an axis's ladder can
show a value its own enum never lists, so a value inside another axis's range
may be that axis's row. `SportMarketRegistry.ambiguous_markets(sport)` computes,
per `(main_market, line_axis)`, each market whose value falls within `[min, max]`
of another axis, and `scrape_markets` returns each one empty with `Market
'<token>' refused: its line may also be a <axis> line, and the page does not
tell them apart.`:

| Sport | Refused markets |
|---|---|
| Volleyball | AH sets and points `-2.5`, `-1.5`, `+1.5`, `+2.5` |
| Tennis | AH sets all lines `-2.5` to `+2.5`; AH games `-2.5`, `+2.5`; O/U sets `6.5` to `10.5`; O/U games `6.5` to `10.5` including the whole lines `7` to `10` |

The rule compares value ranges, not equal labels, because an axis's ladder
shows values its enum does not list: the Gea - Machac games AH ladder of
2026-09-29 read `-1.5` to `+3.5`, inside the sets range. Lines outside the
other axis's range (volleyball O/U sets stop at `4.5`, points start at `150.5`)
are matched on their exact value (§7). If the page brings the axis word back,
restore it in `sport_market_registry.py`; the refusals then disappear on their
own.

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

> **2026-09 note (§20):** the two testids below are gone. A row's state now
> shows in one place, the row's first column: `HH:MM` while the match is
> pending, a status or period marker once it started (`Finished`, `5S`). The
> table and the "both signals" reasoning record the 2026-05 DOM.

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

`listing._row_has_started(row)` reads the row's first column
(`_row_status_cell_text`): any text that is not `HH:MM` means started. Wired through
`extract_match_rows(skip_started=…)` → `collect_upcoming_links(include_started=…)`
→ CLI `--include-started/--no-include-started` (default no = filter out
started/finished). The helper is fail-safe: a row whose first column is empty
(future DOM rename) is kept rather than silently dropped.

### When the first column changes shape

The filter degrades open: an empty first column → helper returns False → started
rows leak through. Symptom mirrors the original issue #58 bug. Recapture
listing HAR fixtures and inspect the DOM before touching the helper.

---

## §10 — Listing date-headers are grouped in the browser's timezone

**Severity:** Medium — `upcoming -l <league> -d <date>` silently returned 0
matches for South American leagues (GitHub issue #58 follow-up).

OddsPortal renders the date-header groups on a league
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
  visibly has fixtures. `extract_match_rows` emits a WARNING listing the date
  headers actually seen when a filter matches nothing.

### Fix pattern

- Keep parsing and rendering on the same zone (resolve the effective tz once,
  at context creation).
- There is no "competition-local date" the scraper can infer — the user
  expresses intent with `--timezone`. Don't try to guess it per league.

### Times render at the browser's current UTC offset (seen 2026-09-29)

The page applies the browser's UTC offset of the scrape moment to every time
it shows (match header, listing rows, odds-history modal), not the offset in
force on the date shown. Djokovic - Sinner (26 Jan 2024, kickoff 03:45 UTC)
scraped on 2026-09-30 showed 04:45 under `Europe/Paris` and `Europe/London`,
and 03:45 under `UTC`. The site changed between 2026-09-02 and 2026-09-25:
HARs captured on 2026-09-02 render each date at its own offset, HARs captured
from 2026-09-25 on render at the replay machine's current offset.

The rule the scraper applies (`utils/page_time.py`): a naive time `t` shown on
the page is the UTC instant `t - page_utc_offset(zone)`, where the offset is
the browser zone's offset at the scrape moment. `match_date`, a listing row's
`kickoff_utc` and the `--kickoff-within-hours` window (its cutoff is computed
in UTC) use it. An odds-history time takes its year from the kickoff as the
page shows it, then goes to UTC and back to the zone's local time on its own
date, still emitted naive. Reading a shown time with the zone's rules for its
date (`replace(tzinfo=ZoneInfo(...))`) is one hour off for any date on the
other side of a DST switch from the scrape. In the autumn fold two instants an
hour apart come out as the same naive local time (01:30 twice on
2026-10-25 in London); that is a limit of naive output, not a parsing error.

Community pages follow the same rule. A top-predictions or profile row's
`kickoff` (`2026-01-04T17:30`) and the `kickoff` of `community --match-url`
(`Sunday, 04 Jan 2026, 17:30`) hold the kickoff's local time in the browser
zone on its own date (`row_helpers.extract_datetime_and_market`,
`match_community_parser._kickoff`); a row's `kickoff_text` stays the page's
text. Before the fix, Man City - Chelsea (17:30 UK time) came out `18:30`
under `Europe/London` (2026-09-30). The match header says `Today`, `Tomorrow`
or `Yesterday` in place of the weekday around the day it is read, so the
parser writes the weekday back.

Known limit: date headers are the page's own grouping, rendered at the same
current offset. A match within an hour of midnight on the other side of a DST
switch can sit under the neighbouring date header, so `-d` can keep or drop it
one day off.

Integration replays and captures still run the browser in `UTC`
(`tests/integration/helpers/cli_runner.py`, `capture.py`): HARs captured
before 2026-09-25 carry the old rendering, which the parser would read an hour
off in a DST zone. The odds-history replay runs in `Europe/London`; its HAR
dates from 2026-09-25, so its golden holds the true times in any season.
The community replays and their `SPECIAL_FIXTURES` captures pass
`--timezone UTC` as well. A community row dated within a day of the day the
page is read says `Yest.`, `Today` or `Tomorr.` (replayed under a fixed
browser clock, 2026-09-30), and its year is inferred from that day, so the
top-predictions replay leaves kickoff out of its compare (kickoff_text is
compared). The row parser reads `Yest.` and `Tomorr.` as `Yesterday` and
`Tomorrow`, which `_parse_date_header` resolves against the browser zone's
current date.

### References

- `core/playwright_manager.py` — effective-timezone resolution.
- `listing._parse_date_header`; `utils/page_time.py` (`page_utc_offset`,
  `shown_to_utc`, `shown_to_local`, `local_to_shown`).
- `upcoming --links-only`: a null `kickoff_utc` under the default
  `--no-include-started` has two causes. Usual: the date header failed to
  parse, the same signal as the WARNING `extract_match_rows` already emits.
  Silent: if the kickoff leaves the row's first column, `_row_has_started`
  keeps a row whose first column is then empty (see §9), and that row's
  kickoff comes back null with no log output at all.
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

`base_scraper._warm_proxy_contexts()` runs `_warm_up_page`, the routine every
page is warmed through, on each non-default proxy context: it navigates to the
run's base URL (`--base-url`, else `ODDSPORTAL_BASE_URL`), dismisses the cookie banner (`CookieDismisser.dismiss`), then calls
`set_odds_format`, once per context, before that context scrapes any
match. Strictness is decided from the domain the page actually landed on
after `goto`, not the one requested: whatever was asked for, a page that
lands on `www.oddsportal.com` gets the strict call, where a timeout, any
other error, or the wanted format missing from the dropdown raises, and
a warm-up that fails twice removes that proxy from the rotation
(`blacklist_proxy`), since a context left on another odds format would
corrupt every match it scrapes. A proxy can be geo-redirected to a regional mirror even when the
canonical domain was requested, and a page that lands anywhere else only
gets the non-strict call, which logs, because the dropdown labels are
localized (§7) and the English match cannot find them there. Listing and
match pages keep the non-strict call, which only logs. It's called from
`extract_match_odds` before match links are dispatched round-robin across
the proxy pool, and tracks already-warmed contexts in `_warmed_proxy_keys`
so each proxy is only warmed once per run. Any future per-context setup
(locale-dependent state, new format/consent flags) must go through this
same warm-once-per-context path — don't assume a page inherits state from
another context on the same proxy pool.

A strict warm-up that times out often hits a context already on decimal
odds, so a failed warm-up is tried once more on the same context
(`PROXY_WARM_UP_ATTEMPTS = 2`, `utils/constants.py`) before the proxy
leaves the run.

### References

- `core/base_scraper.py` — `_warm_proxy_contexts`, `_warmed_proxy_keys`.
- `core/playwright_manager.py` — `non_default_context_keys`,
  `new_page_on_key` (one `BrowserContext` per proxy).
- `core/browser/cookies.py` — `CookieDismisser`.
- `core/browser/warm_up.py`: `warm_up_page` (strictness by the host the page
  landed on) and `set_odds_format`.

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

## §13: Community pages are parsed from the rendered DOM, and a finished match can keep its votes

**Severity:** Medium (the data feeds are obfuscated, a match page shows the votes of one market only, and the old "pre-match only" rule no longer holds).

The `community` command reads three pages: Top Predictions
(`/community/predictions/#sport/<sport>/`, `--sport`), a user profile
(`/profile/<username>/`, `--user`) and a match page (`--match-url`). Several
instincts lead nowhere here; record them before the next contributor
re-discovers each one.

### The AJAX feed is a dead end — parse the rendered DOM

The Top Predictions page and the community homepage widgets are fed by
`ajax-topPredictions/<sport>/` and `ajax-top-predictions/homepage/`, whose
payloads are obfuscated and decoded client-side by `lscompressor.min.js`. Do
not try to read the XHR. Parse the rendered DOM instead. Since the testids
went (§20), a row is found from its match link (`a[href*="/h2h/"]` in the
content root): its block is the nearest ancestor holding outcome columns, each
column a label header (`COMMUNITY_OUTCOME_LABEL`), the odds
(`COMMUNITY_ODD_CELL`), the vote percentage as text and, on a profile, the
pick marker (`COMMUNITY_PICK_MARKER`) on the outcome the user bet on
(`row_helpers.row_of`, `outcome_columns`). A row's country and league are the
section's breadcrumb links, told apart by path depth
(`top_predictions_parser._parse_breadcrumb`).

### Sport switching is fragment-routed — the scraper needs a sport guard

The page switches sport via the URL fragment. Direct fragment navigation is
**not guaranteed** to load the requested sport for non-default sports (the SPA
may keep serving the default sport's rows). The scraper therefore drops any row
whose `match_url` path does not start with the requested sport slug — a §1-class
guard against silently mislabeling one sport's picks as another's. Note
`ice-hockey` maps to the site slug `hockey` in that path check.

### Match pages: one market's votes, read from the DOM, finished matches included

The match page's `pageVar.predictionData.communityData` (raw counts for every
market) went with the 2026-08 redesign (§19), and with it the betting-type and
scope ids, the `#react-event-header` JSON and the one labelled aggregate pick.
`--match-url` now hydrates the page like any match page (`hydrate_match_view`)
and reads the market view on screen (`match_community_parser`):

- the market from the active tab (`MARKET_TAB_ACTIVE`), and the period from the
  bold sub-nav button (`Full Time`, `1st Half` or `2nd Half`, else `Full Time`);
- the votes from the User Predictions row, the first block beside the odds
  table holding two or more `N%` texts (`_vote_percentages`);
- the outcome labels from the odds table's middle header cells
  (`_outcome_labels`), so a 1X2 view gives `1`, `X`, `2`.

A record therefore holds one market, the one the page shows on load (1X2 for a
football URL ending in `#<id>`, as in both goldens), as rounded percentages; the
votes of another market would need a market switch the command does not make.
`is_prematch` is false once the header carries the live marker (`.result-live`)
or the participants show scores (`_has_started`).

A finished match can keep its votes. The `match_community_fulham_chelsea` golden
is Fulham - Chelsea of 24 Aug 2026, scraped on 2026-09-29: `is_prematch: false`
and a 7/9/84 split. When a page shows no vote row, `markets` is empty, the
scraper logs a warning and the CLI exits 1; the code does not tell a finished
match without votes from a match nobody has voted on yet.

### Percentages are rounded — never assert an exact 100 total

Community vote percentages are rounded and may sum to 99–101. Never assert an
exact 100 total.

### Community date tokens use a `/` + trailing-comma form `_parse_date_header` rejects

Non-today community rows carry date tokens like `19/Jul,` (slash separator,
trailing comma) which `listing._parse_date_header` does **not** accept. The
community parser normalizes the token locally before delegating to
`_parse_date_header`. Unparseable kickoffs yield `kickoff = None` (the raw label
is kept in `kickoff_text`), so a token-format drift degrades to a null kickoff,
not a crash.

### User profiles: header always renders, stats/predictions only when public

`/profile/<username>/` always renders the header (the username in `main h1`,
then the ROI, `Member since:`, `Country:` and `Profile Privacy: Public|Private`
texts), even for a private profile. The monthly stats table (the page's only
`<table>`) and the predictions list render only when the profile is public:
**most profiles are private**, so `--user` frequently returns header-only
records with empty stats/predictions. Public profiles are hard to find via the
ROI leaderboard (every sampled leader was private); the `/users/` list and
`community/feed` are mostly private too. The predictions sit behind the Feed
tab, which the scraper clicks (§19). Prediction rows reuse the community row
structure, and the record keeps their outcomes positional (`odds`,
`community_pct`, `picked`, no label); there is no reliable per-row win/loss
signal, so use the stats table for win/loss instead of trying to infer it per
prediction.

### References

- `core/community/` — parser + scraper/runner.
- `cli/commands/community.py` — the `community` command.
- `tests/integration/test_community_predictions.py` — HAR-replay coverage.
- `tests/integration/test_community_extensions.py`: the profile and the two
  match pages, goldens in `tests/integration/fixtures/community/`.

---

## §14 (Cricket): one market and one period

**Severity:** Medium (sets expectations: one market and one period; the per-bookmaker odds came back with the 2026-08 redesign, §19).

Cricket on OddsPortal exposes a single market tab: `Home/Away`, a 2-way match
winner with no draw outcome, for limited-overs formats (T20, ODI). There is no
`Over/Under` tab or any other market. Registered market key is `home_away`.

There is also a single period tab, labelled `FT including OT` (OddsPortal
reuses the same label baseball uses, even though cricket has no overtime
concept). It maps to `CricketPeriod.FULL_INCLUDING_OT`, scope code 1 (same
scope id as baseball's `FT incl. OT`, per §7's period-scope map).

### No per-bookmaker odds on cricket detail pages (any region)

**Superseded by the 2026-08 redesign (§19):** redesigned cricket detail pages
DO render a per-bookmaker odds table (verified live 2026-08-24; the ODI
integration fixture now asserts non-empty odds). Kept for history:

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

- Before the 2026-08 redesign, a cricket scrape returned populated metadata
  with an empty `home_away_market`, and the page said "No odds available for
  this match" whatever the IP. Since the redesign the page renders a
  per-bookmaker table (the ODI fixture holds three bookmakers), so an empty
  `home_away_market` on a cricket match gets the same triage as on any other
  sport.

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

## §15: The season/league cartesian product cannot pre-filter invalid pairs, because HTTP 200 is not validation (§4)

**Severity:** Low (informational). Explains a design decision so a future contributor does not "fix" it into a network validation step.

`historic --season` accepts a comma-separated list and is scraped as the
cartesian product with `--league`, league outer and season inner order
preserved in the output; listings run up to `--concurrency` at once
(issue #78, `_scrape_combos` in `core/scraper_app.py`). Some leagues
changed season format mid-history
(Russia moved from calendar-year to autumn-spring format in 2011-2012),
so a bulk request spanning that boundary has to pass both formats and
accept that the wrong-format pairs return nothing.

The scraper does not try to pre-filter which `(league, season)` pairs are
valid before scraping them. It cannot: §4 established this behaviour for
dead league-slug URLs, and by analogy the same pattern holds for wrong
season suffixes. A dead season URL on OddsPortal returns HTTP 200 with a
valid-looking `<title>`, and only the absence of match links
reveals it is dead. There is no cheap request (a HEAD, a status check)
that tells a wrong-format season apart from a right one; the only signal
is doing the actual listing scrape and counting links. A pre-filtering pass
would cost the same network round trip as just scraping the combo, for no
benefit.

Because a zero-link result is the expected shape for an invalid pairing, not
a scraper malfunction, a combo returning zero results is reported in the
end-of-run summary table (`format_combo_summary` in
`cli/commands/_output.py`) as a zero-count row, not as an error, and does
not fail the run while another combo returns data; when every combo returns
nothing, the run exits 1, as any run that scraped no match does. A season that OddsPortal redirects away (§4) is
also reported as a zero-count row. Only combos whose listing failed (network
error, parse exception, unknown league) count toward the "errored" total;
they make the run exit 1 once the other combos' data is written, and they
are the ones worth re-running.

### Detection signal

- A bulk `--season` run against a league that changed format shows some
  combos with a `0` count in the end-of-run table. That is expected, not a
  bug, when the run intentionally passes both old- and new-format seasons.
- Don't add a pre-scrape validation step for `(league, season)` pairs. It
  can't be cheaper than the scrape itself (§4), and it would only duplicate
  the zero-link signal the scraper already produces.

### Fix pattern (i.e., how not to "fix" this)

- Keep treating zero links as a normal, non-error outcome. If a future
  report conflates "zero results" with "the scraper is broken," point back
  to this entry and §4.
- A cheap index does exist for the *slug* half of the problem: the season
  selector on `<league>/results/` (§4). It says which seasons the site has and
  under which slug, so it removes renames as a cause of empty combos. It does
  not remove the brute force: the selector is read from the same page the walk
  already loads, and a season the selector lists can still hold no odds.
- A wrong pair does not always come back empty. Some redirect to the league's
  current fixtures, which is why `collect_historic_links` fails a season whose landed
  URL no longer matches the requested one (§4).

### References

- §4's "HTTP 200 is not validation" point.
- `core/scraper_app.py`: `_scrape_combos`.
- `cli/commands/_scrape.py`: `scrape_and_report`, the exit codes.
- `cli/commands/_output.py`: `format_combo_summary`.
- Issue #78.

---

## §16 — In-play (live) pages are a separate URL space with their own end-of-match signal

**Severity:** High — treating the in-play view like a normal match page yields
pre-match odds mixed with live ones, and finished matches silently recorded as
live.

OddsPortal serves live betting from a dedicated URL space, not from the pages
the `upcoming` / `historic` commands already know:

| What | URL |
|---|---|
| Matches in play now | `/inplay-odds/live-now/<sport>/`, which the site redirects to `/inplay-odds/?sport=<sport>` (§19) |
| Matches that will have live odds | `/inplay-odds/scheduled/<sport>/` (the scraper never loads it) |
| One match's live view | `/<sport>/h2h/<home>/<away>/inplay-odds/#<id>` |

On a match page, **"Pre-match Odds" and "In-Play Odds" are two distinct tabs
over the same event**. They must never be mixed in one record: the pre-match
tab keeps serving its own bookmaker table while the match is running.

### The live-now listing as the code reads it

A row is a match link whose href carries the in-play segment
(`/<sport>/h2h/<home>/<away>/inplay-odds/#<id>`), so listing hrefs need no
rewriting. The same match can appear twice in the DOM, so rows are deduped on
the href. The href carries no league segment, so `--league` cannot filter on
it: `extract_live_match_links` walks the match links and the section-header
league links (`/<sport>/<country>/<league>/`, `_is_league_link`) in document
order, gives each row the league of the header link before it, and keeps the
rows whose league path is the requested league's.

### The end-of-match signal: `.result-live` and its parent

The header's live block (period, running score, partial result) is the parent
of the `.result-live` pulse element (`LIVE_INFO_MARKER`, which replaced
`data-testid="live-info"`, §20). The observations of what it does at full time
disagree: on 2026-07-20 (tennis) and 2026-08-24 (§19) the block stayed and its
period marker became a terminal string (`Final result`, which can arrive as one
chunk with the score), and on 2026-09-02 (§20) it was gone after the match.
`_parse_live_info` handles both, and returns "not live" when:

- there is no `.result-live` element;
- or the block's period chunk starts with a terminal marker (`final result`,
  `finished`, `postponed`, `canceled`, `cancelled`, `abandoned`, `retired`,
  `walkover`, compared by prefix).

A live visit that reads "not live" returns no record and counts as neither
scraped nor failed (`extract_match_odds`), so a match that ended between the
listing and its visit leaves the snapshot.

Text chunks in this container are separated with **non-breaking spaces**
(`Final\u00a0result`), so normalize `\u00a0` before comparing. The main score
uses a colon (`1:0`), but OddsPortal renders scores with an en-dash elsewhere,
so accept both.

The period marker is sport-specific and must never be parsed as a fixed
vocabulary. It is not even consistent *within* a sport: football alternates
between elapsed minutes (`4'`) and named phases (`Half-time`), both verified
2026-07-20. Also verified: `1st Set` / `2nd Set Tiebreak` (tennis), `9th Inning`
(baseball). Match on shape instead: a chunk of the form `N:N` is the score, the
remaining chunk is the period. Any attempt to enumerate the vocabulary will be
wrong within one sport, let alone across eleven.

`live_period` is that remaining chunk, so it is filled whenever the block shows
one. §19 recorded on 2026-08-24 a page with no period or clock and
`live_period` always None; the code reads the period from the `.result-live`
block and leaves `live_period` None only when the block holds no chunk besides
the score.

### In-play match views are not pre-match views

- They render on load, like every match page (§20). When the view is late,
  `hydrate_match_view` re-routes the bare `#<id>` only: forcing the pre-match
  form `#<id>:1X2;2` can flip the view to Pre-match Odds (§19).
- They use their own hash market codes (`O/U`, not `over-under`), so
  `MarketTabNavigator.navigate_to_tab` skips the hash path on an
  `/inplay-odds/` URL and clicks the tab.
- They have a period bar, below the bookies filter, as pre-match views do (verified 2026-10-08:
  Full Time / 1st Half / 2nd Half in football, FT including OT / 1st Half / quarters in basketball,
  Full Time / sets in tennis). It lists only the periods the shown market offers in play right now:
  the same match had 1st and 2nd Half on 1X2 and no 2nd Half on O/U, and an NBL Home/Away showed no
  period tab at half-time. Its tabs write the pre-match scope ids into the hash (`#<id>:1X2;3`).
- Their data come from `/proxy/feed/live-event/<sport>-<n>-<id>-<market>-<scope>-<hash>.dat`, not from
  `/proxy/match-event/`, so `switch_view` cannot switch them.
- Never write a period scope into an in-play hash. For a period the market lacks, the view requests
  nothing (`H/A;14`, a third set during the first) or another market's data (`O/U;4` served 1X2
  second-half data under the O/U hash, the §27 trap). `PeriodSelector._select_inplay` clicks the bar
  by position instead and reads the scope from the request each click sends; every click sends one,
  a revisited period included. A period click re-renders the bookmaker rows but not the market tabs.
- Their labels can come in another language: from the Helsinki VPS (feed `geo=BG`) the bar read
  `Regulaminowy czas gry (FT)` / `1. połowa` / `2. połowa` in an `en-US` context. Never select by label.
- At half-time (verified 2026-10-08) the live block reads `Half-time 2:1`, the bar keeps all three
  tabs, 1st Half shows the first half's last quotes and 2nd Half shows quotes, both with a payout of
  `-`. A bookmaker can leave a period's quotes frozen: Bets.io's 2nd Half 1X2 still showed its
  half-time prices at 74', payout `-`, which the record carries as `blocked_outcomes`. A period
  snapshot is a price only where its outcomes are not blocked.

### Being in play is not the same as having in-play odds

A match can be visibly live on the sport's daily listing (its row's first
column showing `4'`) and still be absent from the live-now listing. Verified
2026-07-20 on a Kazakh women's league match: the site linked it to its
`/inplay-odds/` view, the live header rendered a period and a score, and the
odds table said **"No odds available for this match"**. The live-now listing is
the set of matches with *bookmaker in-play coverage*, which is much smaller than
the set of matches in play, and smaller again outside peak hours and top
leagues. Scraping the live-now listing is therefore the right entry point; do
not "fix" an empty result by falling back to the general listing, or you will
collect matches that carry no odds at all.

### The page polls itself; the scraper must not

An open in-play page refreshes odds in place via first-party feeds
(`/feed/live-event/*.dat` roughly every 10s, `/feed/postmatch-score/*.dat` every
3-4s) and mutates the DOM without navigating. A snapshot therefore needs exactly
one page load and one parse. Never add a reload loop: repeated refreshes are the
clearest bot signal this feature could send (see §6).

### In-play bookmaker coverage is thin and geo-dependent

A live match commonly exposes 2 to 4 bookmakers where the pre-match tab shows 15
to 20 (observed from a French IP: Betclic.fr, Winamax, Bets.io, Stake.com). A
near-empty in-play odds table is normal, not an extraction failure. Coverage
varies by region, like the Pinnacle case in §3.

The in-play view opens on Classic Bookies, which hides the crypto bookmakers
that carried most live odds for a French IP (§19, 2026-08-24). `live` applies
`--bookies-filter` like the other scrape commands, `all` by default.

### Live pages are ephemeral, so HAR fixtures are capture-once

Once a match finishes, its in-play view is gone for good. A HAR must be captured
while the match runs. Replaying it does *not* bring the live view back, see the
next subsection; the self-discovering live-network test (`--live`) is what
actually exercises this path.

A live HAR is not a frozen instant. The page self-refreshes via first-party
`.dat` feeds, and recording in `record_har_mode="full"` stores every snapshot
that arrived during capture. On replay, timing selects one of them, so
`live_period` and `live_score` are non-deterministic across replays of the same
HAR (a match captured at `Half-time` replayed later as `49'`). Since an in-play
page does not replay at all (next subsection), the live context is checked by
the self-discovering live test instead (`test_live_snapshot_self_discovering`,
run with `--live` and by the health check). It asserts the *shape* of
each record (a UTC scrape timestamp, the `live_period` and `live_score_raw`
keys, no finished match) and never a captured period or score value.

### An in-play page does not replay from a HAR

**Severity:** Medium — costs a day of debugging a "regression" that is a replay
limit, and any future in-play replay fixture will hit it too.

Replaying a live match page from its own HAR renders the **pre-match** variant of
the event header. The live block (then `data-testid="live-info"`, marked by
`.result-live` since §20) never mounts, so the scraper correctly classifies the
match as no longer live and drops the record: the run exits 0 with no output.
The odds tab bar (`Pre-match Odds` / `In-Play Odds`) never renders either,
though a bookmaker table does.

The data is not the problem. The recorded SSR payload carries
`isLive: true`, `realLive: true`, `isFinished: false` and the live text
(`Half-time 0:0 (0:0)`); every recorded request is served; there is no JS error.
The client simply does not mount the in-play view.

Investigated 2026-07-26, five causes ruled out by isolated experiment:

- the 3 requests absent from the HAR (`ajax-getCount/MyBookmarks/`, a header
  icon, analytics) — stubbing them with empty 200s removes every JS error and
  changes nothing;
- the `.dat` feeds — blocking them one at a time and together changes nothing;
- wall-clock — pinning the browser clock to the capture instant with
  `context.clock` changes only the rendered date label;
- a cold session — replaying the full capture journey (homepage first, cookies
  set) changes nothing;
- the URL fragment — present or absent, same result.

The remaining suspect is state the HAR cannot hold (a real-time channel, or
responses served from the browser HTTP cache during capture and therefore never
recorded; `MyBookmarks` is provably in that category). Pre-match H2H fragment
pages had a similar replay limit until the 2026-08 redesign; they replay since
(§19), so the in-play view is the one match view left that a HAR cannot serve.

The live-now listing does replay (`test_live_listing_replays_captured_live_now_page`,
a listing captured on 2026-09-29).

Rechecked 2026-10-08 on the redesigned view: a HAR of a match's second half replayed the live block,
the In-Play Odds tab and the second-half table while the match was still in play, and stopped
replaying once it ended, every request still served from the HAR. The page opens
`wss://oppush-tt2.livesport.eu/WebSocketConnection-Secure`, which a HAR neither records nor serves, so
during a replay it reaches the real network; with it blocked, `.result-live` never mounts, even with
the clock pinned to the capture. The live block most likely comes from that push channel. A replay
test would need its frames recorded and served through `context.route_web_socket`.

Consequence: do not write a replay test that asserts the live header. The one
written for the 2026-07-20 capture was deleted with its HAR in 2026-09: it could
only xfail on replay, and `live_only` would have made it a permanent no-op since
the captured match is over. The 2026-10-08 one, which passed only while its match
was live, went the same way before it was merged.

### References

- `core/url_builder.py`: `get_live_matches_url`, `normalize_inplay_match_url`.
- `core/base_scraper.py`: `extract_live_match_links`, `extract_match_odds` (the ended-match drop).
- `core/listing.py`: `_is_league_link`.
- `core/match_details.py`: `_parse_live_info`.
- `core/odds_portal_scraper.py`: `scrape_live`.
- `core/browser/hydration.py`, `market_navigation.py`, `selection.py`: the
  in-play branches.
- `core/browser/selection.py`: `PeriodSelector._select_inplay`.
- `tests/integration/test_live_snapshot.py`.

---

## §17 — A listing page can answer 200 with zero rendered rows, and silence looks like success

**Severity:** High — a run returns one page of a multi-page season, reports zero
failures, and exits 0. Nothing downstream can detect the gap from the data.

Observed 2026-07-20 on `england-premier-league --season 2022-2023 --links-only`:
50 links instead of 380, `0 listing pages failed`, pagination correctly detecting
8 pages. Intermittent, and it does not reproduce back to back: it appears on cold
or degraded runs, and disappears once the site is answering fast.

### Why zero rows is not an error anywhere in the chain

Three behaviours compose into a silent truncation:

- OddsPortal answers **200 with an empty result set** when it throttles. There is
  no error status to react to (same lesson as §4 and §15).
- `extract_match_rows` (and `extract_live_match_links`) used to wrap its whole
  body in `try/except` and return `[]` on any failure. Since lot 5a a crash
  while reading the rows surfaces instead: a failed listing page (historic), an
  errored combo (upcoming), or a failed live run, so only a page that actually
  renders no rows still reaches the zero-link verdict described below. A
  crashed historic page gets the same single re-fetch as a truncated page
  (below) before it counts as failed.
- The collection loop then counted the page as collected regardless of what came
  back, so `[]` incremented `successful_pages`.

Each piece is defensible alone. Together they turn a blocked page into a
successful one carrying no data.

### Detection signal

Suspect this whenever the collected count is an exact multiple of a page's worth
(50 on results pages) while pagination reported more pages than that. Concretely:
`Pages planned from widget: 8` with `Failed pages: 0` and `Total links found: 50`
in the walk's summary is the fingerprint (before lot 5c-5c the first line read
`Final pages to scrape: [1..8]`).

### The distinction that matters for the fix

Zero links is only contradictory when pagination promised more than one page.
A genuinely empty season has exactly one page and returns zero links, and that is
the documented, expected way to discover an invalid league/season pair (§15). So
the rule is: **more than one page planned and a page yields nothing → that page
failed**; one page planned and it yields nothing → legitimately empty.

Failures raised this way flow into `ErrorType.LISTING_PAGE`, which is distinct
from a per-match failure on purpose: a per-match failure names a URL you can
retry, whereas a lost listing page hides an unknown number of matches that were
never discovered.

### Two hypotheses to skip if this resurfaces

Both were measured and refuted on 2026-07-20, so do not spend time on them again:

- *A race on pagination detection.* Pagination is server-rendered and present at
  `t=0`; a probe sampling `a.pagination-link` every 500ms found all 8 pages
  immediately on every run.
- *Stale page-1 content behind the `#/page/N` fragment.* The fragment never
  reaches the server, so the concern is reasonable, but the SPA swaps the rows
  within ~250ms even with `wait_until="domcontentloaded"`. The page shows no rows
  at all before that, never page 1's rows.

### The same degradation also hits the pagination read (issue #79, 2026-07-27)

Observed on `italy-serie-a --season 2025-2026 --links-only`: one cold run in four
logged `Found 0 pagination links`, planned `[1]`, collected 50 links and reported
`Failed pages: 0`. The other three runs read 8 pages and collected all 380.

The detection signal above cannot match this variant. It keys on
`Final pages to scrape: [1..8]` with 50 links, but here the widget itself read
empty, so only one page was ever planned and the `len(pages_to_scrape) > 1` guard
exempted itself by construction.

Do not re-open the race hypothesis refuted above: the countermeasure is
corroboration across pages, not timing. Two facts make it work, both verified live:

- A results page renders 50 links when full (`RESULTS_PAGE_SIZE`). Serie A
  2025-2026 gave 50 on pages 1-7 and 30 on page 8, totalling 380. A full page
  therefore implies another page exists, whatever the widget says.
- A page past the end (page 9 of 8) renders **zero** rows but still shows a
  pagination widget reporting max 8. So an empty page is only "past the end" when
  the widget on that page corroborates it; otherwise it was degraded.

The widget is now read on every page rather than only the first, which costs no
extra request since the tab is already loaded. When page 1's response is degraded,
page 2's widget still reports 8 and the true count is recovered immediately.

Markup at the time (2026-07): `<a class="pagination-link"
data-number="2">2</a>`, with `Next`/`Prev` sharing the class and carrying **no**
`rel` attribute. The long-standing `:not([rel='next'])` clause in the old selector
was therefore inert; digit filtering is what excludes them. Since the 2026-08
redesign the items are `<button>`s, the current page a `<span>`, inside
`nav.pagination` (`PAGINATION_ITEM`, §19).

### The same silence covers *partial* pages, not just empty ones (issue #78, 2026-08-01)

Reported on a 40-combo run: `Collected 6787 match links (0 listing pages failed)`
while Bundesliga 2024-2025 returned 173 against 308 in every other season of the
same league, Serie A 290 against 380, Ligue 1 219 against 310. Watching the run,
some mid-season listing pages rendered 5 rows instead of 50.

The empty-page guard above did not apply, because the page was not empty. Two
behaviours composed:

- The verdict only tested `link_count == 0` below the frontier, so 5 links out of
  50 read as a normal page: collected, counted in `successful_pages`, absent from
  `failed_pages`, exit code 0.
- `scroll_until_loaded` judges stability **relatively**: the element count
  unchanged across `MAX_SCROLL_ATTEMPTS` polls returns `True`. It holds no
  expected count, so a lazy-load stalled at 5 rows stabilizes at 5 and reports a
  successful scroll. `scroll_ok` therefore cannot discriminate a truncated page
  from a complete one, and any guard built on it would have missed this.

The invariant that does work is positional, not behavioural: **below the frontier
the widget has promised a later page exists, so this page is not the last and must
be full**. Fullness alone decides there; `scroll_ok` stays out of it. At or beyond
the frontier the existing rule stands, since the last page is legitimately short.

A page ruled failed is now fetched once more before being written off
(`LISTING_PAGE_RETRY_ATTEMPTS`). None of the three existing retry layers covers
this: `retry_with_backoff` only fires inside an `except` and only on
`TRANSIENT_ERROR_KEYWORDS`, and a truncated page answers 200 and raises nothing.
The combo-level retry would also be the wrong grain, since it replays the whole
season to recover one page.

Residual hole, accepted: if the widget read is *also* degraded on page 1
(`frontier == 1`) and page 1 is truncated, nothing corroborates, and a truncated
page 1 is indistinguishable from a genuinely small single-page league. No signal
exists to separate them; the re-fetch is what covers it in practice, since a
second attempt usually restores both the widget and the rows.

### When investigating, do not hammer the site

The truncation is triggered by degradation, so the instinct is to run the scrape
repeatedly until it fails. That induces the throttling it is meant to observe and
buries the original condition: five consecutive 8-page scrapes in seven minutes
produced a run where six pages failed outright and one took 17 minutes. Reproduce
with spaced cold runs, and prefer a unit test over live repetition.

---

## §18 — Struck-through odds are a real state; `odds-status-indicator` is not

**Severity:** Medium — the state is invisible to text-only parsing, and the obvious neighbouring signal means something else entirely.

OddsPortal renders a bookmaker's odds with a strikethrough when that price is no
longer on offer. The marker is a `line-through` class on the odds node inside the
cell, driven by a per-outcome boolean from the decrypted feed:

```js
// build/assets/Event-*.js
(a(), n("p", {key: 1, class: T(["odds-text", {"line-through": !g.active}])}, v(_e(te)), 3))
// and, when the bookmaker has a betslip link:
n("a", {class: T(["odds-link underline", {"line-through": !g.active}]), ...})
// active is fed straight from the feed, indexed per bookmaker AND per outcome:
active: r[y].act[b]
```

`OddsParser.parse_market_odds` reads cells with `get_text(strip=True)`, which drops
the class, so a struck-through price used to be indistinguishable from a live one.
It now probes each cell with `OddsPortalSelectors.ODDS_BLOCKED_SELECTOR` and emits a
`blocked_outcomes` list on the row (key omitted when empty, odds values untouched).

Match on the class, not on `p.odds-text` / `a.odds-link`: the bundle picks between
those two elements based on `window.innerWidth >= 1150` and on whether a betslip
link exists for that bookmaker. Both are runtime variables the scraper does not
control.

The probe (`select_one`) is descendant-only, matching against whatever is inside the
odds cell matched by `ODD_CELL_CSS`. If OddsPortal ever moved `line-through`
onto the cell element itself rather than a child, detection would silently return
nothing — if blocked odds stop showing up, check the class's target element first.

On a multi-value cell (e.g. Betfair back/lay, two prices in one cell) the flag is
any-of: either sub-value struck through flags the whole outcome. Text extraction on
such cells is already lossy on its own — the two prices concatenate (e.g.
`1.601.62`) — pre-existing behaviour, out of scope here.

### Two traps

**A bookmaker with no odds is not a blocked bookmaker.** The placeholder row is
built with `active: !1`, but it renders through a separate branch emitting `" - "`
with no `line-through` class. Reading the class only ever flags cells holding a
real value.

**`odds-status-indicator` is a false friend.** Each row also carries a 6px coloured
bar (`data-testid="odds-status-indicator"`) fed by a different field, `status`/`st`:
`1 = FRESH ODDS`, `2 = DELAYED ODDS`, `3 = OLD ODDS`, forced to 3 once the match has
started or finished. That is odds *freshness*, not availability — all seven rows of
a finished match carried it with zero struck-through cells. Never read it as a
blocking signal.

### Detection signal

- A feature request mentions "blocked", "suspended" or "crossed-out" odds, and the
  instinct is to diff consecutive scrape runs to infer it.
- Odds parsing is being changed and only the cell's text is being read.

### Finding a live example

It is rare on well-covered fixtures and easy to conclude, wrongly, that it does not
exist. Two facts, both measured on 2026-07-29:

- Seven hand-checked pages (finished, upcoming and live football, live tennis) gave
  zero hits. A scripted sweep of lower-profile league listings hit one within
  minutes — Albania Superliga.
- Geography is a weak lever. A French residential IP is served seven bookmakers, a
  datacenter IP a geo-generic panel of about nine, measured across ten rendering
  geographies for the odds-evolution collector. More bookmakers is not what makes
  the state appear.

Browser-extension automation is the wrong tool for such a sweep: Chrome throttles
timers in a hidden tab and any long loop stalls. Drive the project's own Playwright
instead.

---

## §19 — The 2026-08 frontend redesign: data-testid DOM, H2H links everywhere, hash-driven match views

**Severity:** Critical — every command returned zero data overnight (issue #85);
this section records the new invariants the whole scraper is built on.

Around 2026-08-10 OddsPortal shipped a full frontend redesign. Old selector
generations died at once, and several long-standing behaviours flipped:

### What changed (all verified live 2026-08-24)

- **Listing rows** (upcoming and `/results/`): `div[class*='eventRow']` is gone;
  rows are `[data-testid='game-row']`. Date headers are **siblings** of the row
  groups (inside a `secondary-header` element), no longer children of the first
  row — `extract_match_rows` walks headers and rows interleaved in document
  order.
- **Match links**: every listing row links to an H2H fragment URL
  (`/<sport>/h2h/<home>/<away>/#<eventId>`). The old per-league match URLs
  return **404** (this killed all pre-redesign integration fixture URLs).
- **Pagination**: `a.pagination-link` is gone; digits are `<button>`s (current
  page a `<span>`) inside `nav.pagination`, whose parent stays `display:none`
  until the listing is scrolled to the bottom (read `text_content`, not
  `inner_text`). The page fragment is now **`#page/N`** — the old `#/page/N`
  is silently ignored and renders page 1 (a silent-truncation trap, cf. §17).
- **Match pages**: SSR renders **no match content** — only an H2H landing
  ("Select a match from the listings … `#MHaHJHqA:1X2;2`"). `#react-event-header`
  and its embedded JSON no longer exist; the event id appears nowhere in the
  DOM. The SSR JSON-LD (`SportsEvent`) describes the **next upcoming** meeting
  of the two teams — same stale-upcoming trap as §1b — so venue data is only
  trusted when its startDate matches the DOM date.
- **Hash-driven match view**: content renders only for the full fragment form
  `#<id>:<marketCode>;<scope>`, and **only after an in-page hashchange** — a
  direct page load with the full hash stays on the landing skeleton. The nudge
  (bare `#<id>`, then the full form + a dispatched `HashChangeEvent`) can fire
  before the SPA has booted, so `_hydrate_match_view` retries it; hydration
  complete = `game-time-item` rendered (since §20: the market tabs,
  `main li.tab-item`). Market and period switching are pure
  hash rewrites (`MARKET_TAB_CODES` codes, `;<scope>` period ids — both were
  already language-independent, §7).
- **Because the SPA fetches the match by the fragment id, the rendered DOM is
  always the requested match.** The §1a/§1b SSR-vs-DOM discrimination and
  eventData.id resync machinery are obsolete (annotated in §1); the failure
  mode left is "never hydrated", raised as a retryable
  `H2HFragmentResolutionError` typed HEADER_NOT_FOUND (proxy-neutral).
- **Odds are a real `<table>`**: one leaf `<tr>` per bookmaker — name in
  `[data-testid='outrights-expanded-bookmaker-name']`, prices in
  `odd-container` / `odd-container-winning` cells, payout in
  `payout-container`. Collapsed submarket line rows use
  **`odd-container-default`** cells and carry a decorative `<img alt="arrow">`
  that the name-fallback chain happily returns — filtering odds cells to
  `odd-container(-winning)` exactly is what keeps line rows out of bookmaker
  parsing. Peripheral rows (`my-coupon-row`, `user-predictions-row`,
  `odds-alert-row`) and the `betting-exchanges-section` (Back/Lay prices) sit
  in the same tables and must be skipped. Expanded submarkets nest a full
  bookmaker table inside a following `<tr>` — only leaf `<tr>`s (no nested
  `tr`) are rows.
  The odds-history hover follows the same rule (`LEAF_BOOKMAKER_ROW_CSS`):
  up to 0.15 it matched the wrapper row too and gave the first bookmaker of an
  expanded submarket every bookmaker's history blocks.
- **Sub-nav tabs** (`sub-nav-active-tab`/`sub-nav-inactive-tab`) carry both the
  bookies filter (All/Classic/Crypto Bookies) and the period tabs;
  `bookies-filter-nav` and `kickoff-events-nav` containers are gone.
- **live-info persists after full time** with a "Final result …" text that can
  arrive as a single chunk — end-of-match detection matches terminal markers
  by prefix (updates §16's assumption that live-info disappears).
- **Cricket now has per-bookmaker odds** (supersedes §14's empty-market rule).
- A **Login modal** (`[data-testid='modal']`, close button
  `button[aria-label='Close']`) can block rendering on cold profiles;
  `_dismiss_login_modal` runs before hydration.
- `/matches/<sport>/YYYYMMDD/` 301-redirects to `/<sport>/YYYY-MM-DD/` and
  `/inplay-odds/live-now/<sport>/` to `/inplay-odds/?sport=<sport>` — old URLs
  still work via redirect.
- **Data regressions**: `match_info` (eventData.staticInfo) has no DOM
  equivalent and is always None; venue trio only survives on matches whose
  JSON-LD date matches (in practice: the next upcoming meeting).

### Detection signal

Sudden across-the-board "Found 0 event rows" / empty markets with valid pages
loading in a real browser, while `[data-testid='game-row']` counts are non-zero
where the old selector finds nothing. Distinguish from anti-bot (§6): a block
zeroes *both* selector generations.

### Community and in-play specifics (resolved 2026-08-24, same rework)

- **Community moved**: `/predictions/` is 404; Top Predictions live at
  `/community/predictions/#sport/<sport>/` with the same testids except that
  `betting-tip-header` cells now sit *inside* each `game-row`, and
  `participant-name` is a data-testid (no longer a class). Wait for
  `sport-country-league-item`, not a bare `game-row` — other widgets render
  game-rows earlier and parse as skippable rows.
- **Match votes**: `window.pageVar.predictionData.communityData` (absolute
  counts, all markets) is gone. Votes surface only as the "User Predictions"
  percentage row (`user-predictions-row` > `prediction-container`) of the
  hydrated market view, labeled by the `betting-tip-header` cells.
- **User profiles** (`/profile/<name>/`): the header and the statistics table
  (a real `<table>`, header line `stats-table-header-line` as a `<tr>`) render
  on load; the predictions list moved behind the **Feed** tab
  (`navigation-inactive-tab`, click-only) whose AJAX
  (`/proxy/ajax-communityFeed/profile/<id>/<timestamp>/`) is cache-busted and
  therefore not HAR-replayable — the one residual replay hole.
- **In-play match views** (`/…/inplay-odds/#<id>`): moved to §16, which holds
  their hydration, market codes, period and bookies-filter facts as the code
  reads them now. The 2026-08-24 reading that left `live_period` always None
  no longer describes the code: `_parse_live_info` reads the period from the
  `.result-live` block (§20) and fills `live_period` whenever that block
  shows one.

**Reference:** issue #85; branch `fix/oddsportal-redesign-85`.

---

## §20 — The data-testid attributes are gone; anchor on hrefs, semantics and text shape

**Severity:** Critical — every command returned zero data (issue #86), with two
symptoms and one cause.

Some time between 2026-08-24 and 2026-09-01, OddsPortal stripped **every**
`data-testid` from the DOM. `document.querySelectorAll('[data-testid]').length`
is 0 on listings, match pages, community pages and profiles. The layout of
§19 is otherwise unchanged, so the fix is a re-anchoring, not another rework.

### Symptoms

- Match pages: "Match view hydration attempt N/3 timed out", then
  `H2HFragmentResolutionError`, 0/N matches scraped.
- Listings: "Found 0 event rows", so `historic`/`upcoming` return nothing.
- Community: "No top-predictions rows rendered", empty profile records.
- Unit and HAR-replay tests stay green throughout: the fixtures hold the old
  DOM, which is exactly why the break was invisible until a user reported it.

### What replaces what (all verified live 2026-09-02)

| Gone | Anchor now |
|---|---|
| `[data-testid='game-row']` | the row **is** the match link, `a[href*="/h2h/"]`; its two direct `<div>` children are the kickoff/status cell and the participants |
| `[data-testid='date-header']` | a leaf element whose whole text is the group date; require the day number so the "Today" nav filter is not read as a header |
| `[data-testid='time-item']` / `game-status-box` | the row's first column: `HH:MM` while pending, a status or period marker once started ("Finished", "5S") |
| `[data-testid='game-time-item']` | the header's date cell, found by its weekday / date / time paragraphs; the title row is the header's first block, the date row its last |
| `[data-testid='game-host'/'game-guest']` | the title block's first and last blocks, each naming its side in an `a`/`p` with class `truncate` (tennis has no team pages, so never rely on `/team/` links) |
| `[data-testid='breadcrumbs-line']` | the content root's first `<ul>`; the league is its last anchor |
| `[data-testid='sports-nav-*-tab']` | `li.tab-item`; the active one carries `font-bold` on its label span |
| `[data-testid='sub-nav-*-tab']` | plain `button[type=button]`; the selected one carries an inline `font-weight: 700` |
| `[data-testid='outrights-expanded-bookmaker-name']` | the `<p>` inside `a[href*="/bookmakers/"]`, else the logo link's `title`, else the slug of that link through `BOOKMAKER_NAME_BY_SLUG` (the logo `alt` is a generic "Bookmaker" and must not be used as a name; since 2026-10-01 the Unibet.fr row shows its logo only, with no label and no title) |
| `[data-testid='odd-container*']` | `td[class*="event-table-odd-col"]:has(.font-bold)` — the `:has` matters: an expanded submarket row puts the line label ("+2.5") in an odds column too, as a bare span |
| `[data-testid='live-info']` / `partial-result` | the header's live block, marked by `p.result-live`; it disappears when the match ends |
| community `betting-tip-header` | the odds table's middle `thead` headers |
| community row cells | one column per outcome: label header (`bg-gray-light`), odds `p.font-bold`, percentage text, and `.user-pred-pick` on the picked one |

Two structural rules make the rest fall out:

- **Scope to the content root.** The SPA nests the page content in a *second*
  `<main>`; parsing the whole document lets sidebar widgets (upcoming-match
  lists, coupons) register as rows, headers or scores.
- **Peripheral rows left the table.** My coupon / User Predictions / OddsAlert
  now render as sibling blocks *outside* `<table>`, so bookmaker-row selection
  no longer needs a skip list — a bookmaker row is simply a leaf `<tr>` holding
  bookmaker links, and a collapsed line row one holding `img[alt="arrow"]`.

### Two behaviours that flipped back or forward

- **No hash nudge is needed any more**: a match URL renders its match on load,
  even without a fragment. `_hydrate_match_view` now waits first and only
  re-routes the hash as a retry. Market and period switching by
  `#<id>:<market>;<scope>` still work exactly as in §19.
- **In-play `--league` filtering cannot use the href**: in-play rows link to
  `/<sport>/h2h/<home>/<away>/inplay-odds/#<id>`, which carries no league
  segment. The league is only in the section header link above the row
  (`extract_live_match_links`, `_is_league_link`; §16).

### Unrelated live break found alongside

The odds-history modal renders September as **"Sept"**, which `%b` rejects, so
every September timestamp was dropped. Normalized before parsing.

### Detection signal

Hydration timeouts on match pages *and* "Found 0 event rows" on listings at the
same time, while the pages render normally in a browser. Distinguish from
anti-bot (§6): a block also zeroes the structural selectors, and pages come
back without content at all.

### The durable lesson

Do not let the whole scraper hang off one attribute family a site owner can
delete in a single commit, and do not treat green fixtures as evidence the
scraper still works: HAR replay pins the DOM of its capture day. A periodic
`--live` smoke run is what catches this class of break.

**Reference:** issue #86; branch `fix/oddsportal-testids-removed-86`.

---

## §21 — Team pages: the id is the only real key, and the data is back in a payload

**Severity:** Medium — wrong assumptions here return plausible-looking empty
records rather than errors. All points verified live on 2026-09-17 while
building the `team` command (issue #80), from a French IP.

### The URL lies, the id does not

Team pages live at `/<sport>/team/<slug>/<id>/`. Two traps:

- Links without the sport prefix, the form that pre-redesign HAR fixtures still
  carry, render the SPA's own 404 ("Offside — page not found") while answering
  **HTTP 200**. Do not copy team URLs out of old fixtures.
- The slug and the sport prefix are echoed but never read. `/basketball/team/liverpool/lId4TMwf/`
  returns Liverpool's full football record. One placeholder path therefore serves
  every team whatever its sport, which is what the `team` command does. The
  corollary: the sport in the URL tells you nothing about the team, so read it
  from the payload's own links.

### A wrong id looks like a valid page

It answers 200 and builds the `<h1>` and the breadcrumb **from the slug**, so
`/football/team/liverpool/zzzzzzzz/` renders "Liverpool Betting Odds, Results &
Fixtures". Only the payload and the header logo are missing. Key any
existence check on the payload, never on the heading, the title or the
breadcrumb, or a typo becomes a blank row instead of an error.

### The data is in the Next flight payload, not in the DOM

§20 says to anchor on the rendered page, and that holds for match pages. Team
pages are the exception: they ship
`{"basicInfo": {venue, venueTown, venueCountry, coach, countryImage},
"lastPerformance": {form, formEvents, avgGoalsScored, avgGoalsConceded,
scoredBtsPercent, scoredOverPercent}}` inside `self.__next_f.push(...)`, with
its quotes escaped. Unescape `\"`, then brace-match out from the key. It is far
more stable than the classes wrapped around it.

Identity is **not** in that payload: the name comes from the breadcrumb, the
full name from the header `<img alt>`, and the logo from that image's `srcset`,
URL-encoded behind `/_next/image`. Note the first `/proxy/serve/images/team-logo/`
path in the document is usually a fixture opponent's, not the team's, so read
the logo off the header element rather than off the document.

### The form tooltips do not follow their own links' side order

`"1:1 (Jequie - Barcelona) 22.02.2026"` links to
`/football/h2h/barcelona-fc-WGt8En5I/jequie-ARKkmIRH/`: the team is first in the
URL and second in the text. Positional mapping silently yields the opponent's
name. Identify the team by eliminating the opponent's slug instead.

### Geography decides which fields exist

`venue`, `venueTown` and `venueCountry` are simply absent for smaller teams, and
the country flag is not a usable fallback: it is an ISO code for one team
(`br.svg`) and an internal numeric id for another (`198.svg`). Fixture rows
follow the IP's selected bookmakers, so the league is often unavailable while
the form block still renders fine.

### Detection signal

A team record with a plausible name and every other field null means the payload
was missing, which is a bad id, not a parsing break.

---

## §22 — A listing page is still settling after `goto`; the row count is not final

**Severity:** Medium — no corruption today, because the scroll's stability rule
catches it, but it sets the floor on how fast a listing can be collected.

An upcoming-league listing keeps mutating its rendered row count for a few
seconds after navigation returns. Measured 2026-09-17 on `--links-only`:
`england/premier-league` read 16 rows on the first scroll tick and settled at
17, while `spain/laliga` read 46, collapsed to 24, and settled there.
Hydration replaces the server markup with the client-rendered list, so a count
taken too early is both incomplete and, transiently, too high.

This stayed invisible for as long as the per-league cookie wait ran before the
scroll: the 10s banner timeout gave the page all the settling time it needed,
so the scroll's first read was already final. Dismissing the banner once per
context (§11) did not create the reflow, it uncovered it. The scroll absorbed
it by spending one more stability cycle, which is the mechanism working as
designed, and is why the per-league saving is ~8s and not the full 10s.

### Detection signal

- The scroll log shows the count moving on the first ticks, then holding:
  `Initial element count: 46` followed by a repeated `Current element count: 24`.
- A count that **drops** is the tell for hydration. Lazy loading only ever adds
  rows, so a decreasing count never means "more content arrived".
- Symptom if the stability rule is ever weakened: fewer links than the page
  really holds, no error raised, and only on pages nothing happened to wait on.

### Fix pattern

Never read rows straight after `goto`. `PageScroller.scroll_until_loaded`
requires three consecutive identical counts before returning, and that rule is
what makes the later read safe. Anyone tuning `SCROLL_PAUSE_S` or
`MAX_SCROLL_ATTEMPTS` for speed must keep it, and must re-measure on a run
where nothing else waits before the scroll: an unrelated wait upstream hides
the reflow completely.

### References

- `core/browser/scrolling.py` — `scroll_until_loaded`, the consecutive-count rule.
- `core/browser/cookies.py` — `CookieDismisser`, the wait that used to mask this.
- §11 — cookie consent and odds format are per-`BrowserContext`.

---

## §23 — HTTP 429 hides inside a page that loads: the document is 200, the view stays empty

**Severity:** High — it reads as a render race (§19) or as a market that does not
exist, and a match scraped under a 429 could come back with an empty market and
no error.

OddsPortal's nginx rate-limits by IP and answers **429 with no `Retry-After`
header**. A match page fires about 110 requests to the OddsPortal host
(scripts, images, `/proxy/match-event/...`, bonus and coupon AJAX). When the
limit trips, the 429s land on whichever of them come next: the document itself,
a Next.js chunk, or the match feed. If the match feed is refused, the view never
renders and `_hydrate_match_view` used to raise `H2HFragmentResolutionError`
("never rendered match content"). If the refused request is a market tab switch,
the extractor logged "Failed to reach the 1X2 tab" and returned the record
without that market.

Measured 2026-09-24 from a Hetzner Helsinki IP, one fresh browser per load:

- in a burst (loads ~5 s apart), the first 3 loads pass, then about half fail;
- blocking images, fonts and media (~43 requests per load) still fails one load
  in three during a burst, so the limit is not only per second;
- after 10 idle minutes, loads 90 s apart: 5 of 6 pass. The one that failed was
  followed 90 s later by a clean load;
- `curl` on the same URL from the same IP, 8 requests 2 s apart: all 200. One
  request per page does not trip it, which is why the site "works" from a shell.

From a France residential IP the same pages loaded every time, so the symptom
looks like a server-only bug.

### Detection signal

- "never rendered match content", or a missing market, on a host that scraped
  fine an hour earlier, with no code change.
- A response listener shows `429` on the OddsPortal host (images and `_next`
  scripts first), while the document status is often 200.
- Third-party hosts (ads, analytics) throttle on their own; their 429s mean
  nothing about OddsPortal.

### Fix pattern

`BaseScraper._scrape_match_data` records every 429 from the site's domain
(`www.` and bare host alike, since a bare-host link redirects) while the match is
scraped. It raises `RateLimitError` (typed `RATE_LIMITED`, attributed to the IP
so proxy failover rotates) when the view never rendered, or when a refused
request carried data (`document`, `xhr`, `fetch`). A refused image or script on
a view that rendered is ignored: throwing away a complete record for a logo
would turn half of a burst into failures. `retry_with_backoff` waits at least
`RATE_LIMIT_RETRY_DELAY_S` (30 s) before retrying a `RateLimitError`; the
default 2 s backoff lands in the same window.

Listings: a 429 on the listing document itself raises `RateLimitError` in
`collect_historic_links`, `collect_upcoming_links` and `scrape_live` (the
live-now listing), before the league-path guard (§24) could read the nginx
error body as "league does not exist". A 429 on a page of the historic walk
(`#page/N`) raises it too, and the run retries the whole listing: re-fetched
seconds later, the page would be refused again. A 429 on a request inside the
listing still reads as a short listing (§17). The 30 s wait is per task: with
`--concurrency` above 1, the other tasks keep loading pages on the same IP
meanwhile.

Community and team pages: their runs load every page through
`core/browser/session.py`'s `open_page`, which calls `raise_if_rate_limited` on
the document's response, so a 429 on a top-predictions, profile,
match-community or team page raises `RateLimitError`. Each of those runs retries
the whole page through `retry_with_backoff` with `OPERATION_RETRY_CONFIG`
(3 attempts), and a `RateLimitError` waits at least `RATE_LIMIT_RETRY_DELAY_S`
(30 s) before the next attempt. `team` also spaces its pages by
`--request-delay` (`RequestPacer`). Only the document is checked there, and on
a profile the Feed tab's AJAX (`/proxy/ajax-communityFeed/profile/...`), whose
429 raises `RateLimitError` instead of storing the profile with no
predictions. A 429 on any other request inside these pages is not recorded as
one.

### References

- `core/base_scraper.py` — `_scrape_match_data`, the response listener.
- `core/browser/session.py`: `open_page`, `raise_if_rate_limited` (also called
  on the listing documents and on the pages of the historic walk).
- `core/odds_portal_scraper.py`: the listing checks in `collect_historic_links`,
  `_collect_match_links` (the walk's pages), `collect_upcoming_links` and
  `scrape_live`.
- `core/community/user_profile_scraper.py`: the Feed AJAX check.
- `core/retry.py` — the rate-limit delay in `retry_with_backoff`.
- `core/retry.py`: `OPERATION_RETRY_CONFIG` and `RequestPacer`, for the
  community and team runs.
- §6 — anti-bot symptoms; §17 — silent short listings; §19 — hydration.

---

## §24 — An unknown league path answers 200 at the requested URL

**Severity:** Medium — a mistyped league path reads exactly like a league with
no fixtures: 0 rows, no error.

`--league` also accepts a league path (`football/bhutan/premier-league`) for
leagues outside `sport_league_constants.py`. OddsPortal does not redirect an
unknown path: `/football/bhutan/no-such-league/`, `/results/` included, answers
**200 at the same URL** with an "Offside — page not found" body and the bare
title "OddsPortal". A real league off-season (Bhutan on 2026-09-24) also shows
0 rows, so the row count cannot tell them apart, and neither can
`_assert_season_page_reached`, which only catches redirects (§4, §15).

### Detection signal

- A real league page, fixtures or `/results/`, links to its country page
  (`a[href='/football/bhutan/']`, breadcrumb). The not-found body has no such
  link. The link is in the server-rendered HTML, so it is there right after
  `goto`.
- The href is relative, so the check holds on regional `--base-url` domains
  and in every language, unlike the page title.

### Fix pattern

`OddsPortalScraper._assert_league_page_exists` runs after navigation for league
paths only (built-in keys are validated against the mapping) and raises a
non-retryable `PageNotFoundError`. The live command's league filter compares
each row's section-header league link with the league's path
(`extract_live_match_links`, §16), so an unknown path there still yields an
empty result.

### References

- `core/url_builder.py` — `get_league_url`, `is_league_path`.
- `core/odds_portal_scraper.py` — `_assert_league_page_exists`.

---

## §25: A sport's site path is not always its CLI name

**Severity:** High (wrong data under the requested sport).

The `Sport` enum value is the site's path segment for every sport but one:
`ice-hockey` lives under `/hockey/` (`/hockey/usa/nhl/`, `/hockey/h2h/...`).
`upcoming --sport ice-hockey --date <d>` used to build `/matches/ice-hockey/<d>/`;
the site answered with its default football page, and the run returned 60
football links labelled `ice-hockey` (2026-09-29). The community predictions page
had met the same trap first (`#sport/hockey/`).

### Detection signal

Rows of a listing whose href starts with another sport's path, or, in the log,
`None of the N rows of this listing links under /<slug>/: it lists no '<sport>' match.`

### Fix pattern

- `site_slug(sport)` in `core/url_builder.py` (with `SPORT_SITE_SLUGS`) is the one
  place that maps a sport to its path; build every sport-level URL with it (date
  listing, live-now listing, community predictions).
- The listing guard: `extract_match_rows` and `extract_live_match_links` take the
  requested sport and keep only rows whose href starts with `/<site_slug>/`,
  counting the others in their summary log line. With the right URL it never
  fires; it keeps a future path change from mixing sports into the output.
- League URLs in `sport_league_constants.py` already use the site path;
  `tests/utils/test_sport_league_constants.py` pins it for every league.
- A league path given to `--league` may start with the site path or the CLI
  name (`hockey/usa/nhl` or `ice-hockey/usa/nhl`); `get_league_url` builds the
  URL on the site path.

---

## §26: A market or period switch resets the bookies filter to Classic

**Severity:** High (wrong data under the requested option, silently).

The match view opens with the "Classic Bookies" panel. `--bookies-filter all`
or `crypto` clicks its sub-nav button once the view hydrates, but every hash
switch (market or period, §7, §19) renders the view again with the default
panel. From v0.11.0 to the fix every scraped market was read with the Classic
panel: live, "All Bookies" showed 7 rows on 1X2 and the scrape kept 4. The filter is applied in the page: its click
fires no request, so a HAR holds every bookmaker and a replay resets the same
way. Writing the hash the URL already holds renders nothing again and keeps the
panel.

### Detection signal

- The `_all` and `_classic` goldens of one match are identical, or the
  `_crypto` golden holds the classic bookmakers.
- On the page, the bold bookies button reads "Classic Bookies" when the table is
  read although the run asked for another panel.

### Fix pattern

`OddsPortalMarketExtractor` shows the requested panel after the last
navigation step and before every read (`_show_bookies`, through
`SelectionManager.ensure_selected`): after the market switch and the period
selection in `extract_market_odds`, and after the switch of an umbrella's line
discovery. It clicks nothing when the panel shown is the one requested, so
`classic` costs no click. A panel that cannot be shown logs a warning and the
market is read as shown.

### References

- `core/odds_portal_market_extractor.py`: `_show_bookies`, `extract_market_odds`, `_discover_line_names`.
- `core/browser/selection.py`: `SelectionManager.ensure_selected`.
- §7: the hash switch; §19: the hash-driven view.

---

## §27: A market switch can show another market's odds under the requested tab

**Severity:** High (another market's odds written under the requested one, silently).

Every hash switch (market or period, §7, §19) makes the view send one data
request, `/proxy/match-event/<n>-<n>-<event id>-<market id>-<scope>-<token>.dat`,
decrypt the answer with WebCrypto (AES-CBC, a PBKDF2 key), gunzip it and render
the table from `{"d": {"bt": <market id>, "sc": <scope>, "nav": {<market id>: ...},
"encodeventId": <event id>, "oddsdata": ...}}`. `bt` is the market the data carry
and `nav` lists every market the match offers. The ids (read on 2026-10-02, the
same on every sport and on the mirrors) are in `OddsPortalSelectors.MARKET_FEED_IDS`:
1 1X2, 2 Over/Under, 3 Home/Away, 4 Double Chance, 5 Asian Handicap, 6 Draw No
Bet, 8 Correct Score, 12 European Handicap, 13 Both Teams to Score. The scope in
the request is the one the view settles on: on basketball, `#<id>:home-away;2`
asks for scope 1.

Three things put another market's odds under the requested tab:

- **A market the match does not offer.** The view asks for its default market's
  data (1X2, or Home/Away on the sports of `DEFAULT_MARKET_CODE_BY_SPORT`) and
  shows that market, fresh tabs and all. A tennis match switched to `bts`, `1X2`
  or `dnb` asked for market 3 each time. Before the fix the scraper read that
  table under the requested name.
- **Data of another market.** On 2026-10-02 from 14:56 to about 15:01, from a
  residential IP, after two 50-match listing runs and with no 429: the 1X2 and
  its history read fine, then Both Teams to Score and Double Chance were written
  with the 1X2 odds of the same bookmakers, Over/Under +2.5 found no line, every
  odds-history tooltip stopped settling, exit 0. Ten minutes later the same
  commands were clean; the trigger was not reproduced on demand, the same burst
  included. Serving the 1X2 answer for another market's request in a replay
  gives exactly that: Both Teams to Score renders a two-column table of each
  bookmaker's first two 1X2 odds, Over/Under renders one line "Over/Under 0",
  and Asian Handicap renders a line "Asian Handicap 0" whose odds are the 1X2's.
  The feed is `cache-control: public, max-age=345600`.
- **No usable answer.** A refused, failed, empty or truncated answer leaves the
  view unrendered ("No view of", the tab bar gone), and the market was written
  empty.

### Detection signal

- A market whose rows start with the odds of that bookmaker's 1X2 row (Both
  Teams to Score with the first two 1X2 prices, Double Chance equal to 1X2).
- "No row of line '+2.5' within 20000 ms" on a match that has the line.
- A run much slower than usual, with "No settled odds-history tooltip" on every
  cell.

### Fix pattern

`PlaywrightManager` installs `VIEW_DATA_HOOK_JS` (`core/browser/view_data.py`) in
every context: in the top frame, a Proxy around `SubtleCrypto.decrypt` records
the event, market, scope and offered markets of each decrypted view data answer,
read as the view reads it (up to three gzip layers, JSON cut at a trailing error,
a market offered when one of its periods lists a bookmaker, which is what makes
the view fall back to its default market). `switch_view`
waits for the data request the switch sends (registered before the hash is
written), its answer, the fresh view, then the recorded data, and raises
`MarketDataError` when the request is not sent or not answered within
`VIEW_DATA_CAP_MS`, comes back with an error, the view does not render, or the
data carry another market than the one switched to while the match offers it.
`MarketTabNavigator._navigate_by_hash` reads a market the match does not offer
as an empty market, with a warning and without the tab-click fallback. When no
decrypted data were recorded within `VIEW_DATA_RECORD_CAP_MS` (the hook gone, a
changed format, data served unencrypted), the market is read from the request's
market id, with one warning per page: a market not offered is still caught, data
of another market is not, and each switch waits that cap.

`MarketDataError` passes through every market-level `except`
(`extract_market_odds`, `scrape_markets`, the market loop of
`_scrape_match_data_unguarded`), so the match is retried, then reported failed;
a 429 among those requests still becomes `RateLimitError` (§23).

A match link that names a market (`#<id>:bts;2`) is loaded on its event
instead (`OddsPortalSelectors.event_url`), then the market is reached through
the checked switch, like any other market request. Live on 2026-10-06, a page
loaded directly on `#lMp9YMye:bts;2` fetched the 1X2 data instead of the btts
data. The loaded-view check (`loaded_view`) still covers the other case: a market
asked again on a page whose URL already names it, where the switch is skipped
since writing the same hash renders nothing, and the data the view already
holds are checked the same way.

Not covered: the tab-click path (in-play views, markets without a hash code);
and the refresh polls of a match not started (`requestPreMatch.refresh`, every
15 s by default), which re-render the table from answers no switch checks.

`tests/integration/test_football.py::TestAMarketWhoseDataDidNotCome` replays
each case by editing a HAR (replays abort a request the HAR does not hold).

### References

- `core/browser/view_data.py`: `VIEW_DATA_HOOK_JS`, `VIEW_DATA_JS`.
- `core/browser/market_navigation.py`: `switch_view`, `loaded_view`, `MarketTabNavigator._navigate_by_hash`.
- `core/odds_portal_selectors.py`: `MARKET_FEED_IDS`.
- `core/exceptions.py`: `MarketDataError`.
- §23 (429 on data requests), §26 (the panel every switch resets).

---

## §28: An invisible anti-bot trap row clones a match link with invented team ids

**Severity:** High (every listing run visited a page built to catch bots, then reported it as a failed match).

OddsPortal pages carry an inline script, called with two 8-character tokens
written into the page's HTML (`('37e4f5e9', '5a49c1bd')` on both captures of
2026-10-05, another pair on 2026-10-02). None of the HARs committed on
2026-09-02 holds it; every HAR committed since 2026-09-17 does. Once a page
lists at least two rows whose links all point at
`/<sport>/h2h/<home>-<id>/<away>-<id>/`, the script:

- clones one of those rows at random;
- replaces the two team ids of each link with the tokens and drops the
  `#<event>` fragment;
- hides the clone with `position:absolute;left:-9999px;top:0;height:0;overflow:hidden`,
  `aria-hidden="true"` and `data-ab-trap="1"`, all three on the clone's root,
  three levels above the link;
- inserts it after a random row of the same list, and injects a new one when
  the list re-renders and drops it (a MutationObserver), or, on a page with no
  DOM mutation in its first 8 s, every 20 to 40 s; it never keeps more than
  one clone.

A person never sees the clone. A scraper that takes every h2h link does: on a
league listing it was one more match, with the kickoff of the row it cloned;
its page never rendered (`match view hydration failed`, after two attempts),
and the run reported one failed URL per listing page. When the cloned row is
the first of its date group, the clone also carries that group's date header,
inserted among the rows of another date: the rows after it took that date, so
their `kickoff_utc` moved and `upcoming --date` dropped them (6 of 24 replays
of the committed listing). The same HTML also calls
`/ajax-esi/ab-proof-mint/` every 250 s with an `X-Proof-Nonce` header. Whether
a trap visit feeds the rate limit of §23 is not known.

The filter of issue #61 (`_is_offscreen_row`) read the link's own `style`.
Since the rows became the links themselves (§20), the clone's hiding style sat
on an ancestor and every trap went through, on the historic, upcoming and live
listing walks alike.

The clone's team names change with each injection, since it copies a random
row (Crystal Palace - Nottingham, then Coventry - Tottenham on the same page);
the tokens stay. The tokens seen so far were lowercase hexadecimal, while real
ids mix cases.

### Detection signal

- A links-only run returns a link without `#<event>`; real listing rows always
  carry it. Its two team ids come back on other runs under other names.
- A listing run logs `carry no event id` (a visible link without `#<event>`)
  or `are hidden` (every row of a page hidden).
- A listing scrape logs `match view hydration failed` for such a link.
- `data-ab-trap` in the page HTML.

### Fix pattern

`OddsPortalSelectors.is_hidden(link)` reads the link and each of its
ancestors: the trap attribute, or an inline style holding one of
`HIDDEN_STYLE_MARKERS`, hides it. Every walk over h2h links skips a hidden one:
`extract_match_rows` and `extract_live_match_links` (counted in their
"offscreen rows skipped" log line) and the top-predictions and profile
parsers. `extract_match_rows` also ignores a hidden date header. `aria-hidden`
is not used alone, since a modal may set it on the whole page.

The trap needs two rows of match links only, so it showed on league listings;
the live-now listing captured with one match and the community pages captured
so far hold none, but the rule covers all four walks.

The check reads the attribute and the inline style only, so two variants would
go through, and each walk says so. A page whose rows are all hidden (a hiding
style on `body` or a wrapper; the trap hides one row) logs `All N rows of this
listing (<url>) are hidden`, and the top-predictions and profile parsers log
the same for their page, instead of reading as an empty listing.
`extract_match_rows` also warns once per page when visible links carry no
`#<event>` (`N visible match links of this listing (<url>) carry no event id`),
and keeps them: on 2026-10-05 none of the committed listing HARs held such a
link once the hidden clones were left out, so one is a clone whose hiding moved
into a class.

`tests/integration/test_listing_replay.py` replays a Premier League listing
captured with the trap: the script runs again in the replay and injects it,
and the rows, kickoffs included, must equal the golden.

### References

- `core/odds_portal_selectors.py`: `is_hidden`, `TRAP_ATTRIBUTE`, `HIDDEN_STYLE_MARKERS`.
- `core/base_scraper.py`: `extract_match_rows`, `extract_live_match_links`;
  `core/listing.py`: `_ListingRows.warn_if_all_hidden`.
- `core/community/top_predictions_parser.py`, `core/community/user_profile_parser.py`,
  `core/community/row_helpers.py` (`visible_match_links`).
- `tests/integration/fixtures/football/premier-league/upcoming-listing/`.
- §1 (the issue #61 twin), §20 (rows are links), §23 (rate limit).

---

## §29: The search runs in two steps, and its data is in the flight payload

**Severity:** Medium (a name search that looks like it returns matches returns teams, and an unknown team id looks
like a team with no match). Verified live on 2026-10-08 from a French IP while building the `search` command.

### Two steps, three URLs

- `/search/results/<name>/<sport>/` lists the **teams** whose name matches, never matches: 19 for "Nacional"
  (Portugal, Uruguay, Bolivia, U20 and women's sides), 1 for "Nacional Potosi".
- `/search/results/:<teamId>/` lists the team's past matches, 20 a page, newest first; later pages sit at
  `/search/results/%3A<teamId>/page/<N>/`.
- `/search/:<teamId>/` lists its upcoming matches, but only those the selected bookmakers price: Nacional Potosi
  showed none ("no odds available from your selected bookmakers") while Arsenal showed 4.

### The data is in the payload

Every search page ships a `searchData` object in the Next flight payload, whole inside one
`self.__next_f.push([1,"..."])` chunk. Decode the chunk as a JSON string, then `raw_decode` from the key: a brace
inside a team name then cannot cut the object short. The name search holds `participants`, keyed by numeric id, so
the payload order is not the page's; rank by `score`. A team tab holds `total`, `rows` and, when it paginates,
`pagination.pageCount`. Empty collections arrive as `[]` (`"pagination":[]`), not as objects. A row's league is
`breadcrumbs.tournament.url`; `tournament-url` is only the slug. The rendered date shows no year (`03/Oct`); use
`date-start-timestamp`. The h2h link does not follow home and away (one normalized URL per team pair, §1:
`arsenal-.../brighton-...` for Brighton at home), so they come from `home-name` and `away-name`. The shown score
gives a shoot-out winner one more goal (PSG 2:1 Arsenal for a 1:1 draw won 4:3 on penalties); `partialresult`
(`0:1, 1:0, 0:0, 4:3`) holds the periods, the shoot-out last. International rows tag names with a country and a
trailing space (`Arsenal (Eng) `).

The rendered results rows also hold the §28 trap row (hex ids, no fragment). The payload never carries it.

### Detection signal

An unknown team id answers 200 with `"searchData":{"total":0,"pagination":[]}`, exactly what a quiet team returns.
Its sibling prop `"searchStringUrl"` is `""` and the heading reads "Search Results for: " with no name; for a real
team both hold the team's name. Key the check on an empty `searchStringUrl`. A missing key means the check cannot
tell, never that the team is unknown, so a renamed prop does not turn every team into an unknown one.

A results page past the first is served with its own rows in the payload (`searchData.page` 2 for `/page/2/`,
checked live on 2026-10-08). Should it ever serve page 1 again, the rows would repeat and a dedup on event id
would hide it, so the parser compares `searchData.page` with the page asked for.

### Fix pattern

- `core/search/search_parser.py` reads only the payload; `parse_matches` raises `PageNotFoundError` ("does not
  exist on OddsPortal") on an empty `searchStringUrl`, and `ParsingError` when `searchData.page` is not the page
  asked for.
- `core/search/search_scraper.py` fails the whole call when one page fails: a partial list would tell a caller that
  a match is not there when a page was only missing.

### References

- `core/search/`, `cli/commands/search.py`, `tests/integration/test_search.py`.
- §21 (team pages, the other payload-backed page), §25 (`site_slug`), §28 (the trap row).

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
