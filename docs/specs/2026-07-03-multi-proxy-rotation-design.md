# Multi-proxy rotation support

**Date:** 2026-07-03
**Branch:** `feat/multi-proxy-rotation` (off `master`)
**Notion task:** Add multi-proxy rotation support — `38febd78-e2ee-815a-9824-d22a81e8cdb9`
**Origin:** GitHub issue #71 (user scraping ~300K matches wants load spread across multiple proxies)

## Objective

Let a user supply several proxies and have the scraper spread its request volume
across them, so a large run (e.g. ~300K matches) does not funnel every request
through a single IP. Today only one static proxy is supported: `ProxyManager`
builds one config and `rotate_proxy()` is a no-op, so all concurrent tabs share
one IP.

The user's mental model (issue #71): "N proxies + concurrency N → volume spread
equally across the N proxies." This maps to round-robin assignment of matches
across a pool of one browser context per proxy.

## Non-goals (YAGNI)

- No active health-check / liveness probe of proxies at startup or on a timer.
- No auto-rehabilitation of a blacklisted proxy within a run.
- No per-proxy in-flight concurrency cap (the user controls `--concurrency`).
- No `--proxy-file` input (decided: repeated `--proxy-url`).
- No proxy sourcing/management (buying, rotating provider endpoints, etc.).
- No weighting / geo-affinity / sticky-per-league assignment.
- Free public proxies are **not** wired into the automated test suite.

## Decisions (from brainstorming)

1. **Scope:** distribution **plus basic failover**. A proxy that fails repeatedly
   is dropped from rotation (blacklist); tasks fall over to the remaining proxies.
2. **Input:** `--proxy-url` becomes repeatable (`multiple=True`). Each value carries
   its own optional embedded credentials `scheme://[user:pass@]host:port`. A single
   `--proxy-url` stays 100% backward compatible.
3. **Assignment:** **round-robin per match** over a persistent pool of one context
   per proxy, skipping blacklisted proxies.
4. **Failure attribution:** only proxy-attributable errors count against a proxy —
   `ErrorType.NAVIGATION` (timeout/connection/network/proxy) and
   `ErrorType.RATE_LIMITED` (429/blocking). Content errors (`PARSING`,
   `MARKET_EXTRACTION`, `PAGE_NOT_FOUND`, `HEADER_NOT_FOUND`) never blacklist a proxy.

## Refinements discovered during planning

These do not change the user-facing decisions above; they make the implementation
correct and keep the single/no-proxy path byte-for-byte unchanged.

- **Failover is active only with ≥ 2 proxies.** With 0 or 1 proxy, `report_result`
  is a no-op — a single flaky proxy is never blacklisted, exactly like today. With
  ≥ 2 proxies, all of them *can* end up blacklisted (→ clean failure per §4 below).
- **Only the per-match scraping phase rotates.** Link collection / pagination
  (`_collect_match_links`) stays on the default context (single IP). It is a tiny
  fraction of total volume; keeping it on the pre-warmed default context avoids
  extra risk for near-zero benefit.
- **Each proxy context must be warmed once (correctness-critical).** Odds format and
  cookie consent are **per-context** state, established today by navigating the
  default context to `ODDSPORTAL_BASE_URL` and running `_prepare_page_for_scraping`
  (`set_odds_format` + cookie dismissal). A cold context would render match pages
  with the wrong odds format → **silently corrupted odds values**. So every
  non-default proxy context is warmed once (navigate to `ODDSPORTAL_BASE_URL`,
  dismiss cookies, set decimal odds) before it scrapes matches. This warrants an
  `docs/agentic-gotchas.md` entry.

## Key constraint: Playwright proxy is per-context

Playwright sets the proxy at browser-launch **or** per `BrowserContext`, never per
page/tab. Today the scraper runs one browser → one context → many tabs
(`context.new_page()`), so every tab shares one IP. To use several IPs concurrently
we need **several contexts, one proxy each**. On Chromium, per-context proxy
override requires the browser to be launched with `proxy={"server":"per-context"}`.

