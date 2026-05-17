# Regional OddsPortal `--base-url` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--base-url` CLI option that retargets the scraper at a regional OddsPortal mirror (e.g. `https://www.centroquote.it`) by swapping scheme+host at runtime, with no behavior change for the default `.com` path.

**Architecture:** A pure `rebase_url(url, base_url)` helper swaps the scheme+host of any resolved URL. It is applied at the three URL-construction points (`URLBuilder` methods + the listing-page match-link join). `base_url` threads through the existing config path: CLI option → `run_scraper` kwarg → `OddsPortalScraper` constructor → `self.base_url`. A non-blocking warning fires when the region likely mismatches an unset locale/timezone. The 100+ absolute league URLs in `sport_league_constants.py` are left untouched.

**Tech Stack:** Python 3.12, Click, pytest, `urllib.parse`. Work happens in the existing worktree `../OddsHarvester-regional-base-url` on branch `feat/regional-base-url` (off `master`).

**Spec:** `docs/specs/2026-05-17-regional-base-url-design.md`

**Run all unit tests with:** `uv run pytest tests/ -q --ignore=tests/integration/` (from the worktree root).

---

## File Structure

- `src/oddsharvester/core/url_builder.py` — add `rebase_url` helper + `base_url` kwarg on the three `URLBuilder` methods.
- `src/oddsharvester/core/base_scraper.py` — `BaseScraper.__init__` stores `self.base_url`; `extract_match_links` uses it for the match-link join.
- `src/oddsharvester/core/odds_portal_scraper.py` — pass `self.base_url` into the two `URLBuilder` call sites.
- `src/oddsharvester/core/scraper_app.py` — `run_scraper` gains `base_url` param, forwards it to `OddsPortalScraper`, emits the mismatch warning.
- `src/oddsharvester/cli/validators.py` — `validate_base_url` callback.
- `src/oddsharvester/cli/options.py` — `--base-url` option in `common_options`.
- `src/oddsharvester/cli/commands/historic.py`, `upcoming.py` — forward `base_url` kwarg to `run_scraper`.
- `tests/core/test_url_builder.py` — extend with `rebase_url` + `base_url` cases.
- `tests/core/test_base_scraper.py` — extend with match-link join case.
- `tests/cli/test_validators_base_url.py` — new file for the validator.
- `tests/core/test_scraper_app_base_url.py` — new file for the warning.
- `README.md`, `docs/agentic-gotchas.md` — docs.

---

### Task 1: `rebase_url` helper

**Files:**
- Modify: `src/oddsharvester/core/url_builder.py`
- Test: `tests/core/test_url_builder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_url_builder.py` (after the existing imports/mapping block; add `rebase_url` to the `url_builder` import line so it reads `from oddsharvester.core.url_builder import URLBuilder, rebase_url`):

```python
class TestRebaseUrl:
    def test_none_base_url_returns_unchanged(self):
        url = "https://www.oddsportal.com/football/england/premier-league/results/"
        assert rebase_url(url, None) == url

    def test_empty_base_url_returns_unchanged(self):
        url = "https://www.oddsportal.com/football/england/premier-league/results/"
        assert rebase_url(url, "") == url

    def test_swaps_scheme_and_host_preserving_path_query_fragment(self):
        url = "https://www.oddsportal.com/football/italy/serie-a/results/?foo=1#bar"
        assert rebase_url(url, "https://www.centroquote.it") == (
            "https://www.centroquote.it/football/italy/serie-a/results/?foo=1#bar"
        )

    def test_preserves_http_scheme_from_base_url(self):
        url = "https://www.oddsportal.com/tennis/atp-tour/"
        assert rebase_url(url, "http://mirror.example.com") == "http://mirror.example.com/tennis/atp-tour/"

    def test_trailing_slash_on_base_url_does_not_double(self):
        url = "https://www.oddsportal.com/football/spain/laliga"
        assert rebase_url(url, "https://www.centroquote.it/") == "https://www.centroquote.it/football/spain/laliga"

    def test_idempotent(self):
        url = "https://www.oddsportal.com/football/france/ligue-1/results/"
        once = rebase_url(url, "https://www.centroquote.it")
        assert rebase_url(once, "https://www.centroquote.it") == once
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_url_builder.py::TestRebaseUrl -q`
Expected: FAIL — `ImportError: cannot import name 'rebase_url'`.

