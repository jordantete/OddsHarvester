from datetime import UTC, date, datetime, timedelta
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError
import pytest

from oddsharvester.core.base_scraper import (
    BaseScraper,
    _extract_fragment_match_id,
    _is_offscreen_row,
    _parse_date_header,
    _parse_live_info,
    _row_has_started,
    _row_kickoff_datetime,
)
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.odds_portal_scraper import OddsPortalScraper
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.utils.constants import NAVIGATION_TIMEOUT_MS, ODDSPORTAL_BASE_URL
from oddsharvester.utils.odds_format_enum import OddsFormat


@pytest.fixture
def setup_base_scraper_mocks():
    """Setup common mocks for BaseScraper tests."""
    # Create mocks for dependencies
    playwright_manager_mock = MagicMock(spec=PlaywrightManager)
    market_extractor_mock = MagicMock(spec=OddsPortalMarketExtractor)

    # Setup page mock
    page_mock = AsyncMock(spec=Page)
    page_mock.goto = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()
    page_mock.query_selector = AsyncMock()
    page_mock.query_selector_all = AsyncMock()
    page_mock.content = AsyncMock(return_value="<html><body>Test HTML</body></html>")
    page_mock.wait_for_timeout = AsyncMock()

    # Configure the context mock
    context_mock = AsyncMock()
    context_mock.new_page = AsyncMock(return_value=page_mock)

    # Configure playwright manager mock
    playwright_manager_mock.context = context_mock
    playwright_manager_mock.new_rotated_page = AsyncMock(return_value=(page_mock, "direct"))
    playwright_manager_mock.new_page_on_key = AsyncMock(return_value=page_mock)
    playwright_manager_mock.non_default_context_keys = MagicMock(return_value=[])
    playwright_manager_mock.report_page_result = MagicMock()
    playwright_manager_mock.blacklist_proxy = MagicMock()

    selection_manager_mock = AsyncMock()

    # Create scraper instance with mocks
    scraper = BaseScraper(
        playwright_manager=playwright_manager_mock,
        market_extractor=market_extractor_mock,
        scroller=AsyncMock(),
        cookie_dismisser=AsyncMock(),
        selection_manager=selection_manager_mock,
    )

    return {
        "scraper": scraper,
        "playwright_manager_mock": playwright_manager_mock,
        "market_extractor_mock": market_extractor_mock,
        "selection_manager_mock": selection_manager_mock,
        "page_mock": page_mock,
        "context_mock": context_mock,
    }


@pytest.mark.asyncio
async def test_set_odds_format(setup_base_scraper_mocks):
    """Test setting odds format on the page."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock the dropdown button
    dropdown_button_mock = AsyncMock()
    dropdown_button_mock.inner_text = AsyncMock(return_value="Decimal Odds")
    page_mock.query_selector.return_value = dropdown_button_mock

    # Test when odds format is already set
    await scraper.set_odds_format(page=page_mock, odds_format=OddsFormat.DECIMAL_ODDS)

    page_mock.wait_for_selector.assert_called_once()
    page_mock.query_selector.assert_called_once()
    dropdown_button_mock.inner_text.assert_called_once()
    dropdown_button_mock.click.assert_not_called()

    # Reset mocks
    page_mock.wait_for_selector.reset_mock()
    page_mock.query_selector.reset_mock()
    dropdown_button_mock.inner_text.reset_mock()

    # Mock dropdown button with different format and options
    dropdown_button_mock.inner_text = AsyncMock(return_value="American")

    # Mock format options
    format_option1 = AsyncMock()
    format_option1.inner_text = AsyncMock(return_value="Decimal Odds")
    format_option2 = AsyncMock()
    format_option2.inner_text = AsyncMock(return_value="Fractional Odds")

    page_mock.query_selector_all.return_value = [format_option1, format_option2]

    # Test selecting a different format
    await scraper.set_odds_format(page=page_mock, odds_format=OddsFormat.DECIMAL_ODDS)

    dropdown_button_mock.click.assert_called_once()
    page_mock.query_selector_all.assert_called_once()
    format_option1.inner_text.assert_called_once()
    format_option1.click.assert_called_once()


@pytest.mark.asyncio
async def test_set_odds_format_uses_text_based_button_selector(setup_base_scraper_mocks):
    """Regression for issue #68.

    OddsPortal's React build dropped the `div.group > button.gap-2` class combo
    (it became `button.flex gap-3`), silently breaking `set_odds_format`. The
    selector must be text-based so it survives Tailwind class refactors. This
    test pins the exact selector string passed to `wait_for_selector`.
    """
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    dropdown_button_mock = AsyncMock()
    dropdown_button_mock.inner_text = AsyncMock(return_value="Decimal Odds")
    page_mock.query_selector.return_value = dropdown_button_mock

    await scraper.set_odds_format(page=page_mock, odds_format=OddsFormat.DECIMAL_ODDS)

    selector_arg = page_mock.wait_for_selector.call_args[0][0]
    assert selector_arg == "button:has-text('Odds')"
    assert "gap-2" not in selector_arg


@pytest.mark.asyncio
async def test_set_odds_format_timeout(setup_base_scraper_mocks):
    """Test handling timeout when setting odds format."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock a timeout error
    page_mock.wait_for_selector.side_effect = TimeoutError("Timeout")

    # Test handling the timeout
    await scraper.set_odds_format(page=page_mock)

    page_mock.wait_for_selector.assert_called_once()
    page_mock.query_selector.assert_not_called()


@pytest.mark.asyncio
async def test_extract_match_links(setup_base_scraper_mocks):
    """Rows are [data-testid='game-row'] elements linking to H2H-fragment URLs
    (2026-08 redesign); short hrefs (<= 3 path segments) are filtered out."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
          <div data-testid="game-row">
            <a href="/football/h2h/h-beer-sheva-EXAD1YZP/sabah-baku-fNGcxbyr/#0KccwcGq">m1</a>
            <a href="/">short - filtered</a>
          </div>
          <div data-testid="game-row">
            <a href="/football/h2h/celtic-QFKRRD8M/lask-linz-MipWYeKQ/#OOklm0j3">m2</a>
          </div>
        </body></html>
        """
    )

    result = await scraper.extract_match_links(page=page_mock)

    page_mock.content.assert_called_once()
    assert result == [
        f"{ODDSPORTAL_BASE_URL}/football/h2h/h-beer-sheva-EXAD1YZP/sabah-baku-fNGcxbyr/#0KccwcGq",
        f"{ODDSPORTAL_BASE_URL}/football/h2h/celtic-QFKRRD8M/lask-linz-MipWYeKQ/#OOklm0j3",
    ]


@pytest.mark.asyncio
@patch("oddsharvester.core.base_scraper.BeautifulSoup")
async def test_extract_match_links_error(bs4_mock, setup_base_scraper_mocks):
    """Test handling errors when extracting match links."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock an exception in BeautifulSoup processing
    bs4_mock.side_effect = Exception("Parsing error")

    # Call the method under test
    result = await scraper.extract_match_links(page=page_mock)

    # Verify error handling
    assert result == []


# -- skip_started filter (GitHub issue #58) ---------------------------------

# Minimal listing HTML mirroring the OddsPortal DOM verified live 2026-05-20
# on football + volleyball listings:
# - Upcoming row: game-status-box empty + time-item shows "HH:MM"
# - Live row: game-status-box still empty + time-item shows a period marker
#   ("1S", "4S", "HT", "1H"); OddsPortal flips only the time-item during play
# - Finished row: game-status-box filled ("FinishedFIN")
# - Edge: row missing both elements (DOM drift fail-safe -> keep)
_LISTING_HTML = """
<html><body>
<div data-testid="game-row">
  <div data-testid="time-item"><p>21:00</p></div>
  <div data-testid="game-status-box"></div>
  <a href="/football/england/premier-league/upcoming-match/aaaa1111">link</a>
</div>
<div data-testid="game-row">
  <div data-testid="time-item"><p>18:00</p></div>
  <div data-testid="game-status-box">FinishedFIN</div>
  <a href="/football/england/premier-league/finished-match/bbbb2222">link</a>
</div>
<div data-testid="game-row">
  <a href="/football/england/premier-league/no-status-box/cccc3333">link</a>
</div>
<div data-testid="game-row">
  <div data-testid="time-item"><p class="text-red-dark">1S</p></div>
  <div data-testid="game-status-box"></div>
  <a href="/volleyball/world/friendly/live-match/dddd4444">link</a>
