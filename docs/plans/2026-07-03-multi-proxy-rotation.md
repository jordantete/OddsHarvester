# Multi-proxy rotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user pass several `--proxy-url` values and have the per-match scraping spread across them via round-robin, with basic failover (a repeatedly-failing proxy is dropped), and zero behavior change to the existing no-proxy / single-proxy paths.

**Architecture:** `ProxyManager` becomes a rotating pool of `ProxyEntry` objects (one per proxy, plus a virtual "direct" entry when none). `PlaywrightManager` creates one `BrowserContext` per pool entry (Chromium per-context proxy override, launched with a `per-context` sentinel only when ≥2 proxies) and exposes `new_rotated_page()` / `report_page_result()`. `BaseScraper.extract_match_odds` warms each non-default context once (odds format + cookie consent are per-context state) then opens each match tab on the round-robin-selected proxy. Failover counts only navigation/rate-limit errors and is active only with ≥2 proxies.

**Tech Stack:** Python 3.12, Playwright (async), Click, pytest, `urllib.parse`. Branch `feat/multi-proxy-rotation` (off `master`), already created.

**Spec:** `docs/specs/2026-07-03-multi-proxy-rotation-design.md`

**Run all unit tests with:** `uv run pytest tests/ -q --ignore=tests/integration/`

## Global Constraints

- Python >=3.12, line length 120, double quotes, Ruff. `S101`/`T201` allowed.
- DRY: proxy-failure error-type classification lives in `core/retry.py` (canonical home for error keywords/patterns). Import it; do not duplicate the tuple.
- No behavior change for the no-proxy and single-proxy paths (existing tests in `tests/utils/test_proxy_manager.py`, `tests/core/test_playwright_manager.py`, `tests/core/test_scraper_app.py`, `tests/core/test_base_scraper.py` must stay green).
- Credentials must never be logged. Reuse `ProxyManager._sanitize_url_for_logging`.
- Failover active only when ≥2 real proxies; blacklist threshold = 3 consecutive proxy-attributable failures.
- `utils/proxy_manager.py` must NOT import from `core/` (keep layering: caller passes a plain `is_proxy_failure: bool`).
- Never commit to `master`; commit each task on `feat/multi-proxy-rotation`. Never `push --force`.

---

## File Structure

- `src/oddsharvester/core/retry.py` — add `PROXY_ATTRIBUTABLE_ERROR_TYPES` + `is_proxy_attributable_error()`.
- `src/oddsharvester/core/exceptions.py` — add `AllProxiesExhaustedError`.
- `src/oddsharvester/utils/proxy_manager.py` — rework into a rotating pool (`ProxyEntry`, parse list, `next_proxy`, `report_result`, `launch_proxy`, `is_multi_proxy`; keep legacy accessors).
- `src/oddsharvester/core/playwright_manager.py` — multi-context creation + `new_rotated_page` / `new_page_on_key` / `non_default_context_keys` / `report_page_result`.
- `src/oddsharvester/core/base_scraper.py` — `__init__` gets `self._warmed_proxy_keys`; `extract_match_odds` warms non-default contexts and rotates per-match page creation + reports results.
- `src/oddsharvester/core/scraper_app.py` — build `ProxyManager` from a list; pass `proxy_manager` to `start_playwright`.
- `src/oddsharvester/core/odds_portal_scraper.py` — `start_playwright(proxy_manager=...)` forwards to `initialize`.
- `src/oddsharvester/cli/validators.py` — `validate_proxy_url` handles a tuple + optional embedded credentials.
- `src/oddsharvester/cli/options.py` — `--proxy-url` becomes `multiple=True`.
- `README.md` + `docs/agentic-gotchas.md` — document usage + the per-context warm-up gotcha.
- `scripts/fetch_free_proxies.py` — helper for the manual smoke test (not imported by the package, not in the automated suite).

Test files: `tests/utils/test_proxy_manager.py`, `tests/core/test_retry.py`, `tests/core/test_exceptions.py`, `tests/core/test_playwright_manager.py`, `tests/core/test_base_scraper.py`, `tests/core/test_scraper_app.py`, `tests/cli/test_validators_proxy.py` (new).

---

## Task 1: Proxy-failure error classification helper (`retry.py`)

**Files:**
- Modify: `src/oddsharvester/core/retry.py`
- Test: `tests/core/test_retry.py`

**Interfaces:**
- Produces: `PROXY_ATTRIBUTABLE_ERROR_TYPES: tuple[ErrorType, ...]` and
  `is_proxy_attributable_error(error_type: ErrorType | None) -> bool` (True only for `NAVIGATION` and `RATE_LIMITED`).

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_retry.py`:

```python
from oddsharvester.core.retry import is_proxy_attributable_error
from oddsharvester.core.scrape_result import ErrorType