- [ ] **Step 3: Implement `rebase_url`**

In `src/oddsharvester/core/url_builder.py`, add the import at the top (after `import re`):

```python
from urllib.parse import urlsplit, urlunsplit
```

Add this module-level function after the imports and before `class URLBuilder:`:

```python
def rebase_url(url: str, base_url: str | None) -> str:
    """
    Swap the scheme and host of ``url`` with those of ``base_url``.

    Path, query, and fragment are preserved exactly. When ``base_url`` is None
    or empty, ``url`` is returned unchanged (the default oddsportal.com path).
    Idempotent. ``base_url`` is expected to be host-only (validated upstream).
    """
    if not base_url:
        return url

    base = urlsplit(base_url)
    parts = urlsplit(url)
    return urlunsplit((base.scheme, base.netloc, parts.path, parts.query, parts.fragment))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_url_builder.py::TestRebaseUrl -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/url_builder.py tests/core/test_url_builder.py
git commit -m "feat: add rebase_url helper for regional domain swap"
```

---

### Task 2: `base_url` kwarg on `URLBuilder` methods

**Files:**
- Modify: `src/oddsharvester/core/url_builder.py`
- Test: `tests/core/test_url_builder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_url_builder.py`:

```python
class TestUrlBuilderBaseUrl:
    BASE = "https://www.centroquote.it"

    def test_get_league_url_default_unchanged(self):
        url = URLBuilder.get_league_url("football", "england-premier-league")
        assert url.startswith("https://www.oddsportal.com/")

    def test_get_league_url_rebased(self):
        url = URLBuilder.get_league_url("football", "england-premier-league", base_url=self.BASE)
        assert url == f"{self.BASE}/football/england/premier-league"

    def test_get_historic_matches_url_rebased_with_season(self):
        url = URLBuilder.get_historic_matches_url(
            sport="football", league="england-premier-league", season="2021-2022", base_url=self.BASE
        )
        assert url == f"{self.BASE}/football/england/premier-league-2021-2022/results/"

    def test_get_historic_matches_url_rebased_current_season(self):
        url = URLBuilder.get_historic_matches_url(
            sport="football", league="england-premier-league", season="current", base_url=self.BASE
        )
        assert url == f"{self.BASE}/football/england/premier-league/results/"

    def test_get_historic_matches_url_baseball_special_case_rebased(self):
        url = URLBuilder.get_historic_matches_url(
            sport="baseball", league="mlb", season="2022-2023", base_url=self.BASE
        )
        assert url == f"{self.BASE}/baseball/usa/mlb-2022/results/"

    def test_get_upcoming_matches_url_no_league_rebased(self):
        url = URLBuilder.get_upcoming_matches_url(sport="football", date="2025-01-15", base_url=self.BASE)
        assert url == f"{self.BASE}/matches/football/2025-01-15/"

    def test_get_upcoming_matches_url_with_league_rebased(self):
        url = URLBuilder.get_upcoming_matches_url(
            sport="football", date="2025-01-15", league="england-premier-league", base_url=self.BASE
        )
        assert url == f"{self.BASE}/football/england/premier-league"

    def test_default_calls_have_no_regression(self):
        assert URLBuilder.get_upcoming_matches_url(sport="football", date="2025-01-15").startswith(
            "https://www.oddsportal.com/"
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_url_builder.py::TestUrlBuilderBaseUrl -q`
Expected: FAIL — `TypeError: ... got an unexpected keyword argument 'base_url'`.