</div>
</body></html>
"""


@pytest.mark.asyncio
async def test_extract_match_links_skips_started_rows_when_requested(setup_base_scraper_mocks):
    """With skip_started=True, finished AND live rows are dropped; upcoming
    and the no-status-box fail-safe row are kept."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_LISTING_HTML)

    result = await scraper.extract_match_links(page=page_mock, skip_started=True)

    assert any("upcoming-match/aaaa1111" in url for url in result)
    assert any("no-status-box/cccc3333" in url for url in result)
    assert not any("finished-match/bbbb2222" in url for url in result)
    assert not any("live-match/dddd4444" in url for url in result)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_extract_match_links_default_keeps_started_rows(setup_base_scraper_mocks):
    """Default (skip_started=False) preserves prior behaviour: all rows are
    kept regardless of status."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_LISTING_HTML)

    result = await scraper.extract_match_links(page=page_mock)

    assert len(result) == 4
    assert any("finished-match/bbbb2222" in url for url in result)
    assert any("live-match/dddd4444" in url for url in result)


class TestRowHasStarted:
    """Unit tests for the _row_has_started helper (GitHub issue #58)."""

    def _row(self, html: str):
        return BeautifulSoup(f'<div data-testid="game-row">{html}</div>', "lxml").find(
            attrs={"data-testid": "game-row"}
        )

    def test_upcoming_clock_time_means_not_started(self):
        assert (
            _row_has_started(
                self._row('<div data-testid="time-item"><p>21:00</p></div><div data-testid="game-status-box"></div>')
            )
            is False
        )

    def test_single_digit_hour_clock_time_means_not_started(self):
        assert _row_has_started(self._row('<div data-testid="time-item"><p>9:00</p></div>')) is False

    def test_finished_status_box_means_started(self):
        assert (
            _row_has_started(
                self._row(
                    '<div data-testid="time-item"><p>18:00</p></div>'
                    '<div data-testid="game-status-box">FinishedFIN</div>'
                )
            )
            is True
        )

    def test_live_period_marker_means_started(self):
        """Live volleyball: status-box empty, time-item shows a set marker."""
        assert (
            _row_has_started(
                self._row(
                    '<div data-testid="time-item"><p class="text-red-dark">4S</p></div>'
                    '<div data-testid="game-status-box"></div>'
                )
            )
            is True
        )

    def test_live_football_half_marker_means_started(self):
        assert _row_has_started(self._row('<div data-testid="time-item"><p class="text-red-dark">HT</p></div>')) is True

    def test_missing_both_elements_is_failsafe_keep(self):
        """Row without status-box AND without time-item (DOM drift) is treated
        as upcoming so we don't silently drop everything when OddsPortal
        renames things."""
        assert _row_has_started(self._row("<span>no markers here</span>")) is False

    def test_empty_time_item_is_failsafe_keep(self):
        """Time-item present but empty: don't guess; keep the row."""
        assert _row_has_started(self._row('<div data-testid="time-item"></div>')) is False


# -- Date header parser ---------------------------------------------------


class TestParseDateHeader:
    """Unit tests for the _parse_date_header helper."""

    def test_today_returns_today_in_utc_by_default(self):
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Today, 14 Apr") == today_utc

    def test_tomorrow_returns_today_plus_one_day(self):
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Tomorrow, 15 Apr") == today_utc + timedelta(days=1)

    def test_yesterday_returns_today_minus_one_day(self):
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Yesterday, 13 Apr") == today_utc - timedelta(days=1)

    def test_explicit_date_with_year(self):
        assert _parse_date_header("18 Apr 2026") == date(2026, 4, 18)

    def test_explicit_date_with_full_month_name(self):
        # Only first 3 chars are looked up, so "April" should work the same as "Apr"
        assert _parse_date_header("18 April 2026") == date(2026, 4, 18)

    def test_tournament_suffix_is_stripped(self):
        assert _parse_date_header("18 Apr 2026 - Apertura") == date(2026, 4, 18)

    def test_today_with_tournament_suffix(self):
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Today, 14 Apr  - Apertura") == today_utc

    def test_date_without_year_uses_current_year(self):
        # Use a month close to today to avoid the >180 days roll-over heuristic
        today = datetime.now(ZoneInfo("UTC")).date()
        result = _parse_date_header(f"{today.day:02d} {today.strftime('%b')}")
        assert result == today

    def test_empty_string_returns_none(self):
        assert _parse_date_header("") is None

    def test_garbage_string_returns_none(self):
        assert _parse_date_header("not a date") is None

    def test_invalid_day_returns_none(self):
        assert _parse_date_header("99 Apr 2026") is None

    def test_invalid_month_returns_none(self):
        assert _parse_date_header("18 Xyz 2026") is None

    def test_invalid_tz_falls_back_to_utc(self):
        # Unknown tz name should not crash, should fall back to UTC silently
        today_utc = datetime.now(ZoneInfo("UTC")).date()
        assert _parse_date_header("Today, 14 Apr", tz_name="Not/A_Real_Zone") == today_utc

    def test_custom_timezone_used_for_today(self):
        # "Today" should resolve to current date in the specified timezone
        tokyo_today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
        assert _parse_date_header("Today, 14 Apr", tz_name="Asia/Tokyo") == tokyo_today


# -- extract_match_links with date_filter ---------------------------------


def _make_league_page_html() -> str:
    """Build a minimal OddsPortal-like HTML page with 3 date groups."""
    return """
    <html><body>
        <div data-testid="secondary-header"><div data-testid="date-header">Today, 14 Apr</div></div>
        <div data-testid="game-row">
        <a href="/football/england/premier-league/match-one/aaaaaaa1">Match 1</a>
      </div>
      <div data-testid="game-row">
        <a href="/football/england/premier-league/match-two/aaaaaaa2">Match 2</a>
      </div>
        <div data-testid="secondary-header"><div data-testid="date-header">18 Apr 2026</div></div>
        <div data-testid="game-row">
        <a href="/football/england/premier-league/match-three/aaaaaaa3">Match 3</a>
      </div>
      <div data-testid="game-row">
        <a href="/football/england/premier-league/match-four/aaaaaaa4">Match 4</a>
      </div>
        <div data-testid="secondary-header"><div data-testid="date-header">19 Apr 2026</div></div>
        <div data-testid="game-row">
        <a href="/football/england/premier-league/match-five/aaaaaaa5">Match 5</a>
      </div>
    </body></html>
    """


@pytest.mark.asyncio
async def test_extract_match_links_date_filter_matches_one_group(setup_base_scraper_mocks):
    """Only rows under the matching date-header should be kept."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_make_league_page_html())

    result = await scraper.extract_match_links(page=page_mock, date_filter=date(2026, 4, 18))

    # Match 3 and Match 4 both inherit the "18 Apr 2026" header (Match 4 has no
    # header of its own so it inherits from the previous one).
    assert result == [
        f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/match-three/aaaaaaa3",
        f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/match-four/aaaaaaa4",
    ]


@pytest.mark.asyncio
async def test_extract_match_links_date_filter_no_match_returns_empty(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_make_league_page_html())

    result = await scraper.extract_match_links(page=page_mock, date_filter=date(2030, 1, 1))
    assert result == []


@pytest.mark.asyncio
async def test_extract_match_links_date_filter_none_preserves_all_links(setup_base_scraper_mocks):
    """Regression baseline: without date_filter, all links are returned."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_make_league_page_html())

    result = await scraper.extract_match_links(page=page_mock)
    assert len(result) == 5
    assert all("/match-" in link for link in result)


@pytest.mark.asyncio
async def test_extract_match_links_unparseable_header_fails_safe(setup_base_scraper_mocks):
    """Rows under an unparseable header should be kept (fail-safe)."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
            <div data-testid="secondary-header"><div data-testid="date-header">Some gibberish</div></div>
            <div data-testid="game-row">
            <a href="/football/england/premier-league/match-x/xxxxxxx1">Match X</a>
          </div>
            <div data-testid="secondary-header"><div data-testid="date-header">18 Apr 2026</div></div>
            <div data-testid="game-row">
            <a href="/football/england/premier-league/match-y/yyyyyyy1">Match Y</a>
          </div>
        </body></html>
        """
    )

    result = await scraper.extract_match_links(page=page_mock, date_filter=date(2026, 4, 18))

    # Match X survives because its header is unparseable (fail-safe).
    # Match Y matches the filter explicitly.
    assert f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/match-x/xxxxxxx1" in result
    assert f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/match-y/yyyyyyy1" in result


@pytest.mark.asyncio
async def test_extract_match_links_date_filter_no_match_logs_timezone_diagnostic(setup_base_scraper_mocks, caplog):
    """A 0-result date filter emits a diagnostic listing the headers seen and
    the --timezone hint (GitHub issue #58 follow-up)."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_make_league_page_html())

    with caplog.at_level("WARNING"):
        result = await scraper.extract_match_links(page=page_mock, date_filter=date(2030, 1, 1))

    assert result == []
    diagnostic = [r.message for r in caplog.records if "matched 0 matches" in r.message]
    assert diagnostic, "Expected a 0-result date-filter diagnostic warning"
    assert "2026-04-18" in diagnostic[0]
    assert "2026-04-19" in diagnostic[0]
    assert "--timezone" in diagnostic[0]


@pytest.mark.asyncio
async def test_extract_match_links_date_filter_match_emits_no_diagnostic(setup_base_scraper_mocks, caplog):
    """When the date filter yields matches, no 0-result diagnostic is logged."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_make_league_page_html())

    with caplog.at_level("WARNING"):
        result = await scraper.extract_match_links(page=page_mock, date_filter=date(2026, 4, 18))

    assert result
    assert not [r for r in caplog.records if "matched 0 matches" in r.message]


@pytest.mark.asyncio
async def test_extract_match_links_deduplicates_preserving_order(setup_base_scraper_mocks):
    """Duplicate links across rows should be deduplicated while preserving order."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
          <div data-testid="game-row">
            <a href="/football/england/premier-league/match-one/aaaaaaa1">L1</a>
            <a href="/football/england/premier-league/match-one/aaaaaaa1">L1 dup</a>
          </div>
          <div data-testid="game-row">
            <a href="/football/england/premier-league/match-two/aaaaaaa2">L2</a>
          </div>
        </body></html>
        """
    )

    result = await scraper.extract_match_links(page=page_mock)
    assert result == [
        f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/match-one/aaaaaaa1",
        f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/match-two/aaaaaaa2",
    ]


@pytest.mark.asyncio
async def test_extract_match_links_uses_playwright_manager_timezone(setup_base_scraper_mocks):
    """Reference timezone should be read from PlaywrightManager when filtering."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "Asia/Tokyo"

    # "Today" in Tokyo becomes the reference date
    tokyo_today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
            <div data-testid="secondary-header"><div data-testid="date-header">Today, 14 Apr</div></div>
            <div data-testid="game-row">
            <a href="/football/england/premier-league/tokyo-match/tttttttt">Tokyo match</a>
          </div>
        </body></html>
        """
    )

    result = await scraper.extract_match_links(page=page_mock, date_filter=tokyo_today)
    assert len(result) == 1


# -- extract_match_links with kickoff_within_hours (GitHub issue #77) --------


class _FixedNow(datetime):
    """datetime subclass whose ``now()`` is frozen for deterministic window
    tests. ``combine`` and the constructor are inherited unchanged."""

    _frozen = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls._frozen if tz is None else cls._frozen.astimezone(tz)


def _make_kickoff_window_html() -> str:
    """Listing with one date group ('18 Apr 2026') and three kickoff times.

    Against the frozen now (12:00 on 18 Apr 2026): Soon is 1h away, Edge 1.5h
    away, Late 4h away.
    """
    return """
    <html><body>
        <div data-testid="secondary-header"><div data-testid="date-header">18 Apr 2026</div></div>
        <div data-testid="game-row">
        <div data-testid="time-item"><p>13:00</p></div>
        <a href="/football/england/premier-league/soon-match/aaaaaaa1">Soon</a>
      </div>
      <div data-testid="game-row">
        <div data-testid="time-item"><p>13:30</p></div>
        <a href="/football/england/premier-league/edge-match/aaaaaaa2">Edge</a>
      </div>
      <div data-testid="game-row">
        <div data-testid="time-item"><p>16:00</p></div>
        <a href="/football/england/premier-league/late-match/aaaaaaa3">Late</a>
      </div>
    </body></html>
    """


