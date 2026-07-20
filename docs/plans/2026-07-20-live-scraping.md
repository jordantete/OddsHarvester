# Live Scraping Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `live` CLI command that takes a one-shot snapshot of in-play matches: per-bookmaker live odds plus live context (score, period, scrape timestamp).

**Architecture:** Mirror of `scrape_upcoming`. Listing source is `/inplay-odds/live-now/<sport>/`; per-match pages are the `<match_url>/inplay-odds/#<id>` in-play view, which reuses the existing selector family. New pieces: live listing URL builder, live match-link extraction, `live-info` header parsing, a `live_mode` flag through the odds-extraction pipeline, `scrape_live()`, scraper_app routing, and the CLI command.

**Tech Stack:** Python >=3.12, Playwright (async), BeautifulSoup/lxml, Click, pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-07-20-live-scraping-design.md` (read it first).

## Global Constraints

- Branch: `feat/live-scraping` (already created; never commit to master, never push).
- Commit messages: single line, imperative, no trailers of any kind.
- Line length 120, double quotes, Ruff formatting. `uv run ruff format .` and `uv run ruff check --fix src/` before each commit.
- No em-dashes in code comments or docs.
- Before starting and after every task: `uv run pytest tests/ -q --ignore=tests/integration/` must pass.
- Constants live in ONE place (`odds_portal_selectors.py` for testids, `core/retry.py` for error keywords). Never duplicate literals.
- DOM state detection matches on text content shape or `data-testid`, never on Tailwind class names (see `docs/agentic-gotchas.md` §9).
- Package manager is `uv`; run everything through `uv run`.

## Verified DOM facts (captured live 2026-07-20, use verbatim in fixtures)

Live-now listing row (outer element; an inner div duplicates `data-testid="game-row"` inside the `<a>`):

```html
<div class="group flex" data-testid="game-row">
  <a class="ml-2 min-h-[32px] w-full" href="/tennis/h2h/janvier-maxime-S4riPNES/kuzmanov-dimitar-WEwUtEGs/inplay-odds/#t0bmQMVh">
    <div class="column h-full" data-testid="game-row">
      <div><p class="result-live"></p>
        <div data-testid="time-item"><p>1S</p></div>
      </div>
      <div data-testid="event-participants">...</div>
    </div>
  </a>
</div>
```

In-play match page live header:

```html
<div class="flex max-sm:gap-2" data-testid="live-info">
  <div class="flex flex-wrap gap-2">
    <p class="result-live"></p>
    <div class="text-red-dark">2nd Set</div>
    <div class="text-red-dark font-bold">1:0</div>
    <div class="flex" data-testid="partial-result"><span>(</span><div class="flex">6:4, 0:0</div><span>)</span></div>
  </div>
</div>
```

Key facts: listing hrefs already carry `/inplay-odds/#<id>`; `live-info` disappears when the match ends; the period chunk comes before the score chunk; `partial-result` holds the compound detail in parentheses.

---

### Task 1: Live URL building and CommandEnum

**Files:**
- Modify: `src/oddsharvester/utils/command_enum.py`
- Modify: `src/oddsharvester/core/url_builder.py`
- Test: `tests/core/test_url_builder.py`

**Interfaces:**
- Produces: `CommandEnum.LIVE` (value `"scrape_live"`); `URLBuilder.get_live_matches_url(sport: str, base_url: str | None = None) -> str`; module-level `normalize_inplay_match_url(url: str) -> str` in `url_builder.py`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_url_builder.py` (match the file's existing class/style conventions; read its first 60 lines before writing):

```python
class TestLiveUrls:
    def test_get_live_matches_url(self):
        url = URLBuilder.get_live_matches_url(sport="football")
        assert url == "https://www.oddsportal.com/inplay-odds/live-now/football/"

    def test_get_live_matches_url_rebases_on_base_url(self):
        url = URLBuilder.get_live_matches_url(sport="football", base_url="https://www.centroquote.it")
        assert url == "https://www.centroquote.it/inplay-odds/live-now/football/"

    def test_get_live_matches_url_rejects_unknown_sport(self):
        with pytest.raises(ValueError):
            URLBuilder.get_live_matches_url(sport="chess")

    def test_normalize_inplay_match_url_appends_segment(self):
        url = "https://www.oddsportal.com/football/spain/laliga/real-madrid-barcelona-abc123/"
        assert (
            normalize_inplay_match_url(url)
            == "https://www.oddsportal.com/football/spain/laliga/real-madrid-barcelona-abc123/inplay-odds/"
        )

    def test_normalize_inplay_match_url_preserves_fragment(self):
        url = "https://www.oddsportal.com/tennis/h2h/a-x1/b-y2/#t0bmQMVh"
        assert normalize_inplay_match_url(url) == "https://www.oddsportal.com/tennis/h2h/a-x1/b-y2/inplay-odds/#t0bmQMVh"

    def test_normalize_inplay_match_url_idempotent(self):
        url = "https://www.oddsportal.com/tennis/h2h/a-x1/b-y2/inplay-odds/#t0bmQMVh"
        assert normalize_inplay_match_url(url) == url
```

Add `from oddsharvester.core.url_builder import normalize_inplay_match_url` to the imports (the file already imports `URLBuilder` and `pytest`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_url_builder.py -q -k Live`
Expected: FAIL / ERROR with ImportError on `normalize_inplay_match_url` (or AttributeError on `get_live_matches_url`).

- [ ] **Step 3: Implement**

In `src/oddsharvester/utils/command_enum.py`, add one member to the enum:

```python
class CommandEnum(str, Enum):
    UPCOMING_MATCHES = "scrape_upcoming"
    HISTORIC = "scrape_historic"
    LIVE = "scrape_live"
```

In `src/oddsharvester/core/url_builder.py`, add after `rebase_url` (module level):

```python
def normalize_inplay_match_url(url: str) -> str:
    """
    Ensure a match URL points at its in-play view.

    Inserts the `/inplay-odds/` path segment before the fragment when it is
    missing. Idempotent. Live-now listing hrefs already carry the segment;
    this exists for user-supplied --match-link values in classic form.
    """
    parts = urlsplit(url)
    path = parts.path
    if not path.rstrip("/").endswith("/inplay-odds"):
        path = path.rstrip("/") + "/inplay-odds/"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))
```