- [ ] **Step 3: Add `base_url` to the three methods**

In `src/oddsharvester/core/url_builder.py`:

`get_historic_matches_url` — change the signature line and wrap every `return`:

```python
    @staticmethod
    def get_historic_matches_url(
        sport: str, league: str, season: str | None = None, base_url: str | None = None
    ) -> str:
```

Replace each `return f"..."` / `return f"{base_url}/results/"` body so the final value is rebased. The cleanest edit: rename the existing local variable `base_url` (it shadows the new param) to `league_url`, then rebase at every return. Concretely:

- Line `base_url = URLBuilder.get_league_url(sport, league).rstrip("/")` → `league_url = URLBuilder.get_league_url(sport, league).rstrip("/")`
- Every subsequent reference to the local `base_url` becomes `league_url`.
- Wrap each returned string in `rebase_url(..., base_url)`. Final method body:

```python
        if isinstance(season, str) and season.lower() == "current":
            season = None

        league_url = URLBuilder.get_league_url(sport, league).rstrip("/")

        alias_slug = get_league_slug_for_season(Sport(sport), league, season)
        if alias_slug:
            league_url = league_url.rsplit("/", 1)[0] + "/" + alias_slug

        if not season:
            return rebase_url(f"{league_url}/results/", base_url)

        if re.match(r"^\d{4}$", season):
            return rebase_url(f"{league_url}-{season}/results/", base_url)

        if re.match(r"^\d{4}-\d{4}$", season):
            start_year, end_year = map(int, season.split("-"))
            if end_year != start_year + 1:
                raise ValueError(
                    f"Invalid season range: {season}. The second year must be exactly one year after the first."
                )

            if sport.lower() == "baseball":
                return rebase_url(f"{league_url}-{start_year}/results/", base_url)

            current_year = datetime.now(UTC).year
            if end_year == current_year:
                return rebase_url(f"{league_url}/results/", base_url)

            return rebase_url(f"{league_url}-{season}/results/", base_url)

        raise ValueError(f"Invalid season format: {season}. Expected format: 'YYYY' or 'YYYY-YYYY'")
```

`get_upcoming_matches_url`:

```python
    @staticmethod
    def get_upcoming_matches_url(
        sport: str, date: str, league: str | None = None, base_url: str | None = None
    ) -> str:
        if league:
            return URLBuilder.get_league_url(sport, league, base_url=base_url)
        return rebase_url(f"{ODDSPORTAL_BASE_URL}/matches/{sport}/{date}/", base_url)
```

`get_league_url`:

```python
    @staticmethod
    def get_league_url(sport: str, league: str, base_url: str | None = None) -> str:
```

and change its final `return leagues[league]` to:

```python
        return rebase_url(leagues[league], base_url)
```

(Keep all existing docstrings/validation logic in these methods intact — only the signature, the variable rename in `get_historic_matches_url`, and the return wrapping change.)

- [ ] **Step 4: Run the full url_builder suite to verify pass + no regression**

Run: `uv run pytest tests/core/test_url_builder.py -q`
Expected: PASS (all existing tests + `TestRebaseUrl` + `TestUrlBuilderBaseUrl`).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/url_builder.py tests/core/test_url_builder.py
git commit -m "feat: thread base_url through URLBuilder methods"
```

---

### Task 3: `BaseScraper` stores `base_url`; match-link join uses it

**Files:**
- Modify: `src/oddsharvester/core/base_scraper.py` (`__init__` ~line 174, `extract_match_links` ~line 312)
- Test: `tests/core/test_base_scraper.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/core/test_base_scraper.py` (reuse the file's existing BaseScraper construction/mocking style — if a fixture builds a `BaseScraper` with mocked collaborators, instantiate the same way and pass `base_url=`). Add:

```python
class TestBaseScraperBaseUrl:
    def test_base_url_defaults_to_none(self):
        scraper = _make_base_scraper()  # existing helper/fixture pattern in this file
        assert scraper.base_url is None

    def test_base_url_is_stored(self):
        scraper = _make_base_scraper(base_url="https://www.centroquote.it")
        assert scraper.base_url == "https://www.centroquote.it"

    @pytest.mark.asyncio
    async def test_extract_match_links_uses_default_domain(self):
        scraper = _make_base_scraper()
        page = _fake_page_with_event_row(href="/football/italy/serie-a/match-xyz/")
        links = await scraper.extract_match_links(page)
        assert links == ["https://www.oddsportal.com/football/italy/serie-a/match-xyz/"]

    @pytest.mark.asyncio
    async def test_extract_match_links_uses_base_url(self):
        scraper = _make_base_scraper(base_url="https://www.centroquote.it")
        page = _fake_page_with_event_row(href="/football/italy/serie-a/match-xyz/")
        links = await scraper.extract_match_links(page)
        assert links == ["https://www.centroquote.it/football/italy/serie-a/match-xyz/"]