@pytest.mark.asyncio
async def test_extract_match_links_kickoff_window_keeps_only_matches_within_window(setup_base_scraper_mocks):
    """Only matches kicking off within the window are kept; later ones dropped."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_make_kickoff_window_html())

    with patch("oddsharvester.core.base_scraper.datetime", _FixedNow):
        result = await scraper.extract_match_links(page=page_mock, kickoff_within_hours=2)

    assert any("soon-match/aaaaaaa1" in url for url in result)
    assert any("edge-match/aaaaaaa2" in url for url in result)
    assert not any("late-match/aaaaaaa3" in url for url in result)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_extract_match_links_kickoff_window_none_preserves_all(setup_base_scraper_mocks):
    """Regression: without the window filter, all rows are returned."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_make_kickoff_window_html())

    result = await scraper.extract_match_links(page=page_mock)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_extract_match_links_kickoff_window_unparseable_time_fails_safe(setup_base_scraper_mocks):
    """A row with no parseable HH:MM (e.g. a live marker) has no computable
    kickoff, so it is kept rather than silently dropped."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
            <div data-testid="secondary-header"><div data-testid="date-header">18 Apr 2026</div></div>
            <div data-testid="game-row">
            <div data-testid="time-item"><p class="text-red-dark">1H</p></div>
            <a href="/football/england/premier-league/live-match/bbbbbbb1">Live</a>
          </div>
          <div data-testid="game-row">
            <div data-testid="time-item"><p>16:00</p></div>
            <a href="/football/england/premier-league/late-match/bbbbbbb2">Late</a>
          </div>
        </body></html>
        """
    )

    with patch("oddsharvester.core.base_scraper.datetime", _FixedNow):
        result = await scraper.extract_match_links(page=page_mock, kickoff_within_hours=1)

    assert any("live-match/bbbbbbb1" in url for url in result)
    assert not any("late-match/bbbbbbb2" in url for url in result)


@pytest.mark.asyncio
async def test_extract_match_links_kickoff_window_row_without_date_header_fails_safe(setup_base_scraper_mocks):
    """Without a date-header, a row's kickoff date is unknown, so it is kept."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
          <div data-testid="game-row">
            <div data-testid="time-item"><p>16:00</p></div>
            <a href="/football/england/premier-league/orphan-match/ccccccc1">Orphan</a>
          </div>
        </body></html>
        """
    )

    with patch("oddsharvester.core.base_scraper.datetime", _FixedNow):
        result = await scraper.extract_match_links(page=page_mock, kickoff_within_hours=1)

    assert any("orphan-match/ccccccc1" in url for url in result)


@pytest.mark.asyncio
async def test_extract_match_links_kickoff_window_composes_with_skip_started(setup_base_scraper_mocks):
    """Window filter and skip_started compose: started rows dropped by
    skip_started, far-future rows dropped by the window, the near upcoming row
    survives."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
            <div data-testid="secondary-header"><div data-testid="date-header">18 Apr 2026</div></div>
            <div data-testid="game-row">
            <div data-testid="time-item"><p>13:00</p></div>
            <div data-testid="game-status-box"></div>
            <a href="/football/england/premier-league/near-upcoming/ddddddd1">Near</a>
          </div>
          <div data-testid="game-row">
            <div data-testid="time-item"><p>11:00</p></div>
            <div data-testid="game-status-box">FinishedFIN</div>
            <a href="/football/england/premier-league/finished/ddddddd2">Finished</a>
          </div>
          <div data-testid="game-row">
            <div data-testid="time-item"><p>16:00</p></div>
            <div data-testid="game-status-box"></div>
            <a href="/football/england/premier-league/far-future/ddddddd3">Far</a>
          </div>
        </body></html>
        """
    )

    with patch("oddsharvester.core.base_scraper.datetime", _FixedNow):
        result = await scraper.extract_match_links(page=page_mock, kickoff_within_hours=2, skip_started=True)

    assert any("near-upcoming/ddddddd1" in url for url in result)
    assert not any("finished/ddddddd2" in url for url in result)
    assert not any("far-future/ddddddd3" in url for url in result)
    assert len(result) == 1


class TestRowKickoffDatetime:
    """Unit tests for the _row_kickoff_datetime helper (GitHub issue #77)."""

    def _row(self, html: str):
        return BeautifulSoup(f'<div data-testid="game-row">{html}</div>', "lxml").find(
            attrs={"data-testid": "game-row"}
        )

    def test_valid_time_and_date_returns_aware_datetime(self):
        row = self._row('<div data-testid="time-item"><p>21:00</p></div>')
        assert _row_kickoff_datetime(row, date(2026, 4, 18), UTC) == datetime(2026, 4, 18, 21, 0, tzinfo=UTC)

    def test_single_digit_hour_parsed(self):
        row = self._row('<div data-testid="time-item"><p>9:05</p></div>')
        assert _row_kickoff_datetime(row, date(2026, 4, 18), UTC) == datetime(2026, 4, 18, 9, 5, tzinfo=UTC)

    def test_none_row_date_returns_none(self):
        row = self._row('<div data-testid="time-item"><p>21:00</p></div>')
        assert _row_kickoff_datetime(row, None, UTC) is None

    def test_missing_time_item_returns_none(self):
        row = self._row("<span>no time here</span>")
        assert _row_kickoff_datetime(row, date(2026, 4, 18), UTC) is None

    def test_empty_time_item_returns_none(self):
        row = self._row('<div data-testid="time-item"></div>')
        assert _row_kickoff_datetime(row, date(2026, 4, 18), UTC) is None

    def test_live_marker_returns_none(self):
        row = self._row('<div data-testid="time-item"><p>1H</p></div>')
        assert _row_kickoff_datetime(row, date(2026, 4, 18), UTC) is None

    def test_invalid_clock_returns_none(self):
        row = self._row('<div data-testid="time-item"><p>25:00</p></div>')
        assert _row_kickoff_datetime(row, date(2026, 4, 18), UTC) is None


# -- extract_match_rows kickoff column (GitHub issue #81) --------------------


def _make_kickoff_column_html() -> str:
    """One date group, a normal row and a started row (live period marker)."""
    return """
    <html><body>
        <div data-testid="secondary-header"><div data-testid="date-header">18 Apr 2026</div></div>
        <div data-testid="game-row">
        <div data-testid="time-item"><p>20:30</p></div>
        <a href="/football/england/premier-league/normal-match/aaaaaaa1">Normal</a>
      </div>
      <div data-testid="game-row">
        <div data-testid="time-item"><p>1H</p></div>
        <a href="/football/england/premier-league/started-match/aaaaaaa2">Started</a>
      </div>
    </body></html>
    """


@pytest.mark.asyncio
async def test_extract_match_rows_converts_kickoff_from_browser_tz_to_utc(setup_base_scraper_mocks):
    """Listing times render in the browser timezone (gotcha 10); output is UTC."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "Europe/Paris"
    page_mock.content = AsyncMock(return_value=_make_kickoff_column_html())

    rows = await scraper.extract_match_rows(page=page_mock, collect_kickoff=True)

    normal = next(r for r in rows if "normal-match/aaaaaaa1" in r["match_link"])
    assert normal["kickoff_utc"] == "2026-04-18 18:30:00 UTC"


@pytest.mark.asyncio
async def test_extract_match_rows_without_collect_kickoff_leaves_every_kickoff_null(setup_base_scraper_mocks):
    """The default keeps the historic pagination path at its current behaviour."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "Europe/Paris"
    page_mock.content = AsyncMock(return_value=_make_kickoff_column_html())

    rows = await scraper.extract_match_rows(page=page_mock)

    assert len(rows) == 2
    assert all(row["kickoff_utc"] is None for row in rows)


@pytest.mark.asyncio
async def test_extract_match_rows_started_row_has_null_kickoff(setup_base_scraper_mocks):
    """A started row (time-item is a period marker) yields no kickoff, and is
    only reachable at all because skip_started defaults to False."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"
    page_mock.content = AsyncMock(return_value=_make_kickoff_column_html())

    rows = await scraper.extract_match_rows(page=page_mock, collect_kickoff=True)

    started = next(r for r in rows if "started-match/aaaaaaa2" in r["match_link"])
    assert started["kickoff_utc"] is None


@pytest.mark.asyncio
async def test_extract_match_rows_unparseable_date_header_yields_null_kickoff(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
            <div data-testid="secondary-header"><div data-testid="date-header">Not A Date</div></div>
            <div data-testid="game-row">
            <div data-testid="time-item"><p>20:30</p></div>
            <a href="/football/england/premier-league/orphan-match/aaaaaaa3">Orphan</a>
          </div>
        </body></html>
        """
    )

    rows = await scraper.extract_match_rows(page=page_mock, collect_kickoff=True)

    assert len(rows) == 1
    assert rows[0]["kickoff_utc"] is None