In the `URLBuilder` class, add:

```python
@staticmethod
def get_live_matches_url(sport: str, base_url: str | None = None) -> str:
    """
    Constructs the URL for the live-now in-play listing of a sport.

    Args:
        sport (str): The sport for which the URL is required (e.g., "football").
        base_url (Optional[str]): When provided, rebases the returned URL onto this scheme+host.

    Returns:
        str: The live-now listing URL, e.g. https://www.oddsportal.com/inplay-odds/live-now/football/

    Raises:
        ValueError: If the sport is not a known Sport enum value.
    """
    sport_value = Sport(sport).value
    return rebase_url(f"{ODDSPORTAL_BASE_URL}/inplay-odds/live-now/{sport_value}/", base_url)
```

`Sport`, `ODDSPORTAL_BASE_URL`, `urlsplit`, `urlunsplit` are already imported in this module.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_url_builder.py -q`
Expected: all PASS (new and pre-existing).

- [ ] **Step 5: Commit**

```bash
uv run ruff format . && uv run ruff check --fix src/
git add src/oddsharvester/utils/command_enum.py src/oddsharvester/core/url_builder.py tests/core/test_url_builder.py
git commit -m "feat: add live listing URL builder and scrape_live command enum"
```

---

### Task 2: Live selectors and `_parse_live_info`

**Files:**
- Modify: `src/oddsharvester/core/odds_portal_selectors.py`
- Modify: `src/oddsharvester/core/base_scraper.py` (module-level helpers, near `_row_has_started`)
- Test: `tests/core/test_base_scraper.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `OddsPortalSelectors.LIVE_INFO_TESTID = "live-info"`, `OddsPortalSelectors.LIVE_PARTIAL_RESULT_TESTID = "partial-result"`, `OddsPortalSelectors.GAME_ROW_TESTID = "game-row"`; module-level `_parse_live_info(soup: BeautifulSoup) -> dict[str, Any] | None` in `base_scraper.py` returning keys `live_period` (str | None), `live_score_home` (int | None), `live_score_away` (int | None), `live_score_raw` (str | None), or None when the `live-info` element is absent.

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/test_base_scraper.py` (it already imports `BeautifulSoup`; add `_parse_live_info` to the existing `from oddsharvester.core.base_scraper import (...)` block):

```python
LIVE_INFO_TENNIS_HTML = """
<div class="flex max-sm:gap-2" data-testid="live-info">
  <div class="flex flex-wrap gap-2">
    <p class="result-live"></p>
    <div class="text-red-dark">2nd Set</div>
    <div class="text-red-dark font-bold">1:0</div>
    <div class="flex" data-testid="partial-result"><span>(</span><div class="flex">6:4, 0:0</div><span>)</span></div>
  </div>
</div>
"""

LIVE_INFO_FOOTBALL_STYLE_HTML = """
<div data-testid="live-info">
  <div>
    <div>65'</div>
    <div>2:1</div>
  </div>
</div>
"""


class TestParseLiveInfo:
    """Unit tests for the _parse_live_info helper (live scraping support)."""

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def test_parses_tennis_header_with_partial_result(self):
        result = _parse_live_info(self._soup(LIVE_INFO_TENNIS_HTML))
        assert result == {
            "live_period": "2nd Set",
            "live_score_home": 1,
            "live_score_away": 0,
            "live_score_raw": "1:0 (6:4, 0:0)",
        }

    def test_parses_minimal_period_and_score(self):
        result = _parse_live_info(self._soup(LIVE_INFO_FOOTBALL_STYLE_HTML))
        assert result == {
            "live_period": "65'",
            "live_score_home": 2,
            "live_score_away": 1,
            "live_score_raw": "2:1",
        }

    def test_returns_none_when_live_info_absent(self):
        assert _parse_live_info(self._soup("<div><p>Finished</p></div>")) is None

    def test_missing_score_yields_none_ints_and_keeps_period(self):
        result = _parse_live_info(self._soup('<div data-testid="live-info"><div>HT</div></div>'))
        assert result == {
            "live_period": "HT",
            "live_score_home": None,
            "live_score_away": None,
            "live_score_raw": None,
        }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_base_scraper.py -q -k ParseLiveInfo`
Expected: FAIL with ImportError on `_parse_live_info`.

- [ ] **Step 3: Implement**

In `src/oddsharvester/core/odds_portal_selectors.py`, in the `OddsPortalSelectors` class near the other `*_TESTID` constants (around line 85):

```python
# Live (in-play) pages. `live-info` is the match-page live header (period,
# score, partial result); it disappears once the match ends. `game-row` is
# the listing row testid shared with community pages.
LIVE_INFO_TESTID = "live-info"
LIVE_PARTIAL_RESULT_TESTID = "partial-result"
GAME_ROW_TESTID = "game-row"
```

In `src/oddsharvester/core/base_scraper.py`, add after `_row_kickoff_datetime` (module level):

```python
_LIVE_MAIN_SCORE_RE = re.compile(r"^(\d+)\s*[:–-]\s*(\d+)$")


def _parse_live_info(soup) -> dict[str, Any] | None:
    """Parse the in-play match header into live context fields.

    Structure (verified 2026-07-20): a `live-info` container holding a period
    chunk, a main-score chunk, and an optional `partial-result` element with
    the compound detail in parentheses. Match on text shape, not classes.
    Returns None when the container is absent (match ended or not live).
    """
    container = soup.find(attrs={"data-testid": OddsPortalSelectors.LIVE_INFO_TESTID})
    if container is None:
        return None

    partial_text = None
    partial_el = container.find(attrs={"data-testid": OddsPortalSelectors.LIVE_PARTIAL_RESULT_TESTID})
    if partial_el is not None:
        partial_text = partial_el.get_text("", strip=True).strip("()") or None
        partial_el.extract()

    period = None
    score_raw = None
    score_home = None
    score_away = None
    for chunk in container.stripped_strings:
        match = _LIVE_MAIN_SCORE_RE.match(chunk)
        if match and score_raw is None:
            score_raw = chunk
            score_home, score_away = int(match.group(1)), int(match.group(2))
        elif period is None and not match:
            period = chunk

    live_score_raw = score_raw
    if score_raw and partial_text:
        live_score_raw = f"{score_raw} ({partial_text})"

    return {
        "live_period": period,
        "live_score_home": score_home,
        "live_score_away": score_away,
        "live_score_raw": live_score_raw,
    }