```

> NOTE for the implementer: `tests/core/test_base_scraper.py` already exercises `extract_match_links`. Locate the existing helper/fixture that builds a `BaseScraper` and the existing page-content mocking approach (search the file for `extract_match_links` and `BeautifulSoup`/`page.content`). Reuse that exact pattern for `_make_base_scraper` and `_fake_page_with_event_row` instead of inventing new mocks. The `href` must have ≥4 path segments (the code skips `len(href.strip("/").split("/")) <= 3`), so `/football/italy/serie-a/match-xyz/` (4 segments) is valid.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_base_scraper.py::TestBaseScraperBaseUrl -q`
Expected: FAIL — `AttributeError: 'BaseScraper' object has no attribute 'base_url'` (and the base_url case asserts the wrong domain).

- [ ] **Step 3: Add `base_url` to `__init__` and use it in the join**

In `src/oddsharvester/core/base_scraper.py`, `BaseScraper.__init__` — add the parameter (after `preview_submarkets_only: bool = False,`):

```python
        preview_submarkets_only: bool = False,
        base_url: str | None = None,
```

Add to the docstring Args a line:

```
            base_url (str | None): Regional OddsPortal domain override (scheme+host).
            When None, the canonical https://www.oddsportal.com is used.
```

Add the attribute assignment next to the others:

```python
        self.preview_submarkets_only = preview_submarkets_only
        self.base_url = base_url
```

In `extract_match_links`, change line 312:

```python
                    full_url = f"{ODDSPORTAL_BASE_URL}{href}"
```

to:

```python
                    full_url = f"{self.base_url or ODDSPORTAL_BASE_URL}{href}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_base_scraper.py::TestBaseScraperBaseUrl -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/base_scraper.py tests/core/test_base_scraper.py
git commit -m "feat: BaseScraper stores base_url and applies it to match-link join"
```

---

### Task 4: `OddsPortalScraper` passes `self.base_url` to `URLBuilder`

**Files:**
- Modify: `src/oddsharvester/core/odds_portal_scraper.py` (call sites ~line 101 and ~line 170)
- Test: `tests/core/test_url_builder.py` already covers `URLBuilder` behavior; this task is a wiring change verified by the integration of Tasks 2+3. Add a focused unit test below.
- Test: `tests/core/test_base_scraper.py`

- [ ] **Step 1: Write the failing test**

`OddsPortalScraper.scrape_historic`/`scrape_upcoming` are async and drive Playwright, so unit-test only the URL wiring by asserting the `URLBuilder` calls receive `base_url`. Append to `tests/core/test_base_scraper.py`:

```python
class TestOddsPortalScraperUrlWiring:
    def test_scrape_historic_passes_base_url_to_url_builder(self, monkeypatch):
        from oddsharvester.core import odds_portal_scraper as ops

        captured = {}

        def fake_get_historic(sport, league, season=None, base_url=None):
            captured["base_url"] = base_url
            return "https://www.centroquote.it/football/italy/serie-a/results/"

        monkeypatch.setattr(ops.URLBuilder, "get_historic_matches_url", staticmethod(fake_get_historic))
        scraper = _make_odds_portal_scraper(base_url="https://www.centroquote.it")
        # Call only the URL-building line via the same expression used in scrape_historic:
        result = ops.URLBuilder.get_historic_matches_url(
            sport="football", league="italy-serie-a", season="current", base_url=scraper.base_url
        )
        assert captured["base_url"] == "https://www.centroquote.it"
        assert result.startswith("https://www.centroquote.it/")
```

> NOTE for the implementer: `_make_odds_portal_scraper` should mirror the existing `OddsPortalScraper` construction pattern in the test file (same mocked collaborators as `_make_base_scraper`, just the `OddsPortalScraper` subclass), passing `base_url=`. This test guards the contract; the wiring edit in Step 3 makes the real call sites use `self.base_url`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_base_scraper.py::TestOddsPortalScraperUrlWiring -q`
Expected: FAIL — `_make_odds_portal_scraper` not defined / `base_url` not accepted (until helper added; the helper just calls the `OddsPortalScraper(...)` constructor which inherits `base_url` from Task 3).

- [ ] **Step 3: Wire the two call sites**

In `src/oddsharvester/core/odds_portal_scraper.py`:

Line ~101 (in `scrape_historic`):

```python
        base_url = URLBuilder.get_historic_matches_url(sport=sport, league=league, season=season)
```

→

```python
        base_url = URLBuilder.get_historic_matches_url(
            sport=sport, league=league, season=season, base_url=self.base_url
        )
```

Line ~170 (in `scrape_upcoming`):

```python
        url = URLBuilder.get_upcoming_matches_url(sport=sport, date=date, league=league)
```

→

```python
        url = URLBuilder.get_upcoming_matches_url(
            sport=sport, date=date, league=league, base_url=self.base_url
        )
```

(`self.base_url` is available because `OddsPortalScraper` extends `BaseScraper`, which now stores it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_base_scraper.py::TestOddsPortalScraperUrlWiring -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/odds_portal_scraper.py tests/core/test_base_scraper.py
git commit -m "feat: pass scraper base_url into URLBuilder call sites"
```

---

### Task 5: `validate_base_url` CLI validator

**Files:**
- Modify: `src/oddsharvester/cli/validators.py`
- Test: `tests/cli/test_validators_base_url.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/cli/test_validators_base_url.py`:

```python
import click
import pytest

from oddsharvester.cli.validators import validate_base_url


def test_none_is_valid():
    assert validate_base_url(None, None, None) is None


def test_empty_is_valid():
    assert validate_base_url(None, None, "") is None


def test_valid_https_host_only():
    assert validate_base_url(None, None, "https://www.centroquote.it") == "https://www.centroquote.it"


def test_valid_http_host_only():
    assert validate_base_url(None, None, "http://mirror.example.com") == "http://mirror.example.com"


def test_strips_trailing_slash():
    assert validate_base_url(None, None, "https://www.centroquote.it/") == "https://www.centroquote.it"


def test_missing_scheme_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "www.centroquote.it")


def test_non_http_scheme_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "ftp://www.centroquote.it")


def test_url_with_path_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "https://www.centroquote.it/football")


def test_url_with_query_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "https://www.centroquote.it?x=1")


def test_empty_host_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "https://")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_validators_base_url.py -q`
Expected: FAIL — `ImportError: cannot import name 'validate_base_url'`.

- [ ] **Step 3: Implement the validator**

In `src/oddsharvester/cli/validators.py`, add `from urllib.parse import urlsplit` near the top imports (alongside `import re`), then append this function at the end of the file:

```python
def validate_base_url(ctx, param, value):
    """Validate --base-url: host-only http(s) URL (no path/query/fragment)."""
    if not value:
        return None

    normalized = value.rstrip("/")
    parts = urlsplit(normalized)

    if parts.scheme not in ("http", "https"):
        raise click.BadParameter(
            f"Invalid base URL '{value}'. Must start with http:// or https:// (e.g. https://www.centroquote.it)."
        )
    if not parts.netloc:
        raise click.BadParameter(f"Invalid base URL '{value}'. Missing host (e.g. https://www.centroquote.it).")
    if parts.path or parts.query or parts.fragment:
        raise click.BadParameter(
            f"Invalid base URL '{value}'. Provide host only, no path/query (e.g. https://www.centroquote.it)."
        )

    return normalized
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_validators_base_url.py -q`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/cli/validators.py tests/cli/test_validators_base_url.py
git commit -m "feat: add --base-url validator"
```

---

### Task 6: `--base-url` CLI option + plumbing through to the scraper

**Files:**
- Modify: `src/oddsharvester/cli/options.py`
- Modify: `src/oddsharvester/cli/commands/historic.py`, `src/oddsharvester/cli/commands/upcoming.py`
- Modify: `src/oddsharvester/core/scraper_app.py` (`run_scraper` signature + `OddsPortalScraper(...)` construction)
- Test: `tests/core/test_scraper_app_base_url.py` (new) — covered together with Task 7's warning test file; this task adds the wiring test below.

- [ ] **Step 1: Write the failing test**

Create `tests/core/test_scraper_app_base_url.py`:

```python
import inspect

from oddsharvester.core import scraper_app


def test_run_scraper_accepts_base_url_param():
    sig = inspect.signature(scraper_app.run_scraper)
    assert "base_url" in sig.parameters
    assert sig.parameters["base_url"].default is None


def test_run_scraper_forwards_base_url_to_scraper(monkeypatch):
    captured = {}

    class FakeScraper:
        def __init__(self, *args, base_url=None, **kwargs):
            captured["base_url"] = base_url

        async def start_playwright(self, **kwargs):
            raise RuntimeError("stop here")  # abort before real scraping

        async def stop_playwright(self):
            pass

    monkeypatch.setattr(scraper_app, "OddsPortalScraper", FakeScraper)

    import asyncio

    asyncio.run(
        scraper_app.run_scraper(
            command="scrape_upcoming",
            sport="football",
            date="2025-01-15",
            base_url="https://www.centroquote.it",
        )
    )
    assert captured["base_url"] == "https://www.centroquote.it"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/test_scraper_app_base_url.py -q`
Expected: FAIL — `base_url` not in `run_scraper` signature / not forwarded.

- [ ] **Step 3a: Add the CLI option**

In `src/oddsharvester/cli/options.py`, add `validate_base_url` to the validators import block (lines 8-16):

```python
from oddsharvester.cli.validators import (
    validate_base_url,
    validate_concurrency,
    validate_file_path,
    validate_leagues,
    validate_markets,
    validate_match_links,
    validate_period,
    validate_proxy_url,
)
```

Add this option inside `common_options`, immediately after the `--timezone` option block (after line 161):

```python
    @click.option(
        "--base-url",
        "base_url",
        callback=validate_base_url,
        envvar="OH_BASE_URL",
        help=(
            "Regional OddsPortal domain to scrape instead of www.oddsportal.com "
            "(e.g. https://www.centroquote.it). Pair with --locale/--timezone matching the region."
        ),
    )
```

- [ ] **Step 3b: Forward through both commands**

In `src/oddsharvester/cli/commands/upcoming.py`, add to the `run_scraper(...)` call (after `browser_timezone_id=kwargs.get("browser_timezone_id"),`):

```python
                base_url=kwargs.get("base_url"),
```

In `src/oddsharvester/cli/commands/historic.py`, add the same line to its `run_scraper(...)` call (after `browser_timezone_id=kwargs.get("browser_timezone_id"),`):

```python
                base_url=kwargs.get("base_url"),