@pytest.mark.asyncio
async def test_extract_match_rows_missing_time_item_yields_null_kickoff(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
            <div data-testid="secondary-header"><div data-testid="date-header">18 Apr 2026</div></div>
            <div data-testid="game-row">
            <a href="/football/england/premier-league/no-time/aaaaaaa4">No time</a>
          </div>
        </body></html>
        """
    )

    rows = await scraper.extract_match_rows(page=page_mock, collect_kickoff=True)

    assert len(rows) == 1
    assert rows[0]["kickoff_utc"] is None


@pytest.mark.asyncio
async def test_extract_match_rows_shares_one_kickoff_across_a_rows_links(setup_base_scraper_mocks):
    """A row can yield several links; each carries that row's kickoff."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
            <div data-testid="secondary-header"><div data-testid="date-header">18 Apr 2026</div></div>
            <div data-testid="game-row">
            <div data-testid="time-item"><p>20:30</p></div>
            <a href="/football/england/premier-league/first-match/aaaaaaa5">First</a>
            <a href="/football/england/premier-league/second-match/aaaaaaa6">Second</a>
          </div>
        </body></html>
        """
    )

    rows = await scraper.extract_match_rows(page=page_mock, collect_kickoff=True)

    assert len(rows) == 2
    assert {row["kickoff_utc"] for row in rows} == {"2026-04-18 20:30:00 UTC"}


@pytest.mark.asyncio
async def test_extract_match_links_still_returns_plain_strings(setup_base_scraper_mocks):
    """Contract guard: the historic pagination path reads bare URLs."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=_make_kickoff_column_html())

    result = await scraper.extract_match_links(page=page_mock)

    assert len(result) == 2
    assert all(isinstance(url, str) for url in result)


# -- _is_offscreen_row + offscreen filtering (regression: issue #61) ---------


class TestIsOffscreenRow:
    """Unit tests for the _is_offscreen_row helper."""

    def test_no_style_attr_is_visible(self):
        row = BeautifulSoup('<div data-testid="game-row"></div>', "lxml").div
        assert _is_offscreen_row(row) is False

    def test_empty_style_is_visible(self):
        row = BeautifulSoup('<div data-testid="game-row" style=""></div>', "lxml").div
        assert _is_offscreen_row(row) is False

    def test_left_minus_9999_marks_offscreen(self):
        row = BeautifulSoup(
            '<div data-testid="game-row" style="position: absolute; left: -9999px;"></div>',
            "lxml",
        ).div
        assert _is_offscreen_row(row) is True

    def test_top_minus_9999_marks_offscreen(self):
        row = BeautifulSoup('<div data-testid="game-row" style="top:-9999px"></div>', "lxml").div
        assert _is_offscreen_row(row) is True

    def test_display_none_marks_offscreen(self):
        row = BeautifulSoup('<div data-testid="game-row" style="display: none;"></div>', "lxml").div
        assert _is_offscreen_row(row) is True

    def test_visibility_hidden_marks_offscreen(self):
        row = BeautifulSoup('<div data-testid="game-row" style="visibility:hidden"></div>', "lxml").div
        assert _is_offscreen_row(row) is True

    def test_uppercase_style_normalized(self):
        row = BeautifulSoup('<div data-testid="game-row" style="DISPLAY: NONE"></div>', "lxml").div
        assert _is_offscreen_row(row) is True

    def test_unrelated_style_is_visible(self):
        row = BeautifulSoup(
            '<div data-testid="game-row" style="color: red; padding-left: 9999px;"></div>',
            "lxml",
        ).div
        assert _is_offscreen_row(row) is False


@pytest.mark.asyncio
async def test_extract_match_links_skips_offscreen_phantom_row(setup_base_scraper_mocks):
    """Regression for issue #61: OddsPortal sometimes duplicates an event row
    in the DOM — one visible, one CSS-hidden offscreen with a corrupted href
    that 301-redirects to an unrelated match. Only the visible row should
    be kept.

    Captured from the live Super Lig listing (2026-05-11): both rows share
    the same OddsPortal row id; the phantom carries the live IDs of an
    unrelated 2017 Czech 2.Liga match.
    """
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
          <div data-testid="game-row" id="4CyOBFbK" set="92939"
               style="position: absolute; left: -9999px; height: 0px; overflow: hidden;">
            <a href="/football/h2h/galatasaray-0j2eUlMC/kasimpasa-EXCPojim/#Aonqhgqt">phantom</a>
          </div>
          <div data-testid="game-row" id="4CyOBFbK" set="92939">
            <a href="/football/h2h/galatasaray-riaqqurF/kasimpasa-dOlaIG4l/#4CyOBFbK">real</a>
          </div>
        </body></html>
        """
    )

    result = await scraper.extract_match_links(page=page_mock)

    assert result == [
        f"{ODDSPORTAL_BASE_URL}/football/h2h/galatasaray-riaqqurF/kasimpasa-dOlaIG4l/#4CyOBFbK",
    ]


@pytest.mark.asyncio
async def test_extract_match_links_offscreen_skipped_before_date_filter(setup_base_scraper_mocks):
    """An offscreen row must be skipped even if its inherited date-header
    matches the filter — otherwise the phantom URL leaks into the results."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
            <div data-testid="secondary-header"><div data-testid="date-header">17 May 2026</div></div>
            <div data-testid="game-row">
            <a href="/football/h2h/real-aaa/match-bbb/#x1">real</a>
          </div>
          <div data-testid="game-row" style="position:absolute;left:-9999px;">
            <a href="/football/h2h/phantom-ccc/match-ddd/#x2">phantom</a>
          </div>
        </body></html>
        """
    )

    result = await scraper.extract_match_links(page=page_mock, date_filter=date(2026, 5, 17))

    assert result == [f"{ODDSPORTAL_BASE_URL}/football/h2h/real-aaa/match-bbb/#x1"]


@pytest.mark.asyncio
async def test_extract_match_links_offscreen_row_does_not_carry_date_header(setup_base_scraper_mocks):
    """If a phantom row carries the only date-header on the page, skipping it
    should not strip the header inheritance for following visible rows."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
          <div data-testid="game-row" style="display:none;">
            <div data-testid="date-header">17 May 2026</div>
            <a href="/football/h2h/phantom-ccc/match-ddd/#x2">phantom</a>
          </div>
            <div data-testid="secondary-header"><div data-testid="date-header">17 May 2026</div></div>
            <div data-testid="game-row">
            <a href="/football/h2h/real-aaa/match-bbb/#x1">real</a>
          </div>
        </body></html>
        """
    )

    result = await scraper.extract_match_links(page=page_mock, date_filter=date(2026, 5, 17))

    assert result == [f"{ODDSPORTAL_BASE_URL}/football/h2h/real-aaa/match-bbb/#x1"]


@pytest.mark.asyncio
async def test_extract_match_odds(setup_base_scraper_mocks):
    """Test extracting odds for multiple match links concurrently."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    pm = mocks["playwright_manager_mock"]

    # Mock _scrape_match_data to return data directly
    scraper._scrape_match_data = AsyncMock(side_effect=[{"match": "data1"}, {"match": "data2"}])

    # Call the method under test
    match_links = ["https://oddsportal.com/match1", "https://oddsportal.com/match2"]

    async def mock_gather(*args):
        results = []
        for task in args:
            if callable(task):
                result = await task()
            else:
                result = await task
            results.append(result)
        return results

    # Patch asyncio.gather temporarily
    with patch("asyncio.gather", side_effect=mock_gather):
        result = await scraper.extract_match_odds(
            sport="football", match_links=match_links, markets=["1x2"], scrape_odds_history=False
        )

    # Verify a rotated page was acquired for each match link
    assert pm.new_rotated_page.await_count == 2

    # Verify the result is a ScrapeResult with successful matches
    assert len(result.success) == 2
    assert {"match": "data1"} in result.success
    assert {"match": "data2"} in result.success
    assert result.stats.total_urls == 2
    assert result.stats.successful == 2
    assert result.stats.failed == 0


@pytest.mark.asyncio
async def test_extract_match_odds_warms_non_default_contexts(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    pm = mocks["playwright_manager_mock"]
    pm.non_default_context_keys = MagicMock(return_value=["http://b.example.com:2"])

    await scraper.extract_match_odds(sport="football", match_links=[], markets=["1x2"])

    pm.new_page_on_key.assert_awaited_with("http://b.example.com:2")
    assert "http://b.example.com:2" in scraper._warmed_proxy_keys


@pytest.mark.asyncio
async def test_warm_failure_blacklists_proxy(setup_base_scraper_mocks):
    """A proxy whose context can't be warmed must be removed from rotation entirely,
    not merely dinged with a single strike - a cold context silently corrupts odds."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    pm = mocks["playwright_manager_mock"]
    pm.non_default_context_keys = MagicMock(return_value=["http://b.example.com:2"])
    mocks["page_mock"].goto = AsyncMock(side_effect=Exception("Page.goto: net::ERR_PROXY_CONNECTION_FAILED"))
    pm.new_page_on_key = AsyncMock(return_value=mocks["page_mock"])
    pm.blacklist_proxy = MagicMock()

    await scraper.extract_match_odds(sport="football", match_links=[], markets=["1x2"])

    pm.blacklist_proxy.assert_called_once_with("http://b.example.com:2")


@pytest.mark.asyncio
async def test_extract_match_odds_uses_rotated_page(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    pm = mocks["playwright_manager_mock"]

    await scraper.extract_match_odds(
        sport="football", match_links=["https://www.oddsportal.com/football/x/y/#z"], markets=["1x2"]
    )

    pm.new_rotated_page.assert_awaited()
    pm.report_page_result.assert_called()


@pytest.mark.asyncio
async def test_scrape_match_data(setup_base_scraper_mocks):
    """Test scraping data for a specific match."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock _extract_match_details
    scraper._hydrate_match_view = AsyncMock()
    scraper._dismiss_login_modal = AsyncMock()
    scraper._extract_match_details = AsyncMock(
        return_value={"home_team": "Arsenal", "away_team": "Chelsea", "match_date": "2023-05-01 20:00:00 UTC"}
    )

    # Mock market_extractor.scrape_markets
    mocks["market_extractor_mock"].scrape_markets = AsyncMock(
        return_value={
            "1x2": {"odds": [2.0, 3.5, 4.0], "bookmakers": ["bet365", "bwin", "unibet"]},
            "over_under_2_5": {"odds": [1.8, 2.1], "bookmakers": ["bet365", "bwin"]},
        }
    )

    page_mock.wait_for_timeout = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()

    # Call the method under test
    result = await scraper._scrape_match_data(
        page=page_mock,
        sport="football",
        match_link="https://oddsportal.com/football/england/arsenal-chelsea/123456",
        markets=["1x2", "over_under_2_5"],
        scrape_odds_history=True,
        target_bookmaker="bet365",
    )

    # Verify interactions
    page_mock.goto.assert_called_once_with(
        "https://oddsportal.com/football/england/arsenal-chelsea/123456",
        timeout=NAVIGATION_TIMEOUT_MS,
        wait_until="domcontentloaded",
    )

    scraper._extract_match_details.assert_called_once_with(
        page_mock, "https://oddsportal.com/football/england/arsenal-chelsea/123456"
    )

    mocks["market_extractor_mock"].scrape_markets.assert_called_once_with(
        page=page_mock,
        sport="football",
        markets=["1x2", "over_under_2_5"],
        period=None,
        scrape_odds_history=True,
        target_bookmaker="bet365",
        preview_submarkets_only=False,
    )

    # Verify the bookies filter was applied via SelectionManager with the right strategy
    from oddsharvester.core.browser.selection import BOOKIES_FILTER_STRATEGY
    from oddsharvester.utils.bookies_filter_enum import BookiesFilter

    mocks["selection_manager_mock"].ensure_selected.assert_called_once_with(
        page=page_mock,
        target_value=BookiesFilter.ALL.value,
        display_label=BookiesFilter.get_display_label(BookiesFilter.ALL),
        strategy=BOOKIES_FILTER_STRATEGY,
    )

    # Verify results
    assert result["home_team"] == "Arsenal"
    assert result["away_team"] == "Chelsea"
    assert result["match_date"] == "2023-05-01 20:00:00 UTC"
    assert "1x2" in result
    assert "over_under_2_5" in result


@pytest.mark.asyncio
async def test_scrape_match_data_no_details(setup_base_scraper_mocks):
    """Test scraping match data when no match details are found."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock _extract_match_details returning None
    scraper._hydrate_match_view = AsyncMock()
    scraper._dismiss_login_modal = AsyncMock()
    scraper._extract_match_details = AsyncMock(return_value=None)

    page_mock.wait_for_timeout = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()

    # Call the method under test
    result = await scraper._scrape_match_data(
        page=page_mock,
        sport="football",
        match_link="https://oddsportal.com/football/england/arsenal-chelsea/123456",
        markets=["1x2"],
    )

    # Verify result is None when no match details are found
    assert result is None
    # Verify market_extractor.scrape_markets was not called
    mocks["market_extractor_mock"].scrape_markets.assert_not_called()


@pytest.mark.asyncio
async def test_scrape_match_data_reraises_proxy_error(setup_base_scraper_mocks):
    """Proxy-attributable navigation errors must propagate so failover can blacklist the dead proxy."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]

    mocks["page_mock"].goto = AsyncMock(side_effect=Exception("Page.goto: net::ERR_PROXY_CONNECTION_FAILED"))

    with pytest.raises(Exception, match="ERR_PROXY_CONNECTION_FAILED"):
        await scraper._scrape_match_data(
            page=mocks["page_mock"],
            sport="football",
            match_link="https://www.oddsportal.com/football/x/y/",
        )


@pytest.mark.asyncio
async def test_scrape_match_data_swallows_post_navigation_error(setup_base_scraper_mocks):
    """Errors raised after a successful goto (DOM/selector drift) must degrade gracefully to
    None, not be attributed to the proxy - navigation already succeeded."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]

    mocks["selection_manager_mock"].ensure_selected = AsyncMock(side_effect=Exception("boom"))

    result = await scraper._scrape_match_data(
        page=mocks["page_mock"],
        sport="football",
        match_link="https://www.oddsportal.com/football/x/y/",
    )

    assert result is None


@pytest.mark.asyncio
@patch("oddsharvester.core.base_scraper.asyncio.sleep", new_callable=AsyncMock)
async def test_extract_match_odds_rate_limiting(mock_sleep, setup_base_scraper_mocks):
    """Test that rate limiting delay is applied between match requests."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]

    # Mock _scrape_match_data to return data directly
    scraper._scrape_match_data = AsyncMock(side_effect=[{"match": "data1"}, {"match": "data2"}, {"match": "data3"}])

    match_links = [
        "https://oddsportal.com/match1",
        "https://oddsportal.com/match2",
        "https://oddsportal.com/match3",
    ]

    # Use concurrent_scraping_task=1 to force sequential execution for predictable test behavior
    result = await scraper.extract_match_odds(
        sport="football",
        match_links=match_links,
        markets=["1x2"],
        concurrent_scraping_task=1,
        request_delay=2.0,
    )

    # First request should not have a delay, subsequent ones should
    # With concurrency=1, requests are sequential so we expect 2 sleep calls (for 2nd and 3rd requests)
    assert mock_sleep.call_count == 2
    assert len(result.success) == 3


@pytest.mark.asyncio
@patch("oddsharvester.core.base_scraper.asyncio.sleep", new_callable=AsyncMock)
async def test_extract_match_odds_no_delay_when_zero(mock_sleep, setup_base_scraper_mocks):
    """Test that no delay is applied when request_delay is 0."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]

    scraper._scrape_match_data = AsyncMock(side_effect=[{"match": "data1"}, {"match": "data2"}])

    match_links = ["https://oddsportal.com/match1", "https://oddsportal.com/match2"]

    result = await scraper.extract_match_odds(
        sport="football",
        match_links=match_links,
        markets=["1x2"],
        concurrent_scraping_task=1,
        request_delay=0,
    )

    mock_sleep.assert_not_called()
    assert len(result.success) == 2


def test_resolved_browser_timezone_defaults_to_utc(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    mocks["playwright_manager_mock"].timezone_id = None
    assert scraper._resolved_browser_timezone() == ZoneInfo("UTC")


def test_resolved_browser_timezone_uses_configured_tz(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    mocks["playwright_manager_mock"].timezone_id = "Europe/Brussels"
    assert scraper._resolved_browser_timezone() == ZoneInfo("Europe/Brussels")


def test_resolved_browser_timezone_falls_back_on_unknown(setup_base_scraper_mocks, caplog):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    mocks["playwright_manager_mock"].timezone_id = "Not/A/Real/Zone"
    with caplog.at_level(logging.WARNING):
        result = scraper._resolved_browser_timezone()
    # Fallback returns the stdlib UTC constant (datetime.timezone.utc), which is
    # not equal to ZoneInfo("UTC"); assert on the offset instead so this stays
    # robust to either tzinfo implementation.
    assert result.utcoffset(datetime(2024, 1, 1)) == timedelta(0)
    assert any("Not/A/Real/Zone" in rec.message for rec in caplog.records)


def test_resolved_browser_timezone_falls_back_on_malformed_key(setup_base_scraper_mocks, caplog):
    """ZoneInfo raises ValueError (not ZoneInfoNotFoundError) for malformed keys,
    e.g. ones containing "..". Must fall back to UTC like the unknown-zone case.
    """

    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    mocks["playwright_manager_mock"].timezone_id = "../Europe/Brussels"
    with caplog.at_level(logging.WARNING):
        result = scraper._resolved_browser_timezone()
    assert result.utcoffset(datetime(2024, 1, 1)) == timedelta(0)
    assert any("../Europe/Brussels" in rec.message for rec in caplog.records)


def test_resolved_browser_timezone_survives_missing_tzdata(setup_base_scraper_mocks, caplog):
    """Regression: when the tz database is unavailable, ZoneInfo("UTC") itself
    raises ZoneInfoNotFoundError. The fallback must not construct a ZoneInfo at
    all (it must return the stdlib UTC constant) or it will crash the same way.
    """

    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"

    def _no_tzdata(_name):
        raise ZoneInfoNotFoundError(f"No time zone found with key {_name}")

    with patch("oddsharvester.core.base_scraper.ZoneInfo", side_effect=_no_tzdata), caplog.at_level(logging.WARNING):
        result = scraper._resolved_browser_timezone()
    assert result is UTC
    assert result.utcoffset(datetime(2024, 1, 1)) == timedelta(0)


def test_parse_date_header_survives_missing_tzdata():
    """Regression: with tz_name="UTC" and no tz database installed, ZoneInfo
    raises for every name including "UTC". The fallback must return a date
    derived from the stdlib UTC constant, not crash.
    """

    def _no_tzdata(_name):
        raise ZoneInfoNotFoundError(f"No time zone found with key {_name}")

    today_utc = datetime.now(UTC).date()
    with patch("oddsharvester.core.base_scraper.ZoneInfo", side_effect=_no_tzdata):
        assert _parse_date_header("Today, 14 Apr", tz_name="UTC") == today_utc


def _make_date_html(date_str: str = "06 Aug 2022,", time_str: str = "11:30") -> str:
    return f"""
    <html><body>
      <div data-testid="game-time-item">
        <p>Saturday</p>
        <p>{date_str}</p>
        <p>{time_str}</p>
      </div>
    </body></html>
    """


def test_parse_match_date_from_dom_parses_utc_nominal(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    setup_base_scraper_mocks["playwright_manager_mock"].timezone_id = "UTC"
    soup = BeautifulSoup(_make_date_html(), "html.parser")
    assert scraper._parse_match_date_from_dom(soup) == "2022-08-06 11:30:00 UTC"


def test_parse_match_date_from_dom_converts_local_tz_to_utc(setup_base_scraper_mocks):
    # Brussels is UTC+2 in August (DST), so 13:30 Brussels = 11:30 UTC
    scraper = setup_base_scraper_mocks["scraper"]
    setup_base_scraper_mocks["playwright_manager_mock"].timezone_id = "Europe/Brussels"
    soup = BeautifulSoup(_make_date_html(time_str="13:30"), "html.parser")
    assert scraper._parse_match_date_from_dom(soup) == "2022-08-06 11:30:00 UTC"


def test_parse_match_date_from_dom_returns_none_when_div_missing(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert scraper._parse_match_date_from_dom(soup) is None


def test_parse_match_date_from_dom_returns_none_on_unparseable_text(setup_base_scraper_mocks, caplog):
    scraper = setup_base_scraper_mocks["scraper"]
    setup_base_scraper_mocks["playwright_manager_mock"].timezone_id = "UTC"
    soup = BeautifulSoup(_make_date_html(date_str="not a date,", time_str="??:??"), "html.parser")
    with caplog.at_level(logging.WARNING):
        result = scraper._parse_match_date_from_dom(soup)
    assert result is None
    assert any("DOM parse failed for match_date" in rec.message for rec in caplog.records)


def _make_teams_html(home: str | None = "Fulham", away: str | None = "Liverpool") -> str:
    home_block = f'<div data-testid="game-host"><p>{home}</p></div>' if home is not None else ""
    away_block = f'<div data-testid="game-guest"><p>{away}</p></div>' if away is not None else ""
    return f"<html><body>{home_block}{away_block}</body></html>"


def test_parse_teams_from_dom_returns_both_when_present(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup(_make_teams_html(), "html.parser")
    assert scraper._parse_teams_from_dom(soup) == ("Fulham", "Liverpool")


def test_parse_teams_from_dom_returns_none_pair_when_home_missing(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup(_make_teams_html(home=None), "html.parser")
    assert scraper._parse_teams_from_dom(soup) == (None, None)


def test_parse_teams_from_dom_returns_none_pair_when_away_missing(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup(_make_teams_html(away=None), "html.parser")
    assert scraper._parse_teams_from_dom(soup) == (None, None)


def test_parse_teams_from_dom_returns_none_pair_when_both_missing(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert scraper._parse_teams_from_dom(soup) == (None, None)


def _make_league_html(text: str | None = "Premier League 2024/2025", with_link: bool = True) -> str:
    if not with_link:
        return '<html><body><div data-testid="breadcrumbs-line"></div></body></html>'
    return (
        f'<html><body><div data-testid="breadcrumbs-line">'
        f'<a data-testid="0">Football</a>'
        f'<a data-testid="1">England</a>'
        f'<a data-testid="2">Premier League</a>'
        f'<a data-testid="{text}">{text}</a>'
        f"</div></body></html>"
    )


def test_parse_league_from_dom_strips_season_suffix(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup(_make_league_html("Premier League 2024/2025"), "html.parser")
    assert scraper._parse_league_from_dom(soup) == "Premier League"


def test_parse_league_from_dom_keeps_name_without_suffix(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup(_make_league_html("LaLiga"), "html.parser")
    assert scraper._parse_league_from_dom(soup) == "LaLiga"


def test_parse_league_from_dom_handles_multiple_spaces_before_suffix(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup(_make_league_html("LaLiga  2019/2020"), "html.parser")
    assert scraper._parse_league_from_dom(soup) == "LaLiga"


def test_parse_league_from_dom_returns_none_when_link_missing(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup(_make_league_html(with_link=False), "html.parser")
    assert scraper._parse_league_from_dom(soup) is None


def test_parse_league_from_dom_returns_none_when_breadcrumb_missing(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert scraper._parse_league_from_dom(soup) is None


def _make_results_html(score_text: str = "Final result 2:1 (1:0, 1:1)") -> str:
    return f"""
    <html><body>
      <section>
        <div data-testid="game-time-item"><p>x</p><p>06 Aug 2022,</p><p>11:30</p></div>
        <div><span>logos</span></div>
        <div>
          <div class="flex flex-wrap">{score_text}</div>
        </div>
      </section>
    </body></html>
    """


def test_parse_results_from_dom_extracts_score_and_partial(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup(_make_results_html(), "html.parser")
    home, away, partial = scraper._parse_results_from_dom(soup)
    assert home == "2"
    assert away == "1"
    assert partial == "(1:0, 1:1)"


def test_parse_results_from_dom_extracts_score_without_partial(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup(_make_results_html(score_text="Final result 4:0"), "html.parser")
    home, away, partial = scraper._parse_results_from_dom(soup)
    assert home == "4"
    assert away == "0"
    assert partial is None


def test_parse_results_from_dom_returns_none_when_pattern_absent(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup('<html><body><div data-testid="game-time-item"></div></body></html>', "html.parser")
    assert scraper._parse_results_from_dom(soup) == (None, None, None)


def test_parse_results_from_dom_returns_none_when_game_time_div_missing(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    soup = BeautifulSoup("<html><body><div>Final result 2:1 (1:0, 1:1)</div></body></html>", "html.parser")
    assert scraper._parse_results_from_dom(soup) == (None, None, None)


def test_parse_results_from_dom_normalizes_nbsp_in_partial(setup_base_scraper_mocks):
    scraper = setup_base_scraper_mocks["scraper"]
    # OddsPortal renders non-breaking spaces (\xa0) between partial-result tokens.
    soup = BeautifulSoup(_make_results_html("Final result 2:1 (1:0,\xa01:1)"), "html.parser")
    home, away, partial = scraper._parse_results_from_dom(soup)
    assert home == "2"
    assert away == "1"
    assert partial == "(1:0, 1:1)"


def test_extract_fragment_match_id_returns_fragment_when_present():
    url = "https://www.oddsportal.com/baseball/h2h/a-team/b-team/#WbDmMwm1"
    assert _extract_fragment_match_id(url) == "WbDmMwm1"


def test_extract_fragment_match_id_returns_none_when_no_fragment():
    assert _extract_fragment_match_id("https://www.oddsportal.com/baseball/h2h/a/b/") is None


def test_extract_fragment_match_id_returns_none_when_fragment_is_empty():
    assert _extract_fragment_match_id("https://www.oddsportal.com/baseball/h2h/a/b/#") is None


def test_extract_fragment_match_id_returns_none_when_fragment_has_slash():
    # Defensive: a stray slash means it isn't a match-id fragment
    assert _extract_fragment_match_id("https://www.oddsportal.com/x/#a/b") is None


def test_extract_fragment_match_id_strips_whitespace():
    # Some scrapers can produce trailing whitespace from raw href
    assert _extract_fragment_match_id("https://www.oddsportal.com/x/#abc   ") == "abc"


@pytest.mark.asyncio
async def test_scrape_match_data_propagates_h2h_fragment_error(setup_base_scraper_mocks):
    """The hydration failure must survive the broad handler in _scrape_match_data."""
    from oddsharvester.core.exceptions import H2HFragmentResolutionError

    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]

    scraper._dismiss_login_modal = AsyncMock()
    scraper._hydrate_match_view = AsyncMock(
        side_effect=H2HFragmentResolutionError("match view hydration failed: never rendered match content")
    )
    scraper._extract_match_details = AsyncMock()

    with pytest.raises(H2HFragmentResolutionError):
        await scraper._scrape_match_data(
            page=mocks["page_mock"],
            sport="football",
            match_link="https://www.oddsportal.com/football/h2h/a/b/#WbDmMwm1",
        )


# -- base_url storage and match-link join -------------------------------------

_SERIE_A_HREF = "/football/italy/serie-a/match-xyz/"
_SERIE_A_HTML = f"""
<html><body>
  <div data-testid="game-row">
    <a href="{_SERIE_A_HREF}">Serie A match</a>
  </div>
</body></html>
"""


class TestBaseScraperBaseUrl:
    """Tests that BaseScraper stores base_url and applies it when building match links."""

    def test_base_url_defaults_to_none(self, setup_base_scraper_mocks):
        """A scraper constructed without base_url has scraper.base_url is None."""
        scraper = setup_base_scraper_mocks["scraper"]
        assert scraper.base_url is None

    def test_base_url_stored_when_provided(self, setup_base_scraper_mocks):
        """A scraper constructed with base_url stores it verbatim."""
        mocks = setup_base_scraper_mocks
        scraper = BaseScraper(
            playwright_manager=mocks["playwright_manager_mock"],
            market_extractor=mocks["market_extractor_mock"],
            scroller=AsyncMock(),
            cookie_dismisser=AsyncMock(),
            selection_manager=mocks["selection_manager_mock"],
            base_url="https://www.centroquote.it",
        )
        assert scraper.base_url == "https://www.centroquote.it"

    @pytest.mark.asyncio
    async def test_extract_match_links_default_uses_oddsportal_base(self, setup_base_scraper_mocks):
        """With no base_url, extract_match_links prefixes with the canonical OddsPortal domain."""
        mocks = setup_base_scraper_mocks
        scraper = mocks["scraper"]
        page_mock = mocks["page_mock"]
        page_mock.content = AsyncMock(return_value=_SERIE_A_HTML)

        result = await scraper.extract_match_links(page=page_mock)

        assert result == [f"{ODDSPORTAL_BASE_URL}{_SERIE_A_HREF}"]

    @pytest.mark.asyncio
    async def test_extract_match_links_regional_base_url_applied(self, setup_base_scraper_mocks):
        """With base_url set, extract_match_links prefixes with the regional domain instead."""
        mocks = setup_base_scraper_mocks
        regional_scraper = BaseScraper(
            playwright_manager=mocks["playwright_manager_mock"],
            market_extractor=mocks["market_extractor_mock"],
            scroller=AsyncMock(),
            cookie_dismisser=AsyncMock(),
            selection_manager=mocks["selection_manager_mock"],
            base_url="https://www.centroquote.it",
        )
        page_mock = mocks["page_mock"]
        page_mock.content = AsyncMock(return_value=_SERIE_A_HTML)

        result = await regional_scraper.extract_match_links(page=page_mock)

        assert result == [f"https://www.centroquote.it{_SERIE_A_HREF}"]


# -- OddsPortalScraper URL wiring --------------------------------------------


def _build_odds_portal_scraper(setup_base_scraper_mocks, base_url=None):
    """Construct an OddsPortalScraper with the same mocked collaborators used in
    the setup_base_scraper_mocks fixture. Mirrors the pattern used in
    TestBaseScraperBaseUrl.test_base_url_stored_when_provided.

    playwright_manager_mock.page is set explicitly because PlaywrightManager.page is
    an instance attribute (not a class-level method), so MagicMock(spec=...) doesn't
    include it automatically. Setting it to page_mock makes the truthy guard in
    scrape_historic / scrape_upcoming pass before the URLBuilder call fires.
    """
    mocks = setup_base_scraper_mocks
    mocks["playwright_manager_mock"].page = mocks["page_mock"]
    return OddsPortalScraper(
        playwright_manager=mocks["playwright_manager_mock"],
        market_extractor=mocks["market_extractor_mock"],
        scroller=AsyncMock(),
        cookie_dismisser=AsyncMock(),
        selection_manager=mocks["selection_manager_mock"],
        base_url=base_url,
    )


class TestOddsPortalScraperUrlWiring:
    @pytest.mark.asyncio
    async def test_scrape_historic_forwards_base_url_to_url_builder(self, setup_base_scraper_mocks, monkeypatch):
        from oddsharvester.core import odds_portal_scraper as ops

        scraper = _build_odds_portal_scraper(setup_base_scraper_mocks, base_url="https://www.centroquote.it")

        captured = {}

        class _StopError(Exception):
            pass

        def fake_get_historic(*, sport, league, season=None, base_url=None):
            captured["base_url"] = base_url
            raise _StopError

        monkeypatch.setattr(ops.URLBuilder, "get_historic_matches_url", staticmethod(fake_get_historic))

        with pytest.raises(_StopError):
            await scraper.scrape_historic(
                sport="football", league="england-premier-league", season="current", markets=["1x2"]
            )
        assert captured["base_url"] == "https://www.centroquote.it"

    @pytest.mark.asyncio
    async def test_scrape_upcoming_forwards_base_url_to_url_builder(self, setup_base_scraper_mocks, monkeypatch):
        from oddsharvester.core import odds_portal_scraper as ops

        scraper = _build_odds_portal_scraper(setup_base_scraper_mocks, base_url="https://www.centroquote.it")

        captured = {}

        class _StopError(Exception):
            pass

        def fake_get_upcoming(*, sport, date, league=None, base_url=None):
            captured["base_url"] = base_url
            raise _StopError

        monkeypatch.setattr(ops.URLBuilder, "get_upcoming_matches_url", staticmethod(fake_get_upcoming))

        with pytest.raises(_StopError):
            await scraper.scrape_upcoming(sport="football", date="2025-01-15", markets=["1x2"])
        assert captured["base_url"] == "https://www.centroquote.it"

    @pytest.mark.asyncio
    async def test_scrape_historic_default_base_url_is_none(self, setup_base_scraper_mocks, monkeypatch):
        from oddsharvester.core import odds_portal_scraper as ops

        scraper = _build_odds_portal_scraper(setup_base_scraper_mocks)

        captured = {}

        class _StopError(Exception):
            pass

        def fake_get_historic(*, sport, league, season=None, base_url=None):
            captured["base_url"] = base_url
            raise _StopError

        monkeypatch.setattr(ops.URLBuilder, "get_historic_matches_url", staticmethod(fake_get_historic))

        with pytest.raises(_StopError):
            await scraper.scrape_historic(
                sport="football", league="england-premier-league", season="current", markets=["1x2"]
            )
        assert captured["base_url"] is None


# -- parse live info -------------------------------------------------------

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

    def test_parses_en_dash_score_separator(self):
        """OddsPortal renders some scores with an en-dash rather than a colon."""
        result = _parse_live_info(self._soup('<div data-testid="live-info"><div>HT</div><div>2\u20131</div></div>'))
        assert result == {
            "live_period": "HT",
            "live_score_home": 2,
            "live_score_away": 1,
            "live_score_raw": "2\u20131",
        }

    def test_parses_real_football_live_header(self):
        """Ground truth captured from a live football match on 2026-07-20 15:04.

        Football marks the period as elapsed minutes with an apostrophe, unlike
        tennis sets or baseball innings, and repeats the running score inside
        partial-result. Locked in so the shape-based parser cannot regress on it.
        """
        html = (
            '<div class="flex max-sm:gap-2" data-testid="live-info">'
            '<div class="flex flex-wrap gap-2"><p class="result-live"></p>'
            '<div class="text-red-dark">4\'</div>'
            '<div class="text-red-dark font-bold">1:0</div>'
            '<div class="flex" data-testid="partial-result">'
            '<span>(</span><div class="flex">1:0</div><span>)</span></div></div></div>'
        )
        assert _parse_live_info(self._soup(html)) == {
            "live_period": "4'",
            "live_score_home": 1,
            "live_score_away": 0,
            "live_score_raw": "1:0 (1:0)",
        }

    def test_returns_none_for_finished_match(self):
        """A finished match keeps its live-info container but shows a terminal marker.

        Verified live 2026-07-20: OddsPortal renders "Final result" (with a
        non-breaking space) instead of dropping the container, so absence is not
        the only end-of-match signal.
        """
        html = '<div data-testid="live-info"><div>Final\u00a0result</div><div>0:2</div></div>'
        assert _parse_live_info(self._soup(html)) is None

    def test_returns_none_for_finished_match_single_chunk(self):
        """2026-08 redesign: the persistent live-info can serve the whole terminal
        text as one chunk ("Final result 1:2 (0:1, 1:1)")."""
        html = '<div data-testid="live-info">Final result 1:2 (0:1, 1:1)</div>'
        assert _parse_live_info(self._soup(html)) is None

    def test_normalizes_non_breaking_space_in_period(self):
        html = '<div data-testid="live-info"><div>1st\u00a0Set</div><div>0:0</div></div>'
        assert _parse_live_info(self._soup(html))["live_period"] == "1st Set"

    def test_missing_score_yields_none_ints_and_keeps_period(self):
        result = _parse_live_info(self._soup('<div data-testid="live-info"><div>HT</div></div>'))
        assert result == {
            "live_period": "HT",
            "live_score_home": None,
            "live_score_away": None,
            "live_score_raw": None,
        }


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
    """Live-now rows yield absolute in-play links plus their period marker."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=LIVE_NOW_LISTING_HTML)

    rows = await scraper.extract_live_match_links(page=page_mock)

    assert [r["match_link"] for r in rows] == [
        "https://www.oddsportal.com/tennis/h2h/janvier-maxime-S4riPNES/kuzmanov-dimitar-WEwUtEGs/inplay-odds/#t0bmQMVh",
        "https://www.oddsportal.com/football/england/premier-league/arsenal-chelsea-xYz12345/inplay-odds/#aB3dE6fG",
    ]
    assert rows[0]["live_period"] == "1S"
    assert rows[1]["live_period"] == "65'"


@pytest.mark.asyncio
async def test_extract_live_match_links_skips_offscreen_twin(setup_base_scraper_mocks):
    """The CSS-hidden duplicate row is dropped, not returned as a third match."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=LIVE_NOW_LISTING_HTML)

    rows = await scraper.extract_live_match_links(page=page_mock)

    assert len(rows) == 2
    assert not any("hidden-twin-corrupt" in r["match_link"] for r in rows)


@pytest.mark.asyncio
async def test_extract_live_match_links_league_filter(setup_base_scraper_mocks):
    """A league slug keeps only rows whose href sits under that league path."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=LIVE_NOW_LISTING_HTML)

    rows = await scraper.extract_live_match_links(page=page_mock, sport="football", league="england-premier-league")

    assert len(rows) == 1
    assert "arsenal-chelsea" in rows[0]["match_link"]


@pytest.mark.asyncio
async def test_extract_live_match_links_empty_listing(setup_base_scraper_mocks):
    """No live matches is a normal outcome, not an error."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value="<html><body></body></html>")

    assert await scraper.extract_live_match_links(page=page_mock) == []


@pytest.mark.asyncio
async def test_extract_live_match_links_ignores_non_inplay_anchors(setup_base_scraper_mocks):
    """Rows whose only anchor is a league link (not a match) are skipped."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
        <div data-testid="game-row">
          <a href="/football/england/premier-league/">Premier League</a>
        </div>
        </body></html>
        """
    )

    assert await scraper.extract_live_match_links(page=page_mock) == []


@pytest.mark.asyncio
async def test_scrape_match_data_live_mode_adds_live_fields(setup_base_scraper_mocks):
    """Live mode enriches the match record with score, period and a scrape timestamp."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=f"<html><body>{LIVE_INFO_TENNIS_HTML}</body></html>")
    scraper._hydrate_match_view = AsyncMock()
    scraper._dismiss_login_modal = AsyncMock()
    scraper._extract_match_details = AsyncMock(return_value={"home_team": "A"})

    data = await scraper._scrape_match_data(
        page=page_mock, sport="tennis", match_link="https://x/inplay-odds/#a", live_mode=True
    )

    assert data["live_period"] == "2nd Set"
    assert data["live_score_home"] == 1
    assert data["live_score_away"] == 0
    assert data["live_score_raw"] == "1:0 (6:4, 0:0)"
    assert data["scraped_at_utc"].endswith("Z")


@pytest.mark.asyncio
async def test_scrape_match_data_live_mode_flags_ended_match(setup_base_scraper_mocks):
    """A page without a live-info header means the match ended; flag it for the caller to drop."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value="<html><body><div>FT 2:1</div></body></html>")
    scraper._hydrate_match_view = AsyncMock()
    scraper._dismiss_login_modal = AsyncMock()
    scraper._extract_match_details = AsyncMock(return_value={"home_team": "A"})

    data = await scraper._scrape_match_data(
        page=page_mock, sport="football", match_link="https://x/inplay-odds/#a", live_mode=True
    )

    assert data == {"_live_ended": True, "match_link": "https://x/inplay-odds/#a"}


@pytest.mark.asyncio
async def test_scrape_match_data_without_live_mode_adds_no_live_fields(setup_base_scraper_mocks):
    """Default (non-live) scraping is untouched by the live-mode branch."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value=f"<html><body>{LIVE_INFO_TENNIS_HTML}</body></html>")
    scraper._hydrate_match_view = AsyncMock()
    scraper._dismiss_login_modal = AsyncMock()
    scraper._extract_match_details = AsyncMock(return_value={"home_team": "A"})

    data = await scraper._scrape_match_data(page=page_mock, sport="tennis", match_link="https://x/")

    assert data == {"home_team": "A"}


@pytest.mark.asyncio
async def test_extract_match_odds_retries_h2h_fragment_failure(setup_base_scraper_mocks):
    """Issue #83: a resync timeout must be retried in-run, and a second attempt
    that succeeds must land in result.success rather than in the failed list."""
    from oddsharvester.core.exceptions import H2HFragmentResolutionError
    from oddsharvester.core.retry import RetryConfig

    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]

    scraper._hydrate_match_view = AsyncMock()
    scraper._dismiss_login_modal = AsyncMock()
    scraper._extract_match_details = AsyncMock(
        side_effect=[
            H2HFragmentResolutionError("page never updated eventData.id to match the fragment"),
            {"match_link": "https://www.oddsportal.com/football/h2h/a/b/#WbDmMwm1", "home_team": "A"},
        ]
    )

    result = await scraper.extract_match_odds(
        sport="football",
        match_links=["https://www.oddsportal.com/football/h2h/a/b/#WbDmMwm1"],
        retry_config=RetryConfig(max_attempts=2, base_delay=0, max_delay=0),
        request_delay=0,
    )

    assert result.stats.successful == 1
    assert result.stats.failed == 0
    assert scraper._extract_match_details.await_count == 2


@pytest.mark.asyncio
async def test_extract_match_odds_h2h_failure_is_reported_retryable(setup_base_scraper_mocks):
    """When every attempt times out, the URL is reported retryable and typed
    HEADER_NOT_FOUND, and the proxy is not blamed for a client-side render race."""
    from oddsharvester.core.exceptions import H2HFragmentResolutionError
    from oddsharvester.core.retry import RetryConfig
    from oddsharvester.core.scrape_result import ErrorType

    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]

    scraper._hydrate_match_view = AsyncMock()
    scraper._dismiss_login_modal = AsyncMock()
    scraper._extract_match_details = AsyncMock(
        side_effect=H2HFragmentResolutionError("page never updated eventData.id to match the fragment")
    )

    result = await scraper.extract_match_odds(
        sport="football",
        match_links=["https://www.oddsportal.com/football/h2h/a/b/#WbDmMwm1"],
        retry_config=RetryConfig(max_attempts=2, base_delay=0, max_delay=0),
        request_delay=0,
    )

    assert result.stats.failed == 1
    failed = result.failed[0]
    assert failed.attempts == 2
    assert failed.is_retryable is True
    assert failed.error_type is ErrorType.HEADER_NOT_FOUND
    assert result.get_retryable_urls() == ["https://www.oddsportal.com/football/h2h/a/b/#WbDmMwm1"]

    mocks["playwright_manager_mock"].report_page_result.assert_called_once_with("direct", is_proxy_failure=False)