## Execution model

- **≤ 1 proxy → current behavior, unchanged.** Browser launched with that single
  proxy (or none); one context; one code path. The common case gets no new logic.
- **≥ 2 proxies → multi-proxy mode.** Browser launched with
  `proxy={"server":"per-context"}`; one `BrowserContext` created per proxy config,
  keyed by a stable proxy key. Scraping tabs open in the chosen proxy's context.

Contexts are created eagerly at startup (proxy counts are small, ~tens). Lazy
creation is a possible future optimization, out of scope here.

## Design

### 1. CLI surface (`cli/options.py`, `cli/validators.py`)

- `--proxy-url` gains `multiple=True`. Click yields a tuple; downstream a list of
  proxy strings (possibly empty, or length 1 for the legacy path).
- `validate_proxy_url` is widened to accept optional embedded credentials. Current
  regex `^(scheme)://(host):(port)$` rejects `user:pass@`. New pattern accepts an
  optional `userinfo` segment: `^(https?|socks4|socks5)://([^:@/]+:[^:@/]+@)?[\w.-]+:\d+$`.
  Applied to each value in the tuple. Invalid entries → `click.BadParameter` naming
  the offending value.
- `--proxy-user` / `--proxy-pass` retained. They apply **only** when exactly one
  `--proxy-url` is given and it has no embedded credentials (legacy path). If
  combined with multiple proxies, emit one non-blocking warning and ignore them
  (per-proxy embedded creds win).

### 2. `ProxyManager` reworked into a rotating pool (`utils/proxy_manager.py`)

Constructor accepts a **list** of proxy URLs (plus the legacy single
`proxy_user`/`proxy_pass` for the one-proxy case). Responsibilities:

- **Parse** each URL into a Playwright proxy config dict: `server` = `scheme://host:port`
  (credentials stripped out of `server`), with `username`/`password` split into
  separate keys when present. This also fixes a latent bug in the current code,
  which passes the raw URL (creds included) as `server` — Playwright expects creds
  in separate keys, not in `server`.
- Assign each parsed proxy a stable **key** (e.g. sanitized `scheme://host:port`,
  credentials never logged) used to map to its context and to track failures.
- **Round-robin cursor** `next() -> ProxyEntry | None`: returns the next non-
  blacklisted proxy, advancing circularly; `None` when all are blacklisted.
- **Failure tracking:** `report_result(key, error_type)`. Consecutive failure
  counter per proxy, incremented only for `NAVIGATION` / `RATE_LIMITED`, reset to 0
  on any success. When the counter reaches
  `PROXY_CONSECUTIVE_FAILURE_THRESHOLD` (constant, default 3) the proxy is
  blacklisted with a `logger.warning` (key only, no creds).
- **Zero proxies:** the pool holds a single virtual entry with config `None`
  (direct connection), so no-proxy behaves exactly like today.

The credential-sanitizing logger helper (`_sanitize_url_for_logging`) is retained
and used everywhere a proxy is logged.

### 3. Context pool (`core/playwright_manager.py`)

- `initialize(...)` decides launch proxy: single/none proxy → launch as today;
  ≥ 2 proxies → launch with `proxy={"server":"per-context"}`.
- Create one `BrowserContext` per pool entry (reusing the existing context kwargs:
  user agent, locale, timezone). Store them keyed by proxy key. The single/none
  case keeps a single context (unchanged), keyed the same way so callers are
  uniform.
- New helper `new_page_on_proxy(key) -> Page` opens a page in the given proxy's
  context. This is the single funnel replacing direct `context.new_page()` calls.

### 4. Integration point (route per-match page creation through the pool)

Only the per-match scraping loop rotates. `base_scraper.py:467` (inside
`scrape_with_semaphore`) changes from `self.playwright_manager.context.new_page()`
to `page, key = await self.playwright_manager.new_rotated_page()`.

Flow per match:
1. `new_rotated_page()` calls `proxy_manager.next()`; if `None` (all blacklisted)
   it raises `AllProxiesExhaustedError` → the match fails via the existing
   `except` path (ProxyManager logs the "all proxies blacklisted" error once).