```

`re`, `Any`, and `OddsPortalSelectors` are already imported in `base_scraper.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_base_scraper.py -q -k ParseLiveInfo`
Expected: 4 PASS.

- [ ] **Step 5: Run full unit suite and commit**

Run: `uv run pytest tests/ -q --ignore=tests/integration/`
Expected: all PASS.

```bash
uv run ruff format . && uv run ruff check --fix src/
git add src/oddsharvester/core/odds_portal_selectors.py src/oddsharvester/core/base_scraper.py tests/core/test_base_scraper.py
git commit -m "feat: parse in-play live-info header into live context fields"
```

---

### Task 3: `extract_live_match_links` on the live-now listing

**Files:**
- Modify: `src/oddsharvester/core/base_scraper.py` (method on `BaseScraper`, after `extract_match_links`)
- Test: `tests/core/test_base_scraper.py`

**Interfaces:**
- Consumes: `OddsPortalSelectors.GAME_ROW_TESTID` (Task 2), `_is_offscreen_row`, `URLBuilder.get_league_url`.
- Produces: `async def extract_live_match_links(self, page: Page, sport: str | None = None, league: str | None = None) -> list[dict[str, Any]]`; each dict has keys `match_link` (absolute URL, str) and `live_period` (str | None). Task 4's `scrape_live` consumes this exact shape.

- [ ] **Step 1: Write the failing tests**

Look at `tests/core/test_base_scraper.py:260` (`test_extract_match_links_skips_started_rows_when_requested`) and reuse its pattern for building a scraper with a mocked page whose `content()` returns fixture HTML (the `setup_base_scraper_mocks` fixture). Append:

```python
LIVE_NOW_LISTING_HTML = """
<html><body>
<div class="group flex" data-testid="game-row">
  <a href="/tennis/h2h/janvier-maxime-S4riPNES/kuzmanov-dimitar-WEwUtEGs/inplay-odds/#t0bmQMVh">
    <div class="column" data-testid="game-row">
      <div data-testid="time-item"><p>1S</p></div>
      <div data-testid="event-participants">Janvier M. - Kuzmanov D.</div>
    </div>
  </a>
</div>
<div class="group flex" data-testid="game-row">
  <a href="/football/england/premier-league/arsenal-chelsea-xYz12345/inplay-odds/#aB3dE6fG">
    <div class="column" data-testid="game-row">
      <div data-testid="time-item"><p>65'</p></div>
      <div data-testid="event-participants">Arsenal - Chelsea</div>
    </div>
  </a>
</div>
<div class="group flex" data-testid="game-row" style="position:absolute;left:-9999px">
  <a href="/football/england/premier-league/hidden-twin-corrupt/inplay-odds/#zzz">
    <div class="column" data-testid="game-row"></div>
  </a>
</div>
</body></html>
"""


@pytest.mark.asyncio
async def test_extract_live_match_links(setup_base_scraper_mocks):
    scraper, page = setup_base_scraper_mocks
    page.content.return_value = LIVE_NOW_LISTING_HTML

    rows = await scraper.extract_live_match_links(page=page)

    assert [r["match_link"] for r in rows] == [
        "https://www.oddsportal.com/tennis/h2h/janvier-maxime-S4riPNES/kuzmanov-dimitar-WEwUtEGs/inplay-odds/#t0bmQMVh",
        "https://www.oddsportal.com/football/england/premier-league/arsenal-chelsea-xYz12345/inplay-odds/#aB3dE6fG",
    ]
    assert rows[0]["live_period"] == "1S"
    assert rows[1]["live_period"] == "65'"


@pytest.mark.asyncio
async def test_extract_live_match_links_league_filter(setup_base_scraper_mocks):
    scraper, page = setup_base_scraper_mocks
    page.content.return_value = LIVE_NOW_LISTING_HTML

    rows = await scraper.extract_live_match_links(page=page, sport="football", league="england-premier-league")

    assert len(rows) == 1
    assert "arsenal-chelsea" in rows[0]["match_link"]


@pytest.mark.asyncio
async def test_extract_live_match_links_empty_listing(setup_base_scraper_mocks):
    scraper, page = setup_base_scraper_mocks
    page.content.return_value = "<html><body></body></html>"

    assert await scraper.extract_live_match_links(page=page) == []
```

Adjust the fixture unpacking (`scraper, page = ...`) to whatever `setup_base_scraper_mocks` actually yields; read the fixture definition first and mirror how `test_extract_match_links_skips_started_rows_when_requested` obtains the scraper and page mock. If the offscreen-twin style marker in the fixture HTML does not match `_OFFSCREEN_STYLE_MARKERS`, read that constant and use one of its markers verbatim.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_base_scraper.py -q -k extract_live`
Expected: FAIL with AttributeError (`extract_live_match_links` does not exist).

- [ ] **Step 3: Implement**

In `BaseScraper` (after `extract_match_links`):