```

- [ ] **Step 3c: Accept and forward in `run_scraper`**

In `src/oddsharvester/core/scraper_app.py`, add the parameter to `run_scraper` (after `browser_timezone_id: str | None = None,`):

```python
    browser_timezone_id: str | None = None,
    base_url: str | None = None,
```

In the same function, add `base_url=base_url` to the `OddsPortalScraper(...)` construction (after `preview_submarkets_only=preview_submarkets_only,`):

```python
    scraper = OddsPortalScraper(
        playwright_manager=playwright_manager,
        market_extractor=market_extractor,
        scroller=scroller,
        cookie_dismisser=cookie_dismisser,
        selection_manager=selection_manager,
        preview_submarkets_only=preview_submarkets_only,
        base_url=base_url,
    )
```

Add `base_url={base_url}` to the existing startup log line (extend the f-string in the `logger.info("Starting scraper with parameters: ...")` block, appending `, base_url={base_url}` before the closing quote).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_scraper_app_base_url.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/cli/options.py src/oddsharvester/cli/commands/historic.py src/oddsharvester/cli/commands/upcoming.py src/oddsharvester/core/scraper_app.py tests/core/test_scraper_app_base_url.py
git commit -m "feat: add --base-url CLI option and plumb it to run_scraper"
```

---

### Task 7: Locale/timezone mismatch warning

**Files:**
- Modify: `src/oddsharvester/core/scraper_app.py` (`run_scraper`)
- Test: `tests/core/test_scraper_app_base_url.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_scraper_app_base_url.py`:

```python
import logging


def _run_until_start(monkeypatch, **kwargs):
    class FakeScraper:
        def __init__(self, *a, base_url=None, **kw):
            pass

        async def start_playwright(self, **kw):
            raise RuntimeError("stop here")

        async def stop_playwright(self):
            pass

    monkeypatch.setattr(scraper_app, "OddsPortalScraper", FakeScraper)
    import asyncio

    asyncio.run(
        scraper_app.run_scraper(command="scrape_upcoming", sport="football", date="2025-01-15", **kwargs)
    )


def test_warns_when_regional_base_url_and_no_locale(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="ScraperApp"):
        _run_until_start(monkeypatch, base_url="https://www.centroquote.it")
    assert any("locale" in r.message.lower() and "timezone" in r.message.lower() for r in caplog.records)


def test_no_warning_for_default_com(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="ScraperApp"):
        _run_until_start(monkeypatch)
    assert not any("base url" in r.message.lower() for r in caplog.records)


def test_no_warning_when_locale_set(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="ScraperApp"):
        _run_until_start(
            monkeypatch, base_url="https://www.centroquote.it", browser_locale_timezone="it-IT"
        )
    assert not any("base url" in r.message.lower() for r in caplog.records)


def test_no_warning_for_oddsportal_subdomain(monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="ScraperApp"):
        _run_until_start(monkeypatch, base_url="https://es.oddsportal.com")
    assert not any("base url" in r.message.lower() for r in caplog.records)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_scraper_app_base_url.py -q -k warn`
Expected: FAIL — no warning emitted (assertions fail).

- [ ] **Step 3: Add the warning**

In `src/oddsharvester/core/scraper_app.py`, add `from urllib.parse import urlsplit` to the imports (top of file, with the stdlib import — there is currently only `import logging`; add a second line `from urllib.parse import urlsplit`).

In `run_scraper`, immediately after the existing `logger.info("Starting scraper with parameters: ...")` block and before `proxy_manager = ProxyManager(...)`, insert:

```python
    if base_url:
        host = urlsplit(base_url).netloc.lower()
        if not host.endswith("oddsportal.com") and not browser_locale_timezone and not browser_timezone_id:
            logger.warning(
                "Regional base URL '%s' is set but no --locale/--timezone provided. "
                "OddsPortal mirrors localise content; pass --locale and --timezone matching "
                "the region (see GitHub issue #45) for consistent results.",
                base_url,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_scraper_app_base_url.py -q`