class TestProxyAttributableError:
    def test_navigation_is_proxy_attributable(self):
        assert is_proxy_attributable_error(ErrorType.NAVIGATION) is True

    def test_rate_limited_is_proxy_attributable(self):
        assert is_proxy_attributable_error(ErrorType.RATE_LIMITED) is True

    def test_parsing_is_not_proxy_attributable(self):
        assert is_proxy_attributable_error(ErrorType.PARSING) is False

    def test_page_not_found_is_not_proxy_attributable(self):
        assert is_proxy_attributable_error(ErrorType.PAGE_NOT_FOUND) is False

    def test_none_is_not_proxy_attributable(self):
        assert is_proxy_attributable_error(None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_retry.py::TestProxyAttributableError -q`
Expected: FAIL with `ImportError: cannot import name 'is_proxy_attributable_error'`.

- [ ] **Step 3: Write minimal implementation**

In `src/oddsharvester/core/retry.py`, after the `classify_error` function, add:

```python
# ErrorTypes attributable to the proxy/IP (vs. content-parsing failures).
# Used by multi-proxy failover to decide whether a failure counts against a proxy.
PROXY_ATTRIBUTABLE_ERROR_TYPES = (ErrorType.NAVIGATION, ErrorType.RATE_LIMITED)


def is_proxy_attributable_error(error_type: ErrorType | None) -> bool:
    """Return True if this error type should count against the proxy that produced it."""
    return error_type in PROXY_ATTRIBUTABLE_ERROR_TYPES
```

`ErrorType` is already imported at the top of `retry.py` (`from oddsharvester.core.scrape_result import ErrorType`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_retry.py -q`
Expected: PASS (all retry tests).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/retry.py tests/core/test_retry.py
git commit -m "feat(retry): add is_proxy_attributable_error helper for proxy failover"
```

---

## Task 2: `AllProxiesExhaustedError` exception

**Files:**
- Modify: `src/oddsharvester/core/exceptions.py`
- Test: `tests/core/test_exceptions.py`

**Interfaces:**
- Produces: `AllProxiesExhaustedError(ScraperError)` — raised when every proxy in the pool is blacklisted.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_exceptions.py`:

```python
from oddsharvester.core.exceptions import AllProxiesExhaustedError, ScraperError


class TestAllProxiesExhaustedError:
    def test_is_scraper_error(self):
        assert issubclass(AllProxiesExhaustedError, ScraperError)

    def test_message_preserved(self):
        err = AllProxiesExhaustedError("all proxies blacklisted")
        assert str(err) == "all proxies blacklisted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_exceptions.py::TestAllProxiesExhaustedError -q`
Expected: FAIL with `ImportError: cannot import name 'AllProxiesExhaustedError'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/oddsharvester/core/exceptions.py`:

```python
class AllProxiesExhaustedError(ScraperError):
    """Raised when every proxy in the rotation pool has been blacklisted.

    Signals that no healthy IP remains for further requests.
    """
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/test_exceptions.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/exceptions.py tests/core/test_exceptions.py
git commit -m "feat(exceptions): add AllProxiesExhaustedError"
```

---

## Task 3: Rework `ProxyManager` into a rotating pool

**Files:**
- Rewrite: `src/oddsharvester/utils/proxy_manager.py`
- Test: `tests/utils/test_proxy_manager.py` (existing tests must stay green; add new ones)

**Interfaces:**
- Consumes: nothing from earlier tasks (stays free of `core/` imports).
- Produces:
  - `ProxyEntry` dataclass: `key: str`, `config: dict[str, str] | None`, `consecutive_failures: int = 0`, `blacklisted: bool = False`.
  - `ProxyManager(proxy_urls: list[str] | None = None, proxy_user: str | None = None, proxy_pass: str | None = None, proxy_url: str | None = None)`.
  - `PROXY_CONSECUTIVE_FAILURE_THRESHOLD = 3` (module constant).
  - `entries: list[ProxyEntry]`, `is_multi_proxy() -> bool`, `launch_proxy() -> dict | None`,
    `next_proxy() -> ProxyEntry | None`, `report_result(key: str, is_proxy_failure: bool) -> None`.
  - Legacy: `get_proxy()`, `get_current_proxy()`, `rotate_proxy()`, `_sanitize_url_for_logging(url) -> str`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/utils/test_proxy_manager.py`:

```python
from oddsharvester.utils.proxy_manager import PROXY_CONSECUTIVE_FAILURE_THRESHOLD, ProxyEntry


class TestMultiProxyPool:
    def test_empty_pool_is_direct(self):
        pm = ProxyManager()
        assert pm.is_multi_proxy() is False
        assert pm.launch_proxy() is None
        entry = pm.next_proxy()
        assert entry.config is None

    def test_single_proxy_launches_with_that_proxy(self):
        pm = ProxyManager(proxy_urls=["http://proxy.example.com:8080"])
        assert pm.is_multi_proxy() is False
        assert pm.launch_proxy() == {"server": "http://proxy.example.com:8080"}

    def test_multiple_proxies_launch_per_context(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        assert pm.is_multi_proxy() is True
        assert pm.launch_proxy() == {"server": "per-context"}

    def test_embedded_credentials_split_into_username_password(self):
        pm = ProxyManager(proxy_urls=["http://user:pass@a.example.com:8080"])
        entry = pm.entries[0]
        assert entry.config == {
            "server": "http://a.example.com:8080",
            "username": "user",
            "password": "pass",
        }

    def test_round_robin_cycles_entries(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        keys = [pm.next_proxy().key for _ in range(4)]
        assert keys == [
            "http://a.example.com:1",
            "http://b.example.com:2",
            "http://a.example.com:1",
            "http://b.example.com:2",
        ]

    def test_blacklist_after_threshold_skips_proxy(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        key_a = "http://a.example.com:1"
        for _ in range(PROXY_CONSECUTIVE_FAILURE_THRESHOLD):
            pm.report_result(key_a, is_proxy_failure=True)
        keys = {pm.next_proxy().key for _ in range(4)}
        assert keys == {"http://b.example.com:2"}

    def test_success_resets_failure_counter(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        key_a = "http://a.example.com:1"
        pm.report_result(key_a, is_proxy_failure=True)
        pm.report_result(key_a, is_proxy_failure=True)
        pm.report_result(key_a, is_proxy_failure=False)  # reset
        pm.report_result(key_a, is_proxy_failure=True)
        # Only 1 consecutive failure since reset -> not blacklisted
        assert any(e.key == key_a and not e.blacklisted for e in pm.entries)

    def test_all_blacklisted_returns_none(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        for key in ["http://a.example.com:1", "http://b.example.com:2"]:
            for _ in range(PROXY_CONSECUTIVE_FAILURE_THRESHOLD):
                pm.report_result(key, is_proxy_failure=True)
        assert pm.next_proxy() is None

    def test_single_proxy_never_blacklists(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1"])
        for _ in range(PROXY_CONSECUTIVE_FAILURE_THRESHOLD * 3):
            pm.report_result("http://a.example.com:1", is_proxy_failure=True)
        assert pm.next_proxy().key == "http://a.example.com:1"

    def test_multi_proxy_user_pass_ignored_with_warning(self):
        from unittest.mock import patch

        with patch("oddsharvester.utils.proxy_manager.logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            ProxyManager(
                proxy_urls=["http://a.example.com:1", "http://b.example.com:2"],
                proxy_user="u",
                proxy_pass="p",
            )
            assert any(
                "ignored with multiple proxies" in str(call)
                for call in mock_logger.warning.call_args_list
            )

    def test_entry_dataclass_defaults(self):
        entry = ProxyEntry(key="k", config=None)
        assert entry.consecutive_failures == 0
        assert entry.blacklisted is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/utils/test_proxy_manager.py::TestMultiProxyPool -q`
Expected: FAIL with `ImportError` (`ProxyEntry` / `PROXY_CONSECUTIVE_FAILURE_THRESHOLD` not defined).

- [ ] **Step 3: Rewrite the implementation**

Replace the entire contents of `src/oddsharvester/utils/proxy_manager.py` with:

```python
import logging
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

# A proxy is dropped from rotation after this many CONSECUTIVE proxy-attributable
# failures (navigation / rate-limit). The counter resets on any non-proxy outcome.
PROXY_CONSECUTIVE_FAILURE_THRESHOLD = 3

_VALID_SCHEMES = ("http://", "https://", "socks4://", "socks5://")
_DIRECT_KEY = "direct"
_PER_CONTEXT_SENTINEL = {"server": "per-context"}


@dataclass
class ProxyEntry:
    """A single proxy in the rotation pool."""

    key: str
    config: dict[str, str] | None
    consecutive_failures: int = 0
    blacklisted: bool = False


class ProxyManager:
    """Manages one or more proxies for Playwright, with round-robin rotation and failover.

    With 0 or 1 proxy the pool behaves like the legacy single-proxy manager (no
    rotation, no failover). With 2+ proxies it hands out proxies round-robin and
    blacklists any that fail repeatedly.
    """

    def __init__(
        self,
        proxy_urls: list[str] | None = None,
        proxy_user: str | None = None,
        proxy_pass: str | None = None,
        proxy_url: str | None = None,
    ):
        self.logger = logging.getLogger(self.__class__.__name__)

        urls = self._normalize_urls(proxy_urls, proxy_url)
        legacy_single = len(urls) == 1

        self.entries: list[ProxyEntry] = []
        for url in urls:
            entry = self._build_entry(
                url,
                proxy_user=proxy_user if legacy_single else None,
                proxy_pass=proxy_pass if legacy_single else None,
            )
            if entry is not None:
                self.entries.append(entry)

        if (proxy_user or proxy_pass) and not legacy_single and len(self.entries) > 1:
            self.logger.warning(
                "--proxy-user/--proxy-pass are ignored with multiple proxies; "
                "embed credentials in each proxy URL instead."
            )

        if not self.entries:
            self.logger.info("No proxy provided, running without proxy.")
            self.entries = [ProxyEntry(key=_DIRECT_KEY, config=None)]

        self._real = [e for e in self.entries if e.config is not None]
        self._failover_enabled = len(self._real) >= 2
        self._cursor = 0
        self._exhausted_logged = False

    @staticmethod
    def _normalize_urls(proxy_urls: list[str] | None, proxy_url: str | None) -> list[str]:
        if proxy_urls:
            return [u for u in proxy_urls if u]
        if proxy_url:
            return [proxy_url]
        return []

    @staticmethod
    def _sanitize_url_for_logging(url: str) -> str:
        """Strip embedded credentials from a URL for safe logging."""
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            safe = parsed._replace(netloc=f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname)
            return urlunparse(safe)
        return url

    def _build_entry(
        self,
        url: str,
        proxy_user: str | None = None,
        proxy_pass: str | None = None,
    ) -> ProxyEntry | None:
        if not any(url.startswith(scheme) for scheme in _VALID_SCHEMES):
            self.logger.error("Invalid proxy scheme provided.")
            return None

        parsed = urlparse(url)
        server = self._sanitize_url_for_logging(url)  # scheme://host:port, no creds
        config: dict[str, str] = {"server": server}

        if parsed.username and parsed.password:
            config["username"] = parsed.username
            config["password"] = parsed.password
            self.logger.info(f"Configured proxy with authentication: {server}")
        elif proxy_user and proxy_pass:
            config["username"] = proxy_user
            config["password"] = proxy_pass
            self.logger.info(f"Configured proxy with authentication: {server}")
        elif proxy_user or proxy_pass:
            self.logger.warning("Both proxy_user and proxy_pass must be provided for authentication. Ignoring auth.")
            self.logger.info(f"Configured proxy without authentication: {server}")
        else:
            self.logger.info(f"Configured proxy without authentication: {server}")

        return ProxyEntry(key=server, config=config)

    def is_multi_proxy(self) -> bool:
        return len(self._real) >= 2

    def launch_proxy(self) -> dict[str, str] | None:
        """Proxy dict for browser.launch(). The sentinel enables per-context override (>=2 proxies)."""
        if self.is_multi_proxy():
            return dict(_PER_CONTEXT_SENTINEL)
        return self.entries[0].config

    def next_proxy(self) -> ProxyEntry | None:
        """Return the next non-blacklisted proxy (round-robin), or None if all are blacklisted."""
        n = len(self.entries)
        for i in range(n):
            idx = (self._cursor + i) % n
            entry = self.entries[idx]
            if not entry.blacklisted:
                self._cursor = (idx + 1) % n
                return entry
        if not self._exhausted_logged:
            self.logger.error("All proxies are blacklisted; remaining matches will fail.")
            self._exhausted_logged = True
        return None

    def report_result(self, key: str, is_proxy_failure: bool) -> None:
        """Record the outcome of a request that used the proxy identified by `key`.

        Only active with >=2 proxies. A proxy-attributable failure increments a
        consecutive-failure counter; any other outcome resets it. Reaching the
        threshold blacklists the proxy.
        """
        if not self._failover_enabled:
            return
        entry = next((e for e in self.entries if e.key == key), None)
        if entry is None or entry.blacklisted:
            return
        if is_proxy_failure:
            entry.consecutive_failures += 1
            if entry.consecutive_failures >= PROXY_CONSECUTIVE_FAILURE_THRESHOLD:
                entry.blacklisted = True
                self.logger.warning(
                    f"Proxy blacklisted after {entry.consecutive_failures} consecutive failures: {entry.key}"
                )
        else:
            entry.consecutive_failures = 0

    # Legacy accessors (single-proxy compatibility) ---------------------------------

    def get_proxy(self) -> dict[str, str] | None:
        """Legacy: return the first entry's config (single/no-proxy compatibility)."""
        return self.entries[0].config

    def get_current_proxy(self) -> dict[str, str] | None:
        """Legacy method - use get_proxy() instead."""
        return self.get_proxy()

    def rotate_proxy(self):
        """Legacy no-op; rotation now happens per request via next_proxy()."""
        self.logger.debug("Proxy rotation handled per-request via next_proxy().")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/utils/test_proxy_manager.py -q`
Expected: PASS — both the pre-existing tests (no/single/partial-auth/scheme/sanitization/logging/legacy) and the new `TestMultiProxyPool`.

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/utils/proxy_manager.py tests/utils/test_proxy_manager.py
git commit -m "feat(proxy): rework ProxyManager into a round-robin pool with failover"
```

---

## Task 4: Multi-context support in `PlaywrightManager`

**Files:**
- Modify: `src/oddsharvester/core/playwright_manager.py`
- Modify: `src/oddsharvester/core/odds_portal_scraper.py` (`start_playwright` forwards `proxy_manager`)
- Test: `tests/core/test_playwright_manager.py`

**Interfaces:**
- Consumes: `ProxyManager` (Task 3) — `launch_proxy()`, `is_multi_proxy()`, `entries`, `next_proxy()`, `report_result()`.
- Produces on `PlaywrightManager`:
  - `initialize(self, headless, user_agent=None, locale=None, timezone_id=None, proxy_manager=None)`.
  - `self.contexts: dict[str, BrowserContext]`, `self.context` (default), `self.page` (warm-up page in default).
  - `async new_rotated_page(self) -> tuple[Page, str]` — raises `AllProxiesExhaustedError` when the pool is exhausted.
  - `async new_page_on_key(self, key: str) -> Page`.
  - `non_default_context_keys(self) -> list[str]`.
  - `report_page_result(self, key: str, is_proxy_failure: bool) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_playwright_manager.py`:

```python
from oddsharvester.core.exceptions import AllProxiesExhaustedError
from oddsharvester.utils.proxy_manager import ProxyManager


@pytest.mark.asyncio
async def test_single_context_when_no_proxy_manager(mock_playwright):
    pm = PlaywrightManager()
    await pm.initialize(headless=True)
    mock_playwright["browser"].new_context.assert_awaited_once()
    assert list(pm.contexts.keys()) == ["direct"]
    assert pm.non_default_context_keys() == []


@pytest.mark.asyncio
async def test_one_context_per_proxy_when_multi(mock_playwright):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    # Two contexts created; browser launched with the per-context sentinel.
    assert mock_playwright["browser"].new_context.await_count == 2
    assert set(pm.contexts.keys()) == {"http://a.example.com:1", "http://b.example.com:2"}
    launch_kwargs = mock_playwright["playwright"].chromium.launch.await_args.kwargs
    assert launch_kwargs["proxy"] == {"server": "per-context"}
    assert len(pm.non_default_context_keys()) == 1


@pytest.mark.asyncio
async def test_new_rotated_page_reports_key(mock_playwright):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    _page, key = await pm.new_rotated_page()
    assert key in {"http://a.example.com:1", "http://b.example.com:2"}


@pytest.mark.asyncio
async def test_new_rotated_page_raises_when_exhausted(mock_playwright):
    proxy_manager = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
    pm = PlaywrightManager()
    await pm.initialize(headless=True, proxy_manager=proxy_manager)
    for key in ["http://a.example.com:1", "http://b.example.com:2"]:
        for _ in range(3):
            pm.report_page_result(key, is_proxy_failure=True)
    with pytest.raises(AllProxiesExhaustedError):
        await pm.new_rotated_page()
```

Note: the existing `mock_playwright` fixture returns the *same* `context` mock for every `browser.new_context(...)` call, so `pm.contexts` maps every key to that shared mock — fine for these assertions.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_playwright_manager.py -q`
Expected: FAIL (`initialize` has no `proxy_manager` param / `new_rotated_page` missing).

- [ ] **Step 3: Implement multi-context support**

In `src/oddsharvester/core/playwright_manager.py`:

Add imports near the top (after existing imports):

```python
from oddsharvester.core.exceptions import AllProxiesExhaustedError
```

Replace `__init__` with:

```python
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.timezone_id: str | None = None
        self.contexts: dict = {}
        self._default_key: str | None = None
        self._proxy_manager = None
```

Replace the `initialize` method signature and body. New signature:

```python
    async def initialize(
        self,
        headless: bool,
        user_agent: str | None = None,
        locale: str | None = None,
        timezone_id: str | None = None,
        proxy_manager=None,
    ):
```

Replace the body from `self.playwright = await async_playwright().start()` through `self.page = await self.context.new_page()` with:

```python
            self.timezone_id = timezone_id
            self._proxy_manager = proxy_manager
            self.playwright = await async_playwright().start()

            browser_args = PLAYWRIGHT_BROWSER_ARGS_DOCKER if is_running_in_docker() else PLAYWRIGHT_BROWSER_ARGS
            launch_proxy = proxy_manager.launch_proxy() if proxy_manager else None
            self.browser = await self.playwright.chromium.launch(
                headless=headless, args=browser_args, proxy=launch_proxy
            )

            effective_user_agent = user_agent or random.choice(DEFAULT_USER_AGENTS)  # noqa: S311

            # (key, per-context proxy override) for each context to create.
            # Per-context proxy is used ONLY in multi-proxy mode; otherwise the
            # single context inherits the launch proxy (unchanged behavior).
            if proxy_manager and proxy_manager.is_multi_proxy():
                context_specs = [(e.key, e.config) for e in proxy_manager.entries]
            elif proxy_manager:
                context_specs = [(proxy_manager.entries[0].key, None)]
            else:
                context_specs = [("direct", None)]

            self._default_key = context_specs[0][0]
            for index, (key, ctx_proxy) in enumerate(context_specs):
                self.contexts[key] = await self._create_context(
                    proxy=ctx_proxy,
                    user_agent=effective_user_agent,
                    locale=locale,
                    timezone_id=timezone_id,
                    enable_har=(index == 0),
                )

            self.context = self.contexts[self._default_key]
            self.page = await self.context.new_page()
```

The timezone-resolution block (`if self.timezone_id is None:` ...) and the closing `self.logger.info("Playwright initialized successfully.")` / `except` stay unchanged, immediately after the code above.

Add a new `_create_context` helper method (place it after `initialize`):

```python
    async def _create_context(self, proxy, user_agent, locale, timezone_id, enable_har):
        """Create one browser context. HAR record/replay is applied to the default context only."""
        context_kwargs = {
            "locale": locale,
            "timezone_id": timezone_id,
            "user_agent": user_agent,
            "viewport": {"width": random.randint(1366, 1920), "height": random.randint(768, 1080)},  # noqa: S311
        }
        if proxy is not None:
            context_kwargs["proxy"] = proxy
        if enable_har:
            har_record_path = os.environ.get(HAR_RECORD_ENV_VAR)
            if har_record_path:
                self.logger.info(f"HAR recording mode active: {har_record_path}")
                context_kwargs["record_har_path"] = Path(har_record_path)
                context_kwargs["record_har_mode"] = "full"
                context_kwargs["record_har_url_filter"] = HAR_REPLAY_URL_PATTERN

        context = await self.browser.new_context(**context_kwargs)
        await context.add_init_script(STEALTH_SCRIPT)

        if enable_har:
            har_replay_path = os.environ.get(HAR_REPLAY_ENV_VAR)
            if har_replay_path:
                self.logger.info(f"HAR replay mode active: {har_replay_path}")
                await context.route_from_har(
                    Path(har_replay_path),
                    url=HAR_REPLAY_URL_PATTERN,
                    not_found="abort",
                )
        return context
```

Add the rotation helpers (place after `_create_context`, before `cleanup`):

```python
    def non_default_context_keys(self) -> list[str]:
        """Keys of proxy contexts other than the default one (empty for single/no-proxy)."""
        return [key for key in self.contexts if key != self._default_key]

    async def new_page_on_key(self, key: str):
        """Open a new page in the context bound to a specific proxy key."""
        return await self.contexts[key].new_page()

    async def new_rotated_page(self):
        """Open a page on the next round-robin proxy. Returns (page, proxy_key).

        Raises AllProxiesExhaustedError if every proxy is blacklisted.
        """
        if self._proxy_manager is None:
            return await self.context.new_page(), self._default_key
        entry = self._proxy_manager.next_proxy()
        if entry is None:
            raise AllProxiesExhaustedError("All proxies are blacklisted; cannot open a new page.")
        page = await self.contexts[entry.key].new_page()
        return page, entry.key

    def report_page_result(self, key: str, is_proxy_failure: bool) -> None:
        """Forward a per-page outcome to the proxy pool (no-op without a proxy manager)."""
        if self._proxy_manager is not None:
            self._proxy_manager.report_result(key, is_proxy_failure)
```

Update `cleanup` to close all contexts. Replace the `if self.context:` block:

```python
        for context in self.contexts.values():
            await context.close()
```

(Leave the `self.page` close before it and the `self.browser` / `self.playwright` blocks after it unchanged. `self.context` is one of `self.contexts.values()`, so drop the standalone `if self.context: await self.context.close()` line to avoid a double close.)

Then in `src/oddsharvester/core/odds_portal_scraper.py`, update `start_playwright` (lines 41-62): change the `proxy` parameter to `proxy_manager` and forward it:

```python
    async def start_playwright(
        self,
        headless: bool = True,
        browser_user_agent: str | None = None,
        browser_locale_timezone: str | None = None,
        browser_timezone_id: str | None = None,
        proxy_manager=None,
    ):
        """Initializes Playwright using PlaywrightManager."""
        await self.playwright_manager.initialize(
            headless=headless,
            user_agent=browser_user_agent,
            locale=browser_locale_timezone,
            timezone_id=browser_timezone_id,
            proxy_manager=proxy_manager,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_playwright_manager.py -q`
Expected: PASS (existing HAR/timezone tests + new multi-context tests).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/playwright_manager.py src/oddsharvester/core/odds_portal_scraper.py tests/core/test_playwright_manager.py
git commit -m "feat(playwright): one context per proxy with rotation helpers"
```

---

## Task 5: Rotate + warm contexts in `BaseScraper`

**Files:**
- Modify: `src/oddsharvester/core/base_scraper.py`
- Test: `tests/core/test_base_scraper.py` (update the fixture; add rotation/warm tests)

**Interfaces:**
- Consumes: `PlaywrightManager.new_rotated_page()`, `new_page_on_key()`, `non_default_context_keys()`, `report_page_result()` (Task 4); `is_proxy_attributable_error` (Task 1).
- Produces: `BaseScraper._warmed_proxy_keys: set[str]`; warmed contexts + per-match rotation inside `extract_match_odds`.

- [ ] **Step 1: Update the fixture and write failing tests**

In `tests/core/test_base_scraper.py`, in the fixture that builds `playwright_manager_mock` (around lines 28-45), after `playwright_manager_mock.context = context_mock`, add:

```python
    playwright_manager_mock.new_rotated_page = AsyncMock(return_value=(page_mock, "direct"))
    playwright_manager_mock.new_page_on_key = AsyncMock(return_value=page_mock)
    playwright_manager_mock.non_default_context_keys = MagicMock(return_value=[])
    playwright_manager_mock.report_page_result = MagicMock()
```

Add a new test (uses the same fixture; adjust the fixture key name if the fixture returns a dict — match the existing pattern in the file):

```python
@pytest.mark.asyncio
async def test_extract_match_odds_warms_non_default_contexts(scraper_setup):
    scraper = scraper_setup["scraper"]
    pm = scraper_setup["playwright_manager_mock"]
    pm.non_default_context_keys = MagicMock(return_value=["http://b.example.com:2"])

    await scraper.extract_match_odds(sport="football", match_links=[], markets=["1x2"])

    pm.new_page_on_key.assert_awaited_with("http://b.example.com:2")
    assert "http://b.example.com:2" in scraper._warmed_proxy_keys


@pytest.mark.asyncio
async def test_extract_match_odds_uses_rotated_page(scraper_setup):
    scraper = scraper_setup["scraper"]
    pm = scraper_setup["playwright_manager_mock"]

    await scraper.extract_match_odds(
        sport="football", match_links=["https://www.oddsportal.com/football/x/y/#z"], markets=["1x2"]
    )

    pm.new_rotated_page.assert_awaited()
    pm.report_page_result.assert_called()
```

(Use whatever the fixture's actual name/return is in this file — the existing tests reference it; mirror that exact pattern. If the fixture returns the scraper directly, adapt the two lines that fetch `scraper`/`pm`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_base_scraper.py -q`
Expected: FAIL — `_warmed_proxy_keys` missing / `new_rotated_page` not awaited (the code still calls `context.new_page()`).

- [ ] **Step 3: Implement rotation + warming**

In `src/oddsharvester/core/base_scraper.py`:

Update the retry import (line 23) to also import the helper:

```python
from oddsharvester.core.retry import (
    RetryConfig,
    classify_error,
    is_proxy_attributable_error,
    is_retryable_error,
    retry_with_backoff,
)
```

In `BaseScraper.__init__` (around line 222-228), after `self.base_url = base_url`, add:

```python
        self._warmed_proxy_keys: set[str] = set()
```

Add a warm-up method (place it just before `extract_match_odds`):

```python
    async def _warm_proxy_contexts(self):
        """Warm each non-default proxy context once.

        Odds format and cookie consent are per-context state. Without this, match
        pages loaded on a fresh proxy context would render with the wrong odds
        format, silently corrupting odds values.
        """
        for key in self.playwright_manager.non_default_context_keys():
            if key in self._warmed_proxy_keys:
                continue
            self._warmed_proxy_keys.add(key)
            page = None
            try:
                page = await self.playwright_manager.new_page_on_key(key)
                await page.goto(ODDSPORTAL_BASE_URL, timeout=NAVIGATION_TIMEOUT_MS, wait_until="domcontentloaded")
                await self.cookie_dismisser.dismiss(page=page)
                await self.set_odds_format(page=page)
                self.logger.info(f"Warmed proxy context: {key}")
            except Exception as e:
                self.logger.warning(f"Failed to warm proxy context {key}: {e}")
                self.playwright_manager.report_page_result(key, is_proxy_failure=True)
            finally:
                if page:
                    await page.close()
```

At the very start of `extract_match_odds` body (right after the docstring, before `self.logger.info(f"Starting to scrape odds for ...")`), add:

```python
        await self._warm_proxy_contexts()
```

In `scrape_with_semaphore`, replace the page-acquisition and result-reporting. Change:

```python
                tab = None

                try:
                    tab = await self.playwright_manager.context.new_page()
```

to:

```python
                tab = None
                proxy_key = None

                try:
                    tab, proxy_key = await self.playwright_manager.new_rotated_page()
```

In the same function, in the success branch (right before `return (link, retry_result.result, None)`), add:

```python
                        self.playwright_manager.report_page_result(proxy_key, is_proxy_failure=False)
```

In the post-retry failure branch (right before `return (link, None, failed_url)` that follows the `error_type = ...` assignment), add:

```python
                        self.playwright_manager.report_page_result(
                            proxy_key, is_proxy_failure=is_proxy_attributable_error(error_type)
                        )
```

In the outer `except Exception as e:` block, after `error_message = str(e)` and the `failed_url = FailedUrl(...)` construction, add (before `return (link, None, failed_url)`):

```python
                    if proxy_key is not None:
                        self.playwright_manager.report_page_result(
                            proxy_key,
                            is_proxy_failure=is_proxy_attributable_error(classify_error(error_message)),
                        )
```

(`ODDSPORTAL_BASE_URL` and `NAVIGATION_TIMEOUT_MS` are already imported in `base_scraper.py`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_base_scraper.py -q`
Expected: PASS (updated fixture + new tests + all existing match-scraping tests).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/base_scraper.py tests/core/test_base_scraper.py
git commit -m "feat(scraper): rotate per-match pages across proxies and warm each context"
```

---

## Task 6: Wire the proxy list through `scraper_app`

**Files:**
- Modify: `src/oddsharvester/core/scraper_app.py`
- Test: `tests/core/test_scraper_app.py`

**Interfaces:**
- Consumes: `ProxyManager(proxy_urls=...)` (Task 3), `start_playwright(proxy_manager=...)` (Task 4).
- Produces: `run_scraper` accepts `proxy_url` as either a `str` (legacy) or a `list`/`tuple` (multi) and builds one `ProxyManager` from it, passing it to `start_playwright`.

- [ ] **Step 1: Write the failing test**

Add to `tests/core/test_scraper_app.py` (mirror the existing mocking style in that file — it already patches `OddsPortalScraper`/`start_playwright`):

```python
@pytest.mark.asyncio
async def test_run_scraper_builds_multi_proxy_manager(monkeypatch):
    from oddsharvester.core import scraper_app

    captured = {}

    class DummyScraper:
        def __init__(self, *a, **k):
            pass

        async def start_playwright(self, **kwargs):
            captured["proxy_manager"] = kwargs.get("proxy_manager")

        async def scrape_upcoming(self, *a, **k):
            from oddsharvester.core.scrape_result import ScrapeResult

            return ScrapeResult()

        async def stop_playwright(self):
            pass

    monkeypatch.setattr(scraper_app, "OddsPortalScraper", DummyScraper)

    await scraper_app.run_scraper(
        command="scrape_upcoming",
        sport="football",
        date="20250101",
        markets=["1x2"],
        proxy_url=("http://a.example.com:1", "http://b.example.com:2"),
    )

    assert captured["proxy_manager"].is_multi_proxy() is True
```

(If `test_scraper_app.py` already has a helper/fixture for building a fake scraper, reuse it instead of `DummyScraper` and just assert on the captured `proxy_manager`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_scraper_app.py::test_run_scraper_builds_multi_proxy_manager -q`
Expected: FAIL (`start_playwright` still receives `proxy=`, not `proxy_manager=`).

- [ ] **Step 3: Implement the wiring**

In `src/oddsharvester/core/scraper_app.py`:

Replace the `ProxyManager` construction (line 90):

```python
    if isinstance(proxy_url, list | tuple):
        proxy_manager = ProxyManager(proxy_urls=list(proxy_url), proxy_user=proxy_user, proxy_pass=proxy_pass)
    else:
        proxy_manager = ProxyManager(proxy_url=proxy_url, proxy_user=proxy_user, proxy_pass=proxy_pass)
```

Replace the proxy-config extraction + `start_playwright` call (lines 115-122):

```python
        await scraper.start_playwright(
            headless=headless,
            browser_user_agent=browser_user_agent,
            browser_locale_timezone=browser_locale_timezone,
            browser_timezone_id=browser_timezone_id,
            proxy_manager=proxy_manager,
        )
```

(Delete the now-unused `proxy_config = proxy_manager.get_current_proxy()` line.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_scraper_app.py -q`
Expected: PASS. If a pre-existing test asserts `start_playwright` was called with `proxy=`, update that assertion to `proxy_manager=` (behavior change is intentional).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/scraper_app.py tests/core/test_scraper_app.py
git commit -m "feat(scraper-app): build ProxyManager from a proxy list and pass it through"
```

---

## Task 7: CLI — repeatable `--proxy-url` + embedded credentials

**Files:**
- Modify: `src/oddsharvester/cli/validators.py`
- Modify: `src/oddsharvester/cli/options.py`
- Test: `tests/cli/test_validators_proxy.py` (new)

**Interfaces:**
- Consumes: `run_scraper` now accepts a tuple for `proxy_url` (Task 6). Commands already pass `proxy_url=kwargs.get("proxy_url")` — no change needed there.
- Produces: `validate_proxy_url(ctx, param, value)` accepts a tuple of URLs (from `multiple=True`), each optionally carrying `user:pass@`; returns the validated tuple.

- [ ] **Step 1: Write the failing tests**

Create `tests/cli/test_validators_proxy.py`:

```python
import click
import pytest

from oddsharvester.cli.validators import validate_proxy_url


def test_accepts_empty():
    assert validate_proxy_url(None, None, ()) == ()


def test_accepts_single_without_credentials():
    assert validate_proxy_url(None, None, ("http://proxy.example.com:8080",)) == (
        "http://proxy.example.com:8080",
    )


def test_accepts_embedded_credentials():
    value = ("http://user:pass@proxy.example.com:8080",)
    assert validate_proxy_url(None, None, value) == value


def test_accepts_multiple():
    value = ("http://a.example.com:1", "socks5://b.example.com:2")
    assert validate_proxy_url(None, None, value) == value


def test_rejects_bad_scheme():
    with pytest.raises(click.BadParameter):
        validate_proxy_url(None, None, ("ftp://proxy.example.com:8080",))


def test_rejects_missing_port():
    with pytest.raises(click.BadParameter):
        validate_proxy_url(None, None, ("http://proxy.example.com",))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_validators_proxy.py -q`
Expected: FAIL — the current validator treats `value` as a string and rejects a tuple / embedded creds.

- [ ] **Step 3: Implement the validator + option change**

In `src/oddsharvester/cli/validators.py`, replace `validate_proxy_url`:

```python
def validate_proxy_url(ctx, param, value):
    """Validate one or more proxy URLs (repeatable option → tuple).

    Each URL may carry embedded credentials: scheme://[user:pass@]host:port.
    """
    if not value:
        return value

    proxy_pattern = re.compile(
        r"^(?P<scheme>https?|socks5|socks4)://"
        r"(?:(?P<user>[^:@/]+):(?P<pass>[^:@/]+)@)?"
        r"(?P<host>[\w.-]+):(?P<port>\d+)$"
    )

    for url in value:
        if not proxy_pattern.match(url):
            raise click.BadParameter(
                f"Invalid proxy URL '{url}'. Expected format: "
                "'http[s]://host:port', 'socks5://host:port', or "
                "'scheme://user:pass@host:port'"
            )

    return value
```

In `src/oddsharvester/cli/options.py`, update the `--proxy-url` option (lines 136-142) to add `multiple=True`:

```python
    @click.option(
        "--proxy-url",
        "proxy_url",
        multiple=True,
        callback=validate_proxy_url,
        envvar="OH_PROXY_URL",
        help="Proxy URL (repeatable). Format: http[s]://host:port, socks5://host:port, "
        "or scheme://user:pass@host:port. Repeat to spread load across proxies.",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_validators_proxy.py tests/utils/test_click_cli.py -q`
Expected: PASS. If `test_click_cli.py` asserts `proxy_url` is a string, update it to expect a tuple (the option is now `multiple`).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/cli/validators.py src/oddsharvester/cli/options.py tests/cli/test_validators_proxy.py
git commit -m "feat(cli): repeatable --proxy-url with embedded-credential support"
```

---

## Task 8: Full suite + docs + gotcha

**Files:**
- Modify: `README.md`
- Modify: `docs/agentic-gotchas.md`
- Test: full unit suite

- [ ] **Step 1: Run the full unit suite (regression gate)**

Run: `uv run pytest tests/ -q --ignore=tests/integration/`
Expected: PASS. Fix any regression before proceeding.

- [ ] **Step 2: Lint/format**

Run: `uv run ruff format . && uv run ruff check --fix src/`
Expected: clean.

- [ ] **Step 3: Document usage in README**

In `README.md`, find the proxy documentation (search for `--proxy-url`) and update it to state that `--proxy-url` is repeatable, that each may include embedded credentials, that `--proxy-user`/`--proxy-pass` apply only to a single proxy, and add an example:

```bash
oddsharvester historic --sport football --leagues england-premier-league --season 2013-2014 \
  --markets 1x2 --concurrency 6 \
  --proxy-url http://user:pass@p1.example.com:8000 \
  --proxy-url http://user:pass@p2.example.com:8000 \
  --proxy-url http://user:pass@p3.example.com:8000
```

Note the behavior: matches are spread round-robin across the proxies; a proxy that fails 3 times in a row is dropped from rotation.

- [ ] **Step 4: Record the per-context warm-up gotcha**

Append an entry to `docs/agentic-gotchas.md` describing: odds format and cookie consent are per-`BrowserContext` state; with multi-proxy rotation each proxy gets its own context, so each context must be warmed (navigate to `ODDSPORTAL_BASE_URL`, dismiss cookies, `set_odds_format`) before scraping through it, otherwise match pages render in a non-decimal odds format and odds values are silently wrong.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/agentic-gotchas.md
git commit -m "docs: document multi-proxy usage and per-context warm-up gotcha"
```

---

## Task 9: Real-condition smoke validation (manual — NOT in the automated suite)

**Files:**
- Create: `scripts/fetch_free_proxies.py` (helper for the manual run; not imported by the package)

**Goal:** Exercise rotation + failover against live OddsPortal with real free proxies. Free proxies are volatile, so this is a one-off manual check, never wired into pytest.

- [ ] **Step 1: Write a free-proxy fetch helper**

Create `scripts/fetch_free_proxies.py`:

```python
"""Fetch a few currently-listed free HTTP proxies for MANUAL smoke testing only.

Free proxies are volatile and unauthenticated; never use this in the test suite or
in production. Prints `--proxy-url http://host:port` lines ready to paste.

Usage: uv run python scripts/fetch_free_proxies.py --limit 5
"""

import argparse
import urllib.request

PROXYSCRAPE_URL = (
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all"
)


def fetch(limit: int) -> list[str]:
    with urllib.request.urlopen(PROXYSCRAPE_URL, timeout=20) as resp:  # noqa: S310
        raw = resp.read().decode("utf-8", errors="ignore")
    proxies = [line.strip() for line in raw.splitlines() if line.strip()]
    return proxies[:limit]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    for hostport in fetch(args.limit):
        print(f"--proxy-url http://{hostport}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Fetch proxies and run a rotation smoke test**

```bash
uv run python scripts/fetch_free_proxies.py --limit 4
```

Pick 2-3 that respond, then run a small scrape with concurrency ≥ number of proxies and headful logging:

```bash
uv run oddsharvester upcoming --sport football --leagues england-premier-league \
  --markets 1x2 --concurrency 4 --format json -o /tmp/mp_smoke \
  --proxy-url http://<p1> --proxy-url http://<p2> --proxy-url http://<p3>
```

Verify in the logs: `Configured proxy without authentication` for each; `Warmed proxy context:` for the non-default ones; and that scraping proceeds. Confirm the output JSON has coherent decimal odds (warm-up worked).

- [ ] **Step 3: Force a failover**

Add one deliberately dead proxy and confirm it gets blacklisted while the run continues:

```bash
uv run oddsharvester upcoming --sport football --leagues england-premier-league \
  --markets 1x2 --concurrency 4 --format json -o /tmp/mp_failover \
  --proxy-url http://<good-p1> --proxy-url http://<good-p2> --proxy-url http://127.0.0.1:1
```

Expected log: `Proxy blacklisted after 3 consecutive failures: http://127.0.0.1:1`, with the run still producing results via the healthy proxies. (If all free proxies happen to die, you'll instead see `All proxies are blacklisted; remaining matches will fail.` — also a valid observation of the exhausted path.)

- [ ] **Step 4: Record findings + commit the helper**

Note the observed rotation/failover behavior in the PR description. If any new OddsPortal proxy/block behavior surfaced, append it to `docs/agentic-gotchas.md`.

```bash
git add scripts/fetch_free_proxies.py
git commit -m "chore(scripts): add free-proxy fetch helper for manual multi-proxy smoke test"
```

---

## Self-Review notes

- **Spec coverage:** CLI repeatable input (Task 7); round-robin assignment (Task 3 `next_proxy`); failover/blacklist (Task 3 `report_result`, ≥2-proxy guard); per-match rotation (Task 5); per-context warm-up (Task 5); parse embedded creds into `username`/`password` (Task 3); tests + regression gate (all tasks + Task 8); manual real-proxy validation (Task 9).
- **Backward compatibility:** no-proxy and single-proxy paths keep one context, no failover, and identical logging — guarded by the untouched existing tests in Tasks 3-6.
- **Type consistency:** `next_proxy()` returns `ProxyEntry | None`; `report_result(key, is_proxy_failure: bool)`; `new_rotated_page()` returns `(Page, str)`; `report_page_result(key, is_proxy_failure: bool)` — used consistently across Tasks 3-6.