# -- match details + hydration on the redesigned DOM (issue #85) --------------


def _make_hydrated_match_html(
    date_p: str = "24 May 2026,",
    time_p: str = "17:00",
    score_text: str = "Final result 1:2 (0:1, 1:1)",
    league: str = "Premier League 2025/2026",
    ld_json: str | None = None,
) -> str:
    """Match page as rendered after SPA hydration (verified live 2026-08-24)."""
    ld_block = f'<script type="application/ld+json">{ld_json}</script>' if ld_json else ""
    return f"""
    <html><head>{ld_block}</head><body>
      <div data-testid="breadcrumbs-line">
        <a>&lt;{league}</a>
        <a data-testid="Home">Home</a>
        <a data-testid="Football">Football</a>
        <a data-testid="England">England</a>
        <a data-testid="{league}">{league}</a>
        <span data-testid="breadcrumb-current-page">Crystal Palace - Arsenal</span>
      </div>
      <div data-testid="game-participants">
        <div data-testid="game-host"><p class="participant-name">Crystal Palace</p></div>
        <div data-testid="game-guest"><p class="participant-name">Arsenal</p></div>
      </div>
      <section>
        <div data-testid="game-time-item"><p>Sunday,</p><p>{date_p}</p><p>{time_p}</p></div>
        <div data-testid="live-info">{score_text}</div>
      </section>
    </body></html>
    """