```python
async def extract_live_match_links(
    self,
    page: Page,
    sport: str | None = None,
    league: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract match links and listing context from a live-now in-play listing.

    Rows are `[data-testid='game-row']` elements (no `eventRow` class on this
    listing, unlike /matches/). The testid appears twice per row (outer div
    and a nested div inside the anchor); only the outer one contains the
    anchor, and dedupe on href covers any residual duplication. Hrefs on
    this listing already carry the `/inplay-odds/#<id>` suffix.

    Args:
        page (Page): A Playwright Page instance for this task.
        sport (Optional[str]): Sport slug, required when `league` is given.
        league (Optional[str]): League slug; keeps only rows whose href starts
            with the league URL path from SPORTS_LEAGUES_URLS_MAPPING.

    Returns:
        List[dict]: One dict per live match: {"match_link": str, "live_period": str | None}.
    """
    try:
        league_path_prefix = None
        if league and sport:
            league_url = URLBuilder.get_league_url(sport, league)
            league_path_prefix = urlsplit(league_url).path

        html_content = await page.content()
        soup = BeautifulSoup(html_content, "lxml")
        rows = soup.find_all(attrs={"data-testid": OddsPortalSelectors.GAME_ROW_TESTID})

        seen: set[str] = set()
        results: list[dict[str, Any]] = []
        offscreen_skipped = 0
        league_filtered_out = 0

        for row in rows:
            if _is_offscreen_row(row):
                offscreen_skipped += 1
                continue

            anchor = row.find("a", href=lambda h: h and "/inplay-odds/" in h)
            if anchor is None:
                continue
            href = anchor["href"]
            if href in seen:
                continue
            seen.add(href)

            if league_path_prefix and not href.startswith(league_path_prefix):
                league_filtered_out += 1
                continue

            period = None
            time_el = row.find(attrs={"data-testid": OddsPortalSelectors.EVENT_ROW_TIME_ITEM_TESTID})
            if time_el is not None:
                p = time_el.find("p")
                text = p.get_text(strip=True) if p else time_el.get_text(strip=True)
                period = text or None

            results.append(
                {
                    "match_link": f"{self.base_url or ODDSPORTAL_BASE_URL}{href}",
                    "live_period": period,
                }
            )

        league_suffix = f", {league_filtered_out} rows outside league '{league}'" if league_path_prefix else ""
        self.logger.info(
            f"Extracted {len(results)} live match links "
            f"({offscreen_skipped} offscreen rows skipped{league_suffix})."
        )
        return results

    except Exception as e:
        self.logger.error(f"Error extracting live match links: {e}", exc_info=True)
        return []
```

Add `from oddsharvester.core.url_builder import URLBuilder` and `from urllib.parse import urlsplit` to `base_scraper.py` imports if not already present (check first; `URLBuilder` may be a new import here. If importing `URLBuilder` creates a circular import with `url_builder.py`, do the import inside the method body and note why in a one-line comment).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_base_scraper.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff format . && uv run ruff check --fix src/
git add src/oddsharvester/core/base_scraper.py tests/core/test_base_scraper.py
git commit -m "feat: extract live match links from the in-play live-now listing"
```

---

### Task 4: `live_mode` through the odds pipeline and `scrape_live()`

**Files:**
- Modify: `src/oddsharvester/core/base_scraper.py` (`extract_match_odds`, `_scrape_match_data`)
- Modify: `src/oddsharvester/core/odds_portal_scraper.py` (new `scrape_live` method after `scrape_upcoming`)
- Test: `tests/core/test_odds_portal_scraper.py`

**Interfaces:**
- Consumes: `extract_live_match_links` (Task 3), `_parse_live_info` (Task 2), `URLBuilder.get_live_matches_url` and `normalize_inplay_match_url` (Task 1).
- Produces: `extract_match_odds(..., live_mode: bool = False)`; `_scrape_match_data(..., live_mode: bool = False)`; and:

```python
async def scrape_live(
    self,
    sport: str,
    league: str | None = None,
    markets: list[str] | None = None,
    match_links: list[str] | None = None,
    target_bookmaker: str | None = None,
    bookies_filter: BookiesFilter = BookiesFilter.ALL,
    request_delay: float = DEFAULT_REQUEST_DELAY_S,
    concurrent_scraping_task: int = 3,
    links_only: bool = False,
) -> ScrapeResult
```

In `live_mode`, each successful match dict additionally contains `live_period`, `live_score_home`, `live_score_away`, `live_score_raw`, `scraped_at_utc`. Matches whose page has no `live-info` (ended) are dropped from the result with an info log.

- [ ] **Step 1: Write the failing tests**

Read the top of `tests/core/test_odds_portal_scraper.py` to reuse its scraper-construction fixtures/mocks, then append tests. Mock `extract_live_match_links` and `extract_match_odds` at the method level (they have their own tests):

```python
@pytest.mark.asyncio
async def test_scrape_live_no_matches_returns_empty_result(scraper_fixture):
    scraper = scraper_fixture
    scraper.extract_live_match_links = AsyncMock(return_value=[])
    # playwright_manager.page, goto, _prepare_page_for_scraping, scroller mocked per file conventions

    result = await scraper.scrape_live(sport="football")

    assert result.success == []
    assert result.stats.total_urls == 0


@pytest.mark.asyncio
async def test_scrape_live_links_only(scraper_fixture):
    scraper = scraper_fixture
    scraper.extract_live_match_links = AsyncMock(
        return_value=[{"match_link": "https://www.oddsportal.com/x/inplay-odds/#a", "live_period": "1H"}]
    )

    result = await scraper.scrape_live(sport="football", links_only=True)

    assert result.success == [
        {"match_link": "https://www.oddsportal.com/x/inplay-odds/#a", "sport": "football", "league": None}
    ]


@pytest.mark.asyncio
async def test_scrape_live_drops_ended_matches(scraper_fixture):
    scraper = scraper_fixture
    scraper.extract_live_match_links = AsyncMock(
        return_value=[
            {"match_link": "https://www.oddsportal.com/x/inplay-odds/#a", "live_period": "1H"},
            {"match_link": "https://www.oddsportal.com/y/inplay-odds/#b", "live_period": "2H"},
        ]
    )
    live_match = {"home_team": "A", "away_team": "B", "live_period": "1H"}
    ended_marker = {"_live_ended": True, "match_link": "https://www.oddsportal.com/y/inplay-odds/#b"}
    scraper.extract_match_odds = AsyncMock(
        return_value=ScrapeResult(
            success=[live_match, ended_marker],
            stats=ScrapeStats(total_urls=2, successful=2, failed=0),
        )
    )

    result = await scraper.scrape_live(sport="football", markets=["1x2"])

    assert result.success == [live_match]
    assert result.stats.successful == 1
    assert result.stats.total_urls == 1


@pytest.mark.asyncio
async def test_scrape_live_with_match_links_normalizes_urls(scraper_fixture):
    scraper = scraper_fixture
    scraper.extract_match_odds = AsyncMock(return_value=ScrapeResult())

    await scraper.scrape_live(
        sport="football",
        markets=["1x2"],
        match_links=["https://www.oddsportal.com/football/spain/laliga/real-betis-abc/"],
    )

    called_links = scraper.extract_match_odds.call_args.kwargs["match_links"]
    assert called_links == ["https://www.oddsportal.com/football/spain/laliga/real-betis-abc/inplay-odds/"]
    assert scraper.extract_match_odds.call_args.kwargs["live_mode"] is True
```

Also add a `_scrape_match_data` live-mode test in `tests/core/test_base_scraper.py`:

```python
@pytest.mark.asyncio
async def test_scrape_match_data_live_mode_adds_live_fields(setup_base_scraper_mocks):
    scraper, page = setup_base_scraper_mocks
    page.content.return_value = f"<html><body>{LIVE_INFO_TENNIS_HTML}</body></html>"
    scraper._extract_match_details_event_header = AsyncMock(return_value={"home_team": "A"})

    data = await scraper._scrape_match_data(page=page, sport="tennis", match_link="https://x/inplay-odds/#a", live_mode=True)

    assert data["live_period"] == "2nd Set"
    assert data["live_score_raw"] == "1:0 (6:4, 0:0)"
    assert data["scraped_at_utc"].endswith("Z")


@pytest.mark.asyncio
async def test_scrape_match_data_live_mode_flags_ended_match(setup_base_scraper_mocks):
    scraper, page = setup_base_scraper_mocks
    page.content.return_value = "<html><body><div>FT 2:1</div></body></html>"
    scraper._extract_match_details_event_header = AsyncMock(return_value={"home_team": "A"})

    data = await scraper._scrape_match_data(page=page, sport="football", match_link="https://x/inplay-odds/#a", live_mode=True)

    assert data == {"_live_ended": True, "match_link": "https://x/inplay-odds/#a"}
```

Mirror the file's existing mock plumbing exactly (page mock, selection_manager mock, etc.); the snippets above show intent, the surrounding fixture code comes from the file. Do NOT invent fixture names: `scraper_fixture` stands for whatever the file actually provides.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_odds_portal_scraper.py tests/core/test_base_scraper.py -q -k live`
Expected: FAIL (no `scrape_live`, no `live_mode` parameter).

- [ ] **Step 3: Implement `live_mode` in `base_scraper.py`**

`extract_match_odds`: add parameter `live_mode: bool = False` (after `request_delay`), pass it through in `scrape_single_match`:

```python
async def scrape_single_match(page: Page, link: str) -> dict[str, Any] | None:
    """Inner function to scrape a single match (used for retry)."""
    return await self._scrape_match_data(
        page=page,
        sport=sport,
        match_link=link,
        markets=markets,
        scrape_odds_history=scrape_odds_history,
        target_bookmaker=target_bookmaker,
        preview_submarkets_only=preview_submarkets_only,
        bookies_filter=bookies_filter,
        period=period,
        live_mode=live_mode,
    )
```

`_scrape_match_data`: add parameter `live_mode: bool = False`. Insert after the `match_details` None-check (`return None` at base_scraper.py:725) and before the `if markets:` block:

```python
if live_mode:
    live_html = await page.content()
    live_soup = BeautifulSoup(live_html, "lxml")
    live_info = _parse_live_info(live_soup)
    if live_info is None:
        # No live-info header: the match ended (or lost live coverage)
        # between listing and visit. Not a scraping failure.
        self.logger.info(f"No live-info header on {match_link}; match no longer live, skipping.")
        return {"_live_ended": True, "match_link": match_link}
    match_details.update(live_info)
    match_details["scraped_at_utc"] = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
```

`datetime`, `UTC`, `BeautifulSoup` are already imported in `base_scraper.py` (verify; add if missing).

- [ ] **Step 4: Implement `scrape_live` in `odds_portal_scraper.py`**

After `scrape_upcoming`:

```python
async def scrape_live(
    self,
    sport: str,
    league: str | None = None,
    markets: list[str] | None = None,
    match_links: list[str] | None = None,
    target_bookmaker: str | None = None,
    bookies_filter: BookiesFilter = BookiesFilter.ALL,
    request_delay: float = DEFAULT_REQUEST_DELAY_S,
    concurrent_scraping_task: int = 3,
    links_only: bool = False,
) -> ScrapeResult:
    """
    Scrapes a one-shot snapshot of in-play odds for currently live matches.

    Listing source is /inplay-odds/live-now/<sport>/; each match is scraped
    on its in-play view (per-bookmaker live odds + live score/period). When
    `match_links` is provided the listing is skipped and the given URLs are
    normalized to their in-play form (external re-sampling building block).

    Args:
        sport (str): The sport to scrape.
        league (Optional[str]): Single league slug filter (post-listing).
        markets (Optional[List[str]]): List of markets.
        match_links (Optional[List[str]]): Scrape these matches directly.
        target_bookmaker (str): If set, only scrape odds for this bookmaker.
        links_only (bool): If True, return collected live links without odds.

    Returns:
        ScrapeResult: Contains successful results, failed URLs, and statistics.
    """
    current_page = self.playwright_manager.page
    if not current_page:
        raise RuntimeError("Playwright has not been initialized. Call `start_playwright()` first.")

    if match_links:
        links = [normalize_inplay_match_url(link) for link in match_links]
        await current_page.goto(ODDSPORTAL_BASE_URL, timeout=GOTO_TIMEOUT_LONG_MS, wait_until="domcontentloaded")
        await self._prepare_page_for_scraping(page=current_page)
    else:
        url = URLBuilder.get_live_matches_url(sport=sport, base_url=self.base_url)
        self.logger.info(f"Fetching live matches from {url}")
        await current_page.goto(url, timeout=GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
        await self._prepare_page_for_scraping(page=current_page)
        await self.scroller.scroll_until_loaded(
            page=current_page,
            timeout=30,
            scroll_pause_time=2,
            max_scroll_attempts=3,
            content_check_selector="div[data-testid='game-row']",
        )
        rows = await self.extract_live_match_links(page=current_page, sport=sport, league=league)
        if not rows:
            self.logger.info("No live matches found on the live-now listing.")
            return ScrapeResult()
        links = [row["match_link"] for row in rows]

    if links_only:
        self.logger.info(f"Links-only mode: returning {len(links)} live match links without odds.")
        return self._links_only_result(links=links, context={"sport": sport, "league": league})

    result = await self.extract_match_odds(
        sport=sport,
        match_links=links,
        markets=markets,
        scrape_odds_history=False,
        target_bookmaker=target_bookmaker,
        concurrent_scraping_task=concurrent_scraping_task,
        preview_submarkets_only=self.preview_submarkets_only,
        bookies_filter=bookies_filter,
        period=None,
        request_delay=request_delay,
        live_mode=True,
    )

    ended = [d for d in result.success if d.get("_live_ended")]
    if ended:
        self.logger.info(f"{len(ended)} matches ended between listing and scrape; dropped from output.")
        result.success = [d for d in result.success if not d.get("_live_ended")]
        result.stats.successful -= len(ended)
        result.stats.total_urls -= len(ended)

    return result
```

Add `from oddsharvester.core.url_builder import URLBuilder, normalize_inplay_match_url` to the imports (URLBuilder is already imported; extend that line).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/ -q`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff format . && uv run ruff check --fix src/
git add src/oddsharvester/core/base_scraper.py src/oddsharvester/core/odds_portal_scraper.py tests/core/test_base_scraper.py tests/core/test_odds_portal_scraper.py
git commit -m "feat: add scrape_live snapshot flow with live context extraction"
```

---

### Task 5: scraper_app routing for `scrape_live`

**Files:**
- Modify: `src/oddsharvester/core/scraper_app.py`
- Test: `tests/core/test_scraper_app.py`

**Interfaces:**
- Consumes: `scraper.scrape_live` (Task 4), `CommandEnum.LIVE` (Task 1).
- Produces: `run_scraper(command="scrape_live", ...)` routes to `scrape_live` via `retry_scrape`. CLI (Task 6) relies on this.

- [ ] **Step 1: Write the failing test**

Read `tests/core/test_scraper_app.py` for its existing routing-test pattern (it mocks `OddsPortalScraper`), then append:

```python
@pytest.mark.asyncio
async def test_run_scraper_routes_live_command(mock_scraper_dependencies):
    # per file conventions: OddsPortalScraper is patched; grab the instance mock
    result = await run_scraper(
        command="scrape_live",
        sport="football",
        markets=["1x2"],
    )
    scraper_instance.scrape_live.assert_awaited_once()
    kwargs = scraper_instance.scrape_live.await_args.kwargs
    assert kwargs["sport"] == "football"
    assert kwargs["league"] is None


@pytest.mark.asyncio
async def test_run_scraper_live_with_match_links_uses_scrape_live_not_scrape_matches(mock_scraper_dependencies):
    await run_scraper(
        command="scrape_live",
        sport="football",
        match_links=["https://www.oddsportal.com/football/x/y/z-abc/"],
        markets=["1x2"],
    )
    scraper_instance.scrape_live.assert_awaited_once()
    scraper_instance.scrape_matches.assert_not_awaited()
```

Adapt mock names to the file's real fixtures. The second test is the critical one: the pre-existing `if match_links and sport:` early branch in `run_scraper` must NOT swallow the live command.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_scraper_app.py -q -k live`
Expected: FAIL (`scrape_live` never awaited; generic branch routed to `scrape_matches` / unknown-command ValueError).

- [ ] **Step 3: Implement**

In `run_scraper` (scraper_app.py), insert a live branch BEFORE the `if match_links and sport:` block (currently at line ~130):

```python
if command == CommandEnum.LIVE:
    if not sport:
        raise ValueError("'sport' must be provided for live scraping.")
    logger.info(f"""
        Scraping live matches for sport={sport}, league={leagues}, markets={markets},
        target_bookmaker={target_bookmaker}, bookies_filter={bookies_filter}
    """)
    return await retry_scrape(
        scraper.scrape_live,
        sport=sport,
        league=leagues[0] if leagues else None,
        markets=markets,
        match_links=list(match_links) if match_links else None,
        target_bookmaker=target_bookmaker,
        bookies_filter=bookies_filter_enum,
        request_delay=request_delay,
        concurrent_scraping_task=concurrency_tasks,
        links_only=links_only,
    )
```

Also update the final `else` error message to include the live command:

```python
raise ValueError(f"Unknown command: {command}. Supported commands are 'upcoming-matches', 'historic' and 'live'.")
```

Note: `command` arrives as the string `"scrape_live"` from the CLI; `CommandEnum` is a `str` enum so `command == CommandEnum.LIVE` works for both string and enum inputs (same mechanism as the existing branches).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_scraper_app.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
uv run ruff format . && uv run ruff check --fix src/
git add src/oddsharvester/core/scraper_app.py tests/core/test_scraper_app.py
git commit -m "feat: route scrape_live command in scraper_app"
```

---

### Task 6: CLI `live` command

**Files:**
- Create: `src/oddsharvester/cli/commands/live.py`
- Modify: `src/oddsharvester/cli/commands/__init__.py`
- Modify: `src/oddsharvester/cli/cli.py`
- Test: `tests/cli/test_live_command.py` (new, mirror `tests/cli/test_community_command.py` conventions)

**Interfaces:**
- Consumes: `run_scraper(command="scrape_live", ...)` (Task 5), `common_options`, `store_data`.
- Produces: `oddsharvester live` CLI command.

- [ ] **Step 1: Write the failing tests**

Read `tests/cli/test_community_command.py` for the CliRunner pattern, then create `tests/cli/test_live_command.py`:

```python
"""Tests for the live CLI command."""

from unittest.mock import patch

from click.testing import CliRunner

from oddsharvester.cli.cli import cli


def test_live_requires_sport():
    runner = CliRunner()
    result = runner.invoke(cli, ["live"])
    assert result.exit_code != 0
    assert "--sport" in result.output or "sport" in result.output


def test_live_rejects_odds_history():
    runner = CliRunner()
    result = runner.invoke(cli, ["live", "--sport", "football", "--odds-history"])
    assert result.exit_code != 0
    assert "not supported" in result.output


def test_live_rejects_period():
    runner = CliRunner()
    result = runner.invoke(cli, ["live", "--sport", "football", "--period", "full_time"])
    assert result.exit_code != 0
    assert "not supported" in result.output


def test_live_rejects_multiple_leagues():
    runner = CliRunner()
    result = runner.invoke(
        cli, ["live", "--sport", "football", "--league", "england-premier-league,spain-laliga"]
    )
    assert result.exit_code != 0
    assert "one" in result.output.lower()


def test_live_rejects_links_only_with_match_link():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["live", "--sport", "football", "--links-only", "--match-link", "https://www.oddsportal.com/football/a/b/c-x/"],
    )
    assert result.exit_code != 0


@patch("oddsharvester.cli.commands.live.store_data")
@patch("oddsharvester.cli.commands.live.run_scraper")
def test_live_invokes_run_scraper_with_live_command(mock_run, mock_store):
    from oddsharvester.core.scrape_result import ScrapeResult, ScrapeStats

    mock_run.return_value = ScrapeResult(success=[{"home_team": "A"}], stats=ScrapeStats(total_urls=1, successful=1))
    runner = CliRunner()
    result = runner.invoke(cli, ["live", "--sport", "football", "--market", "1x2"])
    assert result.exit_code == 0
    # run_scraper is wrapped in asyncio.run; check the kwargs captured by the mock
    assert mock_run.call_args.kwargs["command"] == "scrape_live"
    assert mock_run.call_args.kwargs["sport"] == "football"
```

Note on the last test: `run_scraper` is awaited via `asyncio.run(run_scraper(...))` inside the command, so the mock must return an awaitable OR the test must patch differently. Check how `tests/cli/test_click_cli.py` handles this for `upcoming` (it already solves this problem) and copy that exact mechanism.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_live_command.py -q`
Expected: FAIL (command `live` does not exist; usage error mentions "No such command").

- [ ] **Step 3: Implement**

Create `src/oddsharvester/cli/commands/live.py` (modeled on `upcoming.py`):

```python
"""CLI command for scraping live (in-play) matches."""

import asyncio
import logging
import sys

import click

from oddsharvester.cli.options import common_options
from oddsharvester.core.scraper_app import run_scraper
from oddsharvester.storage.storage_manager import store_data

logger = logging.getLogger(__name__)


@click.command("live")
@common_options
@click.pass_context
def live(ctx, **kwargs):
    """Scrape a one-shot snapshot of in-play odds for currently live matches."""
    if kwargs.get("scrape_odds_history"):
        raise click.UsageError("--odds-history is not supported for live scraping.")
    if kwargs.get("period"):
        raise click.UsageError("--period is not supported for live scraping (current view only).")

    leagues = kwargs.get("leagues")
    if leagues and len(leagues) > 1:
        raise click.UsageError("live supports at most one --league.")

    links_only = kwargs.get("links_only", False)
    if links_only and kwargs.get("match_links"):
        raise click.UsageError("--links-only cannot be combined with --match-link (links are already collected).")

    sport = kwargs["sport"]
    storage = kwargs["storage"]
    storage_format = kwargs["storage_format"]
    bookies_filter = kwargs.get("bookies_filter")

    try:
        scraped_data = asyncio.run(
            run_scraper(
                command="scrape_live",
                match_links=kwargs.get("match_links"),
                sport=sport.value if sport else None,
                leagues=leagues,
                markets=kwargs.get("markets"),
                proxy_url=kwargs.get("proxy_url"),
                proxy_user=kwargs.get("proxy_user"),
                proxy_pass=kwargs.get("proxy_pass"),
                browser_user_agent=kwargs.get("browser_user_agent"),
                browser_locale_timezone=kwargs.get("browser_locale_timezone"),
                browser_timezone_id=kwargs.get("browser_timezone_id"),
                base_url=kwargs.get("base_url"),
                target_bookmaker=kwargs.get("target_bookmaker"),
                headless=kwargs.get("headless", False),
                bookies_filter=bookies_filter.value if bookies_filter else "all",
                request_delay=kwargs.get("request_delay", 1.0),
                concurrency_tasks=kwargs.get("concurrency_tasks", 3),
                links_only=links_only,
            )
        )

        if scraped_data is not None and (scraped_data.success or not scraped_data.failed):
            if not scraped_data.success:
                click.echo("No live matches found right now.")
                return
            store_data(
                storage_type=storage.value if storage else "local",
                data=scraped_data.success,
                storage_format=storage_format.value if storage_format else "json",
                file_path=kwargs.get("file_path"),
                append=kwargs.get("append", False),
            )
            if links_only:
                click.echo(f"Collected {scraped_data.stats.successful} live match links.")
            else:
                click.echo(
                    f"Successfully scraped {scraped_data.stats.successful} live matches "
                    f"({scraped_data.stats.failed} failed, {scraped_data.stats.success_rate:.1f}% success rate)."
                )
            if scraped_data.failed:
                click.echo(f"Failed URLs: {[f.url for f in scraped_data.failed]}", err=True)
        else:
            logger.error("Scraper did not return valid data.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        sys.exit(1)
```

Important semantic (from spec): zero live matches is exit 0 with a message, NOT an error. The condition above treats an empty-success/empty-failed result as success. Check the actual signature of `run_scraper` before writing the call: pass only kwargs that exist (e.g. the leagues parameter name, `date`/`seasons` are omitted on purpose since they default to None). Mirror `upcoming.py`'s exact kwarg names for the shared options.

Register the command: in `src/oddsharvester/cli/commands/__init__.py` add the `live` import/export mirroring `upcoming`; in `src/oddsharvester/cli/cli.py` add `cli.add_command(live)` after the existing three.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/ -q`
Expected: all PASS.

- [ ] **Step 5: Manual smoke test (no live football needed)**

Run: `uv run oddsharvester live --sport football --market 1x2 --headless`
Expected (weekday daytime): "No live matches found right now." and exit 0. If matches are live: JSON output file with `live_*` fields. Either outcome is a pass; a crash is a fail.

- [ ] **Step 6: Commit**

```bash
uv run ruff format . && uv run ruff check --fix src/
git add src/oddsharvester/cli/ tests/cli/test_live_command.py
git commit -m "feat: add live CLI command for in-play snapshot scraping"
```

---

### Task 7: Self-discovering live integration test

**Files:**
- Create: `tests/integration/test_live_snapshot.py`

**Interfaces:**
- Consumes: the full `live` pipeline (Tasks 1-6).

- [ ] **Step 1: Read the integration conventions**

Read `tests/integration/conftest.py` and one existing integration test file to reuse the marks (`integration`, `live_only`) and any shared fixtures.

- [ ] **Step 2: Write the test**

```python
"""Live-network integration test for the live (in-play) snapshot flow.