2. Otherwise it opens a page in the selected proxy's context and returns
   `(page, key)`.
3. On completion, classify the outcome and call
   `playwright_manager.report_page_result(key, error_type_or_None)` (None on
   success → resets that proxy's consecutive-failure counter).

`_collect_match_links` (`odds_portal_scraper.py:381`) is left unchanged on the
default context. The initial warm-up page created at launch stays valid for the
single/none path.

Before the per-match loop, `BaseScraper` warms each **non-default** proxy context
once (navigate to `ODDSPORTAL_BASE_URL`, dismiss cookies, `set_odds_format`),
tracking warmed keys on the instance so multi-league runs warm each context only
once. A warm failure reports one proxy-failure strike for that key.

### 5. Plumbing

`run_scraper` (`core/scraper_app.py`) already receives `proxy_url`. It becomes a
list (`proxy_urls: list[str]`), threaded from `kwargs.get("proxy_url")` in
`cli/commands/{upcoming,historic}.py`. `ProxyManager(...)` is constructed from the
list. No change to `--concurrency` semantics: in-flight tasks per proxy ≈
`concurrency / healthy_proxies`, an emergent property of round-robin + the existing
semaphore.

## Testing plan

### Automated (unit, deterministic, no network) — mirror source under `tests/`

- **URL parsing** (`ProxyManager`): `scheme://host:port` (no creds);
  `scheme://user:pass@host:port` (creds split into `username`/`password`, absent
  from `server`); invalid scheme rejected; `socks5` accepted; credentials never in
  the sanitized log string.
- **Round-robin:** even distribution over N proxies; wrap-around; blacklisted
  proxies skipped; single-proxy pool always returns that proxy; empty pool returns
  the virtual `None` (direct) entry.
- **Blacklist:** threshold reached only on `NAVIGATION`/`RATE_LIMITED`; content
  error types never increment; counter resets on success; "all blacklisted" →
  `next()` returns `None`.
- **CLI:** repeated `--proxy-url` → list; validator accepts embedded creds; invalid
  entry → `BadParameter`; `--proxy-user/--proxy-pass` ignored-with-warning when
  combined with multiple proxies.
- **Backward compatibility (regression guard):** no-proxy and single-proxy paths
  produce the same launch config and single context as before; existing proxy tests
  stay green.

Gate: `uv run pytest tests/ -q --ignore=tests/integration/` green before and after.

### Real-condition validation (manual smoke — NOT in the automated suite)

Free public proxies are non-deterministic and short-lived; wiring them into pytest
would make the suite flaky. They are used only for a one-off manual smoke test at
implementation time:

1. Source a handful of currently-alive free proxies (public lists / a fetch script;
   e.g. the ProxyScrape API or spys.one, per the related "Test paid proxies" Notion
   task).
2. Run the scraper on 2–3 known-good OddsPortal matches with 2–3 proxies and
   `--concurrency` ≥ proxies, inspecting logs to confirm: round-robin picks
   different proxy keys and volume is spread across them.
3. Failover: inject one deliberately dead proxy (e.g. `http://127.0.0.1:1`) among
   the good ones; confirm it is blacklisted after the threshold and traffic
   continues on the survivors; confirm "all dead" fails cleanly.

Findings from the smoke run (if any new OddsPortal proxy/block behavior surfaces)
are appended to `docs/agentic-gotchas.md` per the CLAUDE.md gotchas rule.

### Docs

- README + `--help`: document repeatable `--proxy-url`, embedded-credentials
  format, and the `--proxy-user/--proxy-pass` legacy-single-proxy caveat.

## Success criterion

With ≥ 2 valid proxies, a scraping run spreads matches across them (visible in
logs), a repeatedly-failing proxy is dropped without aborting the run, and the
no-proxy / single-proxy paths are byte-for-byte unchanged in behavior (all existing
tests green). The reworked `ProxyManager` correctly splits embedded credentials
into Playwright's `username`/`password` keys.