_MATCHING_LD_JSON = (
    '{"@context":"https://schema.org","@type":["Event","SportsEvent"],"sport":"Football",'
    '"name":"Crystal Palace - Arsenal","startDate":"2026-05-24T18:00:00+01:00",'
    '"location":{"@type":"Place","name":"Selhurst Park",'
    '"address":{"addressLocality":"London","addressCountry":"England"}}}'
)

_STALE_LD_JSON = _MATCHING_LD_JSON.replace("2026-05-24T18:00:00+01:00", "2026-12-26T16:00:00+01:00")


@pytest.mark.asyncio
async def test_extract_match_details_from_hydrated_dom(setup_base_scraper_mocks):
    """Happy path: every field comes from the DOM; venue from the matching JSON-LD."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"

    page_mock.content = AsyncMock(return_value=_make_hydrated_match_html(ld_json=_MATCHING_LD_JSON, time_p="17:00"))

    result = await scraper._extract_match_details(
        page=page_mock,
        match_link="https://www.oddsportal.com/football/h2h/arsenal-hA1Zm19f/crystal-palace-AovF1Mia/#UNC9hLMj",
    )

    assert result["home_team"] == "Crystal Palace"
    assert result["away_team"] == "Arsenal"
    assert result["league_name"] == "Premier League"
    assert result["match_date"] == "2026-05-24 17:00:00 UTC"
    assert result["home_score"] == "1"
    assert result["away_score"] == "2"
    assert result["partial_results"] == "(0:1, 1:1)"
    assert result["venue"] == "Selhurst Park"
    assert result["venue_town"] == "London"
    assert result["venue_country"] == "England"
    assert result["match_info"] is None
    assert "scraped_date" in result


@pytest.mark.asyncio
async def test_extract_match_details_ignores_stale_ld_json_venue(setup_base_scraper_mocks):
    """The SSR JSON-LD describes the *next upcoming* meeting (gotchas 1b): a
    startDate that does not match the DOM date must not contribute venue data."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"

    page_mock.content = AsyncMock(return_value=_make_hydrated_match_html(ld_json=_STALE_LD_JSON))

    result = await scraper._extract_match_details(page=page_mock, match_link="https://example.test/m#id1")

    assert result is not None
    assert result["venue"] is None
    assert result["venue_town"] is None
    assert result["venue_country"] is None