Expected: PASS (all tests in file, including Task 6's).

- [ ] **Step 5: Commit**

```bash
git add src/oddsharvester/core/scraper_app.py tests/core/test_scraper_app_base_url.py
git commit -m "feat: warn on regional base_url without matching locale/timezone"
```

---

### Task 8: Documentation + full verification

**Files:**
- Modify: `README.md`
- Modify: `docs/agentic-gotchas.md`

- [ ] **Step 1: Document the option in README**

In `README.md`, find the CLI options section/table (search for `--locale` or `--proxy-url`). Add an entry for `--base-url` in the same format the file already uses, e.g.:

> `--base-url` — Scrape a regional OddsPortal mirror instead of `www.oddsportal.com` (e.g. `https://www.centroquote.it`). Page structure is identical across mirrors; only the domain changes. Regional domains may expose more bookmakers. Recommended: pair with `--locale`/`--timezone` matching the region (env var: `OH_BASE_URL`).

Match the surrounding formatting exactly (table row vs bullet — follow whatever is already there).

- [ ] **Step 2: Add a gotcha note**

Append to `docs/agentic-gotchas.md` (in the URL-conventions area, matching the file's existing entry format):

> **Regional OddsPortal mirrors** — OddsPortal serves region-specific mirror domains (e.g. `centroquote.it`) with byte-identical page structure; only scheme+host differ. `--base-url` swaps the domain at runtime via `rebase_url` (`url_builder.py`); the 100+ league URLs in `sport_league_constants.py` stay absolute `.com` (canonical default). The bookmaker set differs per region (issue #45 — users previously VPN'd for this). HAR-replay integration tests are `.com`-only, so `--base-url` is a live-only feature and is not covered by replay fixtures.

- [ ] **Step 3: Lint**

Run: `uv run ruff format . && uv run ruff check --fix src/`
Expected: clean (no remaining errors).

- [ ] **Step 4: Full unit test suite**

Run: `uv run pytest tests/ -q --ignore=tests/integration/`
Expected: PASS — all tests green, including the existing suite (no regression: `rebase_url(url, None) == url` guarantees the default path is unchanged).

- [ ] **Step 5: Manual smoke (no network assertion, just URL build)**

Run:
```bash
uv run python -c "from oddsharvester.core.url_builder import URLBuilder; print(URLBuilder.get_historic_matches_url(sport='football', league='italy-serie-a', season='current', base_url='https://www.centroquote.it'))"
```
Expected output: `https://www.centroquote.it/football/italy/serie-a/results/`

- [ ] **Step 6: Commit**

```bash
git add README.md docs/agentic-gotchas.md
git commit -m "docs: document --base-url regional domain support"
```

---

## Self-Review Notes

- **Spec coverage:** §1 rebase_url → Task 1; §2 URLBuilder → Task 2; §3 base_scraper join → Task 3; §4 plumbing → Tasks 4+6; §5 validation → Task 5; §6 locale warning → Task 7; §7 HAR limitation → documented in Task 8; §8 testing → tests in every task + Task 8 full run; docs → Task 8. All spec sections mapped.
- **No placeholders:** every code step shows exact code; test-helper reuse notes point the implementer at the existing patterns in `test_base_scraper.py` rather than leaving them undefined.
- **Type/name consistency:** `rebase_url(url, base_url)` signature consistent across Tasks 1/2/3/5/7; `self.base_url` attribute name consistent Tasks 3/4; `validate_base_url(ctx, param, value)` Click-callback signature consistent Tasks 5/6; `base_url` kwarg name identical from CLI option → `run_scraper` → `OddsPortalScraper` → `URLBuilder`.
- **Known limitation:** the only judgement call left to the implementer is reusing the existing `BaseScraper`/`OddsPortalScraper` test construction helpers in `tests/core/test_base_scraper.py` (Task 3/4); flagged explicitly with search hints because inventing parallel mocks would be brittle.