No HAR replay: live matches are ephemeral, so this test self-discovers
whatever is currently in play across all sports and skips when nothing is.
Run with: uv run pytest tests/integration/test_live_snapshot.py -q -m integration --live
"""

import pytest

from oddsharvester.core.scraper_app import run_scraper

pytestmark = [pytest.mark.integration, pytest.mark.live_only]

# Sports most likely to have something in play at any hour
CANDIDATE_SPORTS = ["football", "tennis", "basketball", "baseball"]


@pytest.mark.asyncio
async def test_live_snapshot_self_discovering():
    for sport in CANDIDATE_SPORTS:
        result = await run_scraper(
            command="scrape_live",
            sport=sport,
            markets=None,
            headless=True,
        )
        if result is None or not result.success:
            continue
        match = result.success[0]
        assert match.get("scraped_at_utc"), "live snapshot must carry a scrape timestamp"
        assert "live_period" in match
        assert "live_score_raw" in match
        return
    pytest.skip("No live matches with in-play odds found on any candidate sport right now.")
```

Adjust the markets argument if `run_scraper` requires a non-None market for output (check: metadata-only scraping without markets is supported by `_scrape_match_data`, so `markets=None` is fine).

- [ ] **Step 3: Verify collection and skip behavior without network**

Run: `uv run pytest tests/integration/test_live_snapshot.py -q -m integration`
Expected: the test is SKIPPED (live_only tests skip outside `--live` mode). Confirm no collection errors.

- [ ] **Step 4: Commit**

```bash
uv run ruff format .
git add tests/integration/test_live_snapshot.py
git commit -m "test: self-discovering live-network test for in-play snapshots"
```

---

### Task 8: Documentation

**Files:**
- Modify: `docs/agentic-gotchas.md` (new §15 + §9 drift note)
- Modify: `README.md` (live command section)

- [ ] **Step 1: Add §15 to the gotchas**

Read the "Adding a new gotcha" criteria at the bottom of `docs/agentic-gotchas.md` and the structure of §14, then append a §15 titled "In-play (live) pages: dedicated URL space, self-polling feeds, thin bookmaker coverage". Content to cover (all verified 2026-07-20, keep the doc's factual tone, no em-dashes):

- URL space: `/inplay-odds/live-now/<sport>/` and `/inplay-odds/scheduled/<sport>/` listings; match-level in-play view at `<match_url>/inplay-odds/#<match_id>`; "Pre-match Odds" and "In-Play Odds" are distinct tabs on the same match page and must never be mixed.
- Live-now listing rows have NO `eventRow` class (unlike `/matches/`); they are `[data-testid='game-row']` elements, the testid duplicated on a nested div. Hrefs already carry `/inplay-odds/#<id>`.
- The open match page polls `/feed/live-event/*.dat` (~10s) and `/feed/postmatch-score/*.dat` (~3-4s) and mutates the DOM in place; a scraper snapshot needs exactly one page load, never a reload loop.
- The `live-info` header (period, main score, `partial-result` in parentheses) disappears when the match ends; its absence on a page reached from the live-now listing means "ended between listing and visit", not a parsing bug.
- In-play bookmaker coverage is much thinner than pre-match (2 bookmakers from FR geo vs 15-20 pre-match) and geo-dependent; a near-empty in-play odds table is normal, not an extraction failure.
- Live match pages are ephemeral: once finished, the in-play view is gone forever. HAR fixtures must be captured while the match runs (capture once, replay forever).

- [ ] **Step 2: Record the §9 drift**

In §9's table area, add a short dated note: on 2026-07-20 a `/matches/football/` listing showed `FinishedFIN` inside the `time-item` text (the table documents it in `game-status-box`). `_row_has_started` still catches this case through its time-item branch (text does not match `^\d{1,2}:\d{2}$`), so no code change; recapture and re-verify at next fixture refresh.

- [ ] **Step 3: README section**

Add a `live` command section next to the `upcoming` examples:

````markdown
### Live (in-play) snapshot

```bash
uv run oddsharvester live --sport football --market 1x2
uv run oddsharvester live --sport football --league england-premier-league --market 1x2,over_under
uv run oddsharvester live --sport football --match-link "https://www.oddsportal.com/football/.../" --market 1x2
```

Takes a one-shot snapshot of matches currently in play: per-bookmaker in-play odds
plus `live_period`, `live_score_home/away`, `live_score_raw` and `scraped_at_utc`.
Zero live matches is a normal outcome (empty output, exit 0).

For repeated sampling, run the command on an external schedule (cron or similar).
Keep at least 60s between snapshots and prefer `--match-link` to re-sample a known
match without reloading the listing. In-play bookmaker coverage is thinner than
pre-match and varies by region. `--odds-history` and `--period` are not supported
in live mode.
````

Match the README's existing heading levels and formatting.

- [ ] **Step 4: Commit**

```bash
git add docs/agentic-gotchas.md README.md
git commit -m "docs: document in-play scraping architecture and live command"
```

---

### Task 9: Full verification pass

- [ ] **Step 1: Full unit suite + lint**

Run: `uv run pytest tests/ -q --ignore=tests/integration/`
Expected: all PASS.
Run: `uv run ruff format --check . && uv run ruff check src/`
Expected: clean.

- [ ] **Step 2: Integration replay suite unaffected**

Run: `uv run pytest tests/integration/ -q -m integration`
Expected: same pass/skip counts as on master (no regression; the new live test skips).

- [ ] **Step 3: End-to-end smoke**

Run: `uv run oddsharvester live --sport tennis --market home_away --headless -o /tmp/live_smoke.json`
(Tennis has near-continuous live coverage.) Expected: either scraped matches whose JSON records contain `live_period`, `live_score_raw`, `scraped_at_utc` and a `home_away_market` block, or "No live matches found right now." with exit 0. Inspect the JSON if produced.

If the market name for tennis differs (check `SPORT_MARKETS_MAPPING` in `utils/sport_market_constants.py` for the tennis market enum values), use the correct one.

- [ ] **Step 4: Commit any fixes, then report**

Report results to the user. Do NOT merge into master and do NOT push; the user decides.

---

## Deferred (documented, not in this plan)

- **HAR fixture capture for deterministic replay tests**: requires a live football match; run during an evening session with `uv run python -m tests.integration.helpers.capture ... --capture-har` against a live match's in-play URL, then add a replay test. The Notion card stays in Doing until this is done.
- Football-specific `live-info` format verification (`65'`, `HT`): the parser is shape-based and covered by the football-style unit fixture, but confirm against a real live football page the same evening and adjust `_parse_live_info` + fixtures if the real DOM differs.
- `/inplay-odds/scheduled/` scraping, watch mode, live odds history, `--period` support: out of scope per spec.