@pytest.mark.asyncio
async def test_extract_match_details_returns_none_without_landmarks(setup_base_scraper_mocks):
    """A non-hydrated page (H2H landing skeleton) has neither teams nor kickoff."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="<html><body><h1>LASK - Celtic</h1><p>Select a match from the listings</p></body></html>"
    )

    result = await scraper._extract_match_details(page=page_mock, match_link="https://example.test/m#id1")
    assert result is None


@pytest.mark.asyncio
async def test_extract_match_details_declares_null_season(setup_base_scraper_mocks):
    """Every row carries a season column; commands with no season leave it null (issue #78)."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"
    page_mock.content = AsyncMock(return_value=_make_hydrated_match_html())

    result = await scraper._extract_match_details(page=page_mock, match_link="https://example.test/m#id1")

    assert result["season"] is None
    # Column position is part of the schema contract: the CSV header follows key order.
    keys = list(result.keys())
    assert keys.index("season") == keys.index("match_date") + 1
    assert keys.index("match_link") == keys.index("season") + 1


@pytest.mark.asyncio
async def test_local_kickoff_disabled_adds_no_keys(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"
    page_mock.content = AsyncMock(return_value=_make_hydrated_match_html(ld_json=_MATCHING_LD_JSON))

    result = await scraper._extract_match_details(page=page_mock, match_link="https://example.test/m#id1")

    assert "venue_timezone" not in result
    assert "match_date_venue_local" not in result


@pytest.mark.asyncio
async def test_local_kickoff_enabled_adds_local_fields(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    scraper.local_kickoff = True
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"
    page_mock.content = AsyncMock(return_value=_make_hydrated_match_html(ld_json=_MATCHING_LD_JSON))

    result = await scraper._extract_match_details(page=page_mock, match_link="https://example.test/m#id1")

    assert result["venue_timezone"] == "Europe/London"
    assert result["match_date_venue_local"] is not None


@pytest.mark.asyncio
async def test_local_kickoff_enabled_unresolved_venue_sets_none(setup_base_scraper_mocks):
    """Without a trustworthy JSON-LD venue, both local-kickoff fields stay None."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    scraper.local_kickoff = True
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"
    page_mock.content = AsyncMock(return_value=_make_hydrated_match_html(ld_json=_STALE_LD_JSON))

    result = await scraper._extract_match_details(page=page_mock, match_link="https://example.test/m#id1")

    assert result["venue_timezone"] is None
    assert result["match_date_venue_local"] is None


@pytest.mark.asyncio
async def test_extract_match_details_teams_via_participant_name_testid(setup_base_scraper_mocks):
    """Live pages carry the team name in a [data-testid='participant-name'] element
    that is not necessarily a <p>."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"
    html = (
        _make_hydrated_match_html()
        .replace(
            '<p class="participant-name">Crystal Palace</p>', '<div data-testid="participant-name">Crystal Palace</div>'
        )
        .replace('<p class="participant-name">Arsenal</p>', '<div data-testid="participant-name">Arsenal</div>')
    )
    page_mock.content = AsyncMock(return_value=html)

    result = await scraper._extract_match_details(page=page_mock, match_link="https://example.test/m#id1")

    assert result["home_team"] == "Crystal Palace"
    assert result["away_team"] == "Arsenal"


def test_extract_fragment_match_id_strips_market_suffix():
    # The hydrated SPA rewrites the fragment to '<id>:<market>;<scope>'.
    assert _extract_fragment_match_id("https://www.oddsportal.com/x/h2h/a/b/#OOklm0j3:1X2;2") == "OOklm0j3"


@pytest.mark.asyncio
async def test_hydrate_match_view_success_first_attempt(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()

    await scraper._hydrate_match_view(
        page=page_mock, match_link="https://www.oddsportal.com/football/h2h/a/b/#UNC9hLMj", sport="football"
    )

    args, kwargs = page_mock.evaluate.await_args
    payload = args[1] if len(args) >= 2 else kwargs.get("arg")
    assert payload["fragment"] == "UNC9hLMj"
    assert payload["code"] == "1X2"
    assert payload["scope"] == 2
    page_mock.wait_for_selector.assert_awaited_once()


@pytest.mark.asyncio
async def test_hydrate_match_view_two_outcome_sport_uses_home_away(setup_base_scraper_mocks):
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()

    await scraper._hydrate_match_view(
        page=page_mock, match_link="https://www.oddsportal.com/tennis/h2h/a/b/#WbDmMwm1", sport="tennis"
    )

    args, kwargs = page_mock.evaluate.await_args
    payload = args[1] if len(args) >= 2 else kwargs.get("arg")
    assert payload["code"] == "home-away"


@pytest.mark.asyncio
async def test_hydrate_match_view_exhaustion_raises_retryable(setup_base_scraper_mocks):
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    from oddsharvester.core.exceptions import H2HFragmentResolutionError

    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.evaluate = AsyncMock()
    page_mock.query_selector = AsyncMock(return_value=None)
    page_mock.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))

    with pytest.raises(H2HFragmentResolutionError) as excinfo:
        await scraper._hydrate_match_view(
            page=page_mock, match_link="https://www.oddsportal.com/football/h2h/a/b/#UNC9hLMj", sport="football"
        )

    assert excinfo.value.is_retryable is True
    assert "hydration" in str(excinfo.value)
    assert page_mock.evaluate.await_count == 3


@pytest.mark.asyncio
async def test_hydrate_match_view_without_fragment_waits_directly(setup_base_scraper_mocks):
    """Legacy non-fragment match URLs skip the hash nudge entirely."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()

    await scraper._hydrate_match_view(
        page=page_mock, match_link="https://www.oddsportal.com/football/england/x-y/abcd1234/", sport="football"
    )

    page_mock.evaluate.assert_not_awaited()
    page_mock.wait_for_selector.assert_awaited_once()


# -- live (in-play) on the redesigned DOM (issue #85 follow-up) ---------------

_INPLAY_HEADER_HTML = """
<div data-testid="game-participants">
  <div class="my-3 flex w-full gap-2">
    <div data-testid="game-host"><a data-testid="participant-name" href="/tennis/team/x/">Kopp S.</a></div>
    <div class="shrink-0 text-right font-semibold text-red-dark">1</div>
  </div>
  <div class="relative inline-block"><span class="max-mm:!hidden text-red-dark">:</span></div>
  <div class="flex w-full gap-2">
    <div data-testid="game-guest"><a data-testid="participant-name" href="/tennis/team/y/">Ribeiro E.</a></div>
    <div class="shrink-0 text-right font-semibold text-red-dark">2</div>
  </div>
</div>
"""


class TestParseLiveInfoInplayRedesign:
    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def test_parses_red_score_digits_from_game_participants(self):
        """In-play pages carry no live-info element; the live score is the red
        digits flanking the participant names (verified live 2026-08-24)."""
        result = _parse_live_info(self._soup(f"<html><body>{_INPLAY_HEADER_HTML}</body></html>"))
        assert result == {
            "live_period": None,
            "live_score_home": 1,
            "live_score_away": 2,
            "live_score_raw": "1:2",
        }

    def test_header_without_red_digits_means_not_live(self):
        html = """
        <html><body><div data-testid="game-participants">
          <div data-testid="game-host"><a data-testid="participant-name">LASK</a></div>
          <div data-testid="game-guest"><a data-testid="participant-name">Celtic</a></div>
        </div></body></html>
        """
        assert _parse_live_info(self._soup(html)) is None

    def test_live_info_element_still_wins_when_present(self):
        """Legacy live-info containers (older captures) keep working unchanged."""
        html = '<div data-testid="live-info"><div>HT</div><div>2:1</div></div>'
        result = _parse_live_info(self._soup(html))
        assert result["live_score_home"] == 2
        assert result["live_period"] == "HT"

    def test_finished_match_standard_page_still_none(self):
        html = f"""
        <html><body>
          <div data-testid="live-info">Final result 1:2 (0:1, 1:1)</div>
          {_INPLAY_HEADER_HTML}
        </body></html>
        """
        assert _parse_live_info(self._soup(html)) is None


@pytest.mark.asyncio
async def test_hydrate_match_view_inplay_waits_without_market_nudge(setup_base_scraper_mocks):
    """/inplay-odds/ pages hydrate on their own and route their own market codes;
    forcing '#id:1X2;2' can flip the view to Pre-match Odds. Wait first."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()

    await scraper._hydrate_match_view(
        page=page_mock,
        match_link="https://www.oddsportal.com/tennis/h2h/a/b/inplay-odds/#niGX35MH",
        sport="tennis",
    )

    page_mock.evaluate.assert_not_awaited()
    page_mock.wait_for_selector.assert_awaited_once()


@pytest.mark.asyncio
async def test_hydrate_match_view_inplay_nudges_bare_id_on_timeout(setup_base_scraper_mocks):
    from playwright.async_api import TimeoutError as PlaywrightTimeoutError

    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.evaluate = AsyncMock()
    page_mock.query_selector = AsyncMock(return_value=None)
    page_mock.wait_for_selector = AsyncMock(side_effect=[PlaywrightTimeoutError("t"), None])

    await scraper._hydrate_match_view(
        page=page_mock,
        match_link="https://www.oddsportal.com/tennis/h2h/a/b/inplay-odds/#niGX35MH",
        sport="tennis",
    )

    args, kwargs = page_mock.evaluate.await_args
    payload = args[1] if len(args) >= 2 else kwargs.get("arg")
    assert payload["fragment"] == "niGX35MH"
    assert payload.get("bare") is True
