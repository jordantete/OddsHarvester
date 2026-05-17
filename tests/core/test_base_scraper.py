from datetime import date, datetime, timedelta
import json as _json
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError
import pytest

from oddsharvester.core.base_scraper import (
    BaseScraper,
    _extract_fragment_match_id,
    _is_offscreen_row,
    _parse_date_header,
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
@patch("oddsharvester.core.base_scraper.BeautifulSoup")
@patch("oddsharvester.core.base_scraper.re")
async def test_extract_match_links(re_mock, bs4_mock, setup_base_scraper_mocks):
    """Test extracting match links from a page."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock BeautifulSoup and its methods
    soup_mock = MagicMock()
    bs4_mock.return_value = soup_mock

    # Mock regex compile
    pattern_mock = MagicMock()
    re_mock.compile.return_value = pattern_mock

    # Mock finding event rows and links
    event_row1 = MagicMock()
    event_row2 = MagicMock()

    link1 = {"href": "/football/england/premier-league/arsenal-chelsea/abcd1234"}
    link2 = {"href": "/football/england/premier-league/liverpool-man-utd/efgh5678"}
    link3 = {"href": "/"}  # Should be filtered out

    event_row1.find_all.return_value = [link1, link3]
    event_row2.find_all.return_value = [link2]

    soup_mock.find_all.return_value = [event_row1, event_row2]

    # Call the method under test
    result = await scraper.extract_match_links(page=page_mock)

    # Verify interactions
    page_mock.content.assert_called_once()
    bs4_mock.assert_called_once()
    re_mock.compile.assert_called_once_with("^eventRow")
    soup_mock.find_all.assert_called_once_with(class_=pattern_mock)

    # Verify results
    expected_links = [
        f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/arsenal-chelsea/abcd1234",
        f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/liverpool-man-utd/efgh5678",
    ]
    assert sorted(result) == sorted(expected_links)


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
      <div class="eventRow">
        <div data-testid="date-header">Today, 14 Apr</div>
        <a href="/football/england/premier-league/match-one/aaaaaaa1">Match 1</a>
      </div>
      <div class="eventRow">
        <a href="/football/england/premier-league/match-two/aaaaaaa2">Match 2</a>
      </div>
      <div class="eventRow">
        <div data-testid="date-header">18 Apr 2026</div>
        <a href="/football/england/premier-league/match-three/aaaaaaa3">Match 3</a>
      </div>
      <div class="eventRow">
        <a href="/football/england/premier-league/match-four/aaaaaaa4">Match 4</a>
      </div>
      <div class="eventRow">
        <div data-testid="date-header">19 Apr 2026</div>
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
          <div class="eventRow">
            <div data-testid="date-header">Some gibberish</div>
            <a href="/football/england/premier-league/match-x/xxxxxxx1">Match X</a>
          </div>
          <div class="eventRow">
            <div data-testid="date-header">18 Apr 2026</div>
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
async def test_extract_match_links_deduplicates_preserving_order(setup_base_scraper_mocks):
    """Duplicate links across rows should be deduplicated while preserving order."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value="""
        <html><body>
          <div class="eventRow">
            <a href="/football/england/premier-league/match-one/aaaaaaa1">L1</a>
            <a href="/football/england/premier-league/match-one/aaaaaaa1">L1 dup</a>
          </div>
          <div class="eventRow">
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
          <div class="eventRow">
            <div data-testid="date-header">Today, 14 Apr</div>
            <a href="/football/england/premier-league/tokyo-match/tttttttt">Tokyo match</a>
          </div>
        </body></html>
        """
    )

    result = await scraper.extract_match_links(page=page_mock, date_filter=tokyo_today)
    assert len(result) == 1


# -- _is_offscreen_row + offscreen filtering (regression: issue #61) ---------


class TestIsOffscreenRow:
    """Unit tests for the _is_offscreen_row helper."""

    def test_no_style_attr_is_visible(self):
        row = BeautifulSoup('<div class="eventRow"></div>', "lxml").div
        assert _is_offscreen_row(row) is False

    def test_empty_style_is_visible(self):
        row = BeautifulSoup('<div class="eventRow" style=""></div>', "lxml").div
        assert _is_offscreen_row(row) is False

    def test_left_minus_9999_marks_offscreen(self):
        row = BeautifulSoup(
            '<div class="eventRow" style="position: absolute; left: -9999px;"></div>',
            "lxml",
        ).div
        assert _is_offscreen_row(row) is True

    def test_top_minus_9999_marks_offscreen(self):
        row = BeautifulSoup('<div class="eventRow" style="top:-9999px"></div>', "lxml").div
        assert _is_offscreen_row(row) is True

    def test_display_none_marks_offscreen(self):
        row = BeautifulSoup('<div class="eventRow" style="display: none;"></div>', "lxml").div
        assert _is_offscreen_row(row) is True

    def test_visibility_hidden_marks_offscreen(self):
        row = BeautifulSoup('<div class="eventRow" style="visibility:hidden"></div>', "lxml").div
        assert _is_offscreen_row(row) is True

    def test_uppercase_style_normalized(self):
        row = BeautifulSoup('<div class="eventRow" style="DISPLAY: NONE"></div>', "lxml").div
        assert _is_offscreen_row(row) is True

    def test_unrelated_style_is_visible(self):
        row = BeautifulSoup(
            '<div class="eventRow" style="color: red; padding-left: 9999px;"></div>',
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
          <div class="eventRow" id="4CyOBFbK" set="92939"
               style="position: absolute; left: -9999px; height: 0px; overflow: hidden;">
            <a href="/football/h2h/galatasaray-0j2eUlMC/kasimpasa-EXCPojim/#Aonqhgqt">phantom</a>
          </div>
          <div class="eventRow" id="4CyOBFbK" set="92939">
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
          <div class="eventRow">
            <div data-testid="date-header">17 May 2026</div>
            <a href="/football/h2h/real-aaa/match-bbb/#x1">real</a>
          </div>
          <div class="eventRow" style="position:absolute;left:-9999px;">
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
          <div class="eventRow" style="display:none;">
            <div data-testid="date-header">17 May 2026</div>
            <a href="/football/h2h/phantom-ccc/match-ddd/#x2">phantom</a>
          </div>
          <div class="eventRow">
            <div data-testid="date-header">17 May 2026</div>
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
    context_mock = mocks["context_mock"]

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

    # Verify new_page was called for each match link
    assert context_mock.new_page.call_count == 2

    # Verify the result is a ScrapeResult with successful matches
    assert len(result.success) == 2
    assert {"match": "data1"} in result.success
    assert {"match": "data2"} in result.success
    assert result.stats.total_urls == 2
    assert result.stats.successful == 2
    assert result.stats.failed == 0


@pytest.mark.asyncio
async def test_scrape_match_data(setup_base_scraper_mocks):
    """Test scraping data for a specific match."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # Mock _extract_match_details_event_header
    scraper._extract_match_details_event_header = AsyncMock(
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

    scraper._extract_match_details_event_header.assert_called_once_with(
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

    # Mock _extract_match_details_event_header returning None
    scraper._extract_match_details_event_header = AsyncMock(return_value=None)

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
async def test_extract_match_details_event_header(setup_base_scraper_mocks):
    """Happy path: minimal valid JSON + no DOM landmarks → JSON-only extraction."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    json_blob = (
        '{"eventBody": {"startDate": 1681753200, "homeResult": 2, "awayResult": 1, '
        '"partialresult": "1-0", "venue": "Emirates Stadium", "venueTown": "London", '
        '"venueCountry": "England"}, "eventData": {"home": "Arsenal", "away": "Chelsea", '
        '"tournamentName": "Premier League"}}'
    )
    page_mock.content = AsyncMock(
        return_value=f"<html><body><div id=\"react-event-header\" data='{json_blob}'></div></body></html>"
    )

    result = await scraper._extract_match_details_event_header(
        page=page_mock,
        match_link="https://www.oddsportal.com/football/england/arsenal-chelsea-123456",
    )

    assert result["match_link"] == "https://www.oddsportal.com/football/england/arsenal-chelsea-123456"
    assert result["home_team"] == "Arsenal"
    assert result["away_team"] == "Chelsea"
    assert result["league_name"] == "Premier League"
    assert result["home_score"] == "2"
    assert result["away_score"] == "1"
    assert result["partial_results"] == "1-0"
    assert result["venue"] == "Emirates Stadium"
    assert result["venue_town"] == "London"
    assert result["venue_country"] == "England"
    assert "match_date" in result
    assert "scraped_date" in result


@pytest.mark.asyncio
async def test_extract_match_details_missing_div(setup_base_scraper_mocks):
    """When the react-event-header div is absent, return None."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(return_value="<html><body></body></html>")

    result = await scraper._extract_match_details_event_header(
        page=page_mock, match_link="https://www.oddsportal.com/football/england/test-match"
    )
    assert result is None


@pytest.mark.asyncio
async def test_extract_match_details_invalid_json(setup_base_scraper_mocks):
    """When the data attribute isn't valid JSON, return None."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    page_mock.content = AsyncMock(
        return_value='<html><body><div id="react-event-header" data="not-json{"></div></body></html>'
    )

    result = await scraper._extract_match_details_event_header(
        page=page_mock, match_link="https://www.oddsportal.com/football/england/test-match"
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
    import logging

    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    mocks["playwright_manager_mock"].timezone_id = "Not/A/Real/Zone"
    with caplog.at_level(logging.WARNING):
        result = scraper._resolved_browser_timezone()
    assert result == ZoneInfo("UTC")
    assert any("Not/A/Real/Zone" in rec.message for rec in caplog.records)


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
    import logging

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
        f'<a data-testid="3">{text}</a>'
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


@pytest.mark.asyncio
async def test_extract_match_details_dom_first_overrides_wrong_json(setup_base_scraper_mocks):
    """
    Regression for PR #54: when the JSON eventBody contains wrong values
    but the DOM has the correct ones, DOM wins for the 5 affected fields
    while JSON still provides venue trio.
    """
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"

    # Wrong JSON values (simulating the PR #54 bug for Barcelona-Leganes)
    wrong_json = (
        '{"eventBody": {"startDate": 1745000000, "homeResult": 0, "awayResult": 1, '
        '"partialresult": "0:0, 0:1", "venue": "Camp Nou", "venueTown": "Barcelona", '
        '"venueCountry": "Spain"}, "eventData": {"home": "Leganes", "away": "Barcelona", '
        '"tournamentName": "LaLiga 2024/2025"}}'
    )

    page_mock.content = AsyncMock(
        return_value=f"""
        <html><body>
          <div id="react-event-header" data='{wrong_json}'></div>
          <section>
            <div data-testid="game-time-item"><p>Sun</p><p>17 Nov 2019,</p><p>20:00</p></div>
            <div data-testid="game-host"><p>Leganes</p></div>
            <div data-testid="game-guest"><p>Barcelona</p></div>
            <div data-testid="breadcrumbs-line">
              <a data-testid="3">LaLiga 2019/2020</a>
            </div>
            <div><div class="flex flex-wrap">Final result 2:0 (1:0, 1:0)</div></div>
          </section>
        </body></html>
        """
    )

    result = await scraper._extract_match_details_event_header(
        page=page_mock, match_link="https://example.test/barcelona-leganes"
    )

    # DOM-sourced fields override the (wrong) JSON
    assert result["match_date"] == "2019-11-17 20:00:00 UTC"
    assert result["home_team"] == "Leganes"
    assert result["away_team"] == "Barcelona"
    assert result["league_name"] == "LaLiga"
    assert result["home_score"] == "2"
    assert result["away_score"] == "0"
    assert result["partial_results"] == "(1:0, 1:0)"
    # Venue trio still from JSON
    assert result["venue"] == "Camp Nou"
    assert result["venue_town"] == "Barcelona"
    assert result["venue_country"] == "Spain"


@pytest.mark.asyncio
async def test_extract_match_details_falls_back_to_json_per_field(setup_base_scraper_mocks):
    """
    When DOM is partial (only teams + date present), other affected fields
    fall back to the JSON values individually.
    """
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"

    json_blob = (
        '{"eventBody": {"startDate": 1681753200, "homeResult": 9, "awayResult": 9, '
        '"partialresult": "json-partial", "venue": "Vaa", "venueTown": "Vt", '
        '"venueCountry": "Vc"}, "eventData": {"home": "JsonHome", "away": "JsonAway", '
        '"tournamentName": "JsonLeague"}}'
    )

    page_mock.content = AsyncMock(
        return_value=f"""
        <html><body>
          <div id="react-event-header" data='{json_blob}'></div>
          <div data-testid="game-time-item"><p>x</p><p>17 Apr 2023,</p><p>17:40</p></div>
          <div data-testid="game-host"><p>DomHome</p></div>
          <div data-testid="game-guest"><p>DomAway</p></div>
          <!-- No breadcrumb, no result block -->
        </body></html>
        """
    )

    result = await scraper._extract_match_details_event_header(page=page_mock, match_link="https://example.test/m")

    # DOM provided
    assert result["home_team"] == "DomHome"
    assert result["away_team"] == "DomAway"
    assert result["match_date"] == "2023-04-17 17:40:00 UTC"
    # JSON fallback for missing-from-DOM fields
    assert result["league_name"] == "JsonLeague"
    assert result["home_score"] == "9"
    assert result["away_score"] == "9"
    assert result["partial_results"] == "json-partial"


@pytest.mark.asyncio
async def test_extract_match_details_full_json_fallback_when_dom_absent(setup_base_scraper_mocks):
    """When no DOM landmarks are present, behavior matches the pre-fix JSON path."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    json_blob = (
        '{"eventBody": {"startDate": 1681753200, "homeResult": 2, "awayResult": 1, '
        '"partialresult": "1-0", "venue": "Emirates", "venueTown": "London", '
        '"venueCountry": "England"}, "eventData": {"home": "Arsenal", "away": "Chelsea", '
        '"tournamentName": "Premier League"}}'
    )

    page_mock.content = AsyncMock(
        return_value=f"<html><body><div id=\"react-event-header\" data='{json_blob}'></div></body></html>"
    )

    result = await scraper._extract_match_details_event_header(page=page_mock, match_link="https://example.test/m")

    assert result["home_team"] == "Arsenal"
    assert result["away_team"] == "Chelsea"
    assert result["league_name"] == "Premier League"
    assert result["home_score"] == "2"
    assert result["away_score"] == "1"
    assert result["partial_results"] == "1-0"
    assert result["match_date"] == "2023-04-17 17:40:00 UTC"
    assert result["venue"] == "Emirates"


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


def _make_react_event_header_html(event_id: str, start_date: int = 1681753200) -> str:
    payload = {
        "eventBody": {"startDate": start_date},
        "eventData": {
            "id": event_id,
            "home": "Royals",
            "away": "Mariners",
            "tournamentName": "MLB",
        },
    }
    return f"<html><body><div id=\"react-event-header\" data='{_json.dumps(payload)}'></div></body></html>"


@pytest.mark.asyncio
async def test_resolve_h2h_fragment_mismatch_success_returns_updated_payload(setup_base_scraper_mocks):
    """When wait_for_function succeeds, re-parsed soup + json reflect the requested match id."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_function = AsyncMock()
    page_mock.content = AsyncMock(return_value=_make_react_event_header_html("WbDmMwm1"))

    result = await scraper._resolve_h2h_fragment_mismatch(
        page=page_mock,
        fragment="WbDmMwm1",
    )

    assert result is not None
    _soup, json_data = result
    assert json_data["eventData"]["id"] == "WbDmMwm1"
    page_mock.evaluate.assert_awaited_once()
    page_mock.wait_for_function.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_h2h_fragment_mismatch_timeout_returns_none(setup_base_scraper_mocks, caplog):
    """When wait_for_function times out, the resolver returns None and logs ERROR."""
    import logging

    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_function = AsyncMock(side_effect=TimeoutError("timeout"))

    with caplog.at_level(logging.ERROR):
        result = await scraper._resolve_h2h_fragment_mismatch(
            page=page_mock,
            fragment="WbDmMwm1",
        )

    assert result is None
    assert any("H2H fragment resolution failed" in rec.message for rec in caplog.records)


@pytest.mark.asyncio
async def test_resolve_h2h_fragment_mismatch_passes_fragment_to_evaluate(setup_base_scraper_mocks):
    """The hashchange trigger must receive the fragment as the JS argument, not interpolated."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_function = AsyncMock()
    page_mock.content = AsyncMock(return_value=_make_react_event_header_html("abc"))

    await scraper._resolve_h2h_fragment_mismatch(page=page_mock, fragment="abc")

    args, kwargs = page_mock.evaluate.await_args
    # The fragment is the second positional arg to page.evaluate(expression, arg)
    # Accept either positional or keyword form, but the value must equal "abc"
    if len(args) >= 2:
        assert args[1] == "abc"
    else:
        assert kwargs.get("arg") == "abc"


@pytest.mark.asyncio
async def test_extract_match_details_h2h_fragment_match_skips_resync(setup_base_scraper_mocks):
    """When URL fragment equals eventData.id, no resync attempt is made."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    page_mock.content = AsyncMock(return_value=_make_react_event_header_html("WbDmMwm1"))
    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_function = AsyncMock()

    result = await scraper._extract_match_details_event_header(
        page=page_mock,
        match_link="https://www.oddsportal.com/baseball/h2h/a/b/#WbDmMwm1",
    )

    assert result is not None
    page_mock.evaluate.assert_not_awaited()
    page_mock.wait_for_function.assert_not_awaited()


@pytest.mark.asyncio
async def test_extract_match_details_h2h_fragment_mismatch_resolved(setup_base_scraper_mocks):
    """Initial SSR has wrong id; after resync, the corrected payload is used."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    # First content() call returns the wrong-match SSR (eventData.id = "WRONG_4t78m9X0",
    # startDate = 2026-05-22 23:40 UTC). After resync, the second call returns the
    # correct match (eventData.id = "WbDmMwm1", startDate = 2025-04-15 17:00 UTC).
    wrong_html = _make_react_event_header_html("WRONG_4t78m9X0", start_date=1779493200)
    correct_html = _make_react_event_header_html("WbDmMwm1", start_date=1744736400)
    page_mock.content = AsyncMock(side_effect=[wrong_html, correct_html])
    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_function = AsyncMock()

    result = await scraper._extract_match_details_event_header(
        page=page_mock,
        match_link="https://www.oddsportal.com/baseball/h2h/a/b/#WbDmMwm1",
    )

    assert result is not None
    # The wrong upcoming-match date must not leak through
    assert "2026-05-22" not in (result["match_date"] or "")
    # The corrected match's date should be present
    assert "2025-04-15" in (result["match_date"] or "")
    page_mock.evaluate.assert_awaited_once()
    page_mock.wait_for_function.assert_awaited_once()


@pytest.mark.asyncio
async def test_extract_match_details_h2h_fragment_resync_timeout_returns_none(setup_base_scraper_mocks):
    """When resync times out, the method returns None instead of emitting wrong data."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]

    page_mock.content = AsyncMock(return_value=_make_react_event_header_html("WRONG_4t78m9X0"))
    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_function = AsyncMock(side_effect=TimeoutError("timeout"))

    result = await scraper._extract_match_details_event_header(
        page=page_mock,
        match_link="https://www.oddsportal.com/baseball/h2h/a/b/#WbDmMwm1",
    )

    assert result is None


@pytest.mark.asyncio
async def test_extract_match_details_h2h_fragment_mismatch_dom_resolved_no_resync(setup_base_scraper_mocks):
    """Regression guard for PR #54 vs issue #60 conflict.

    When the URL fragment mismatches the SSR eventData.id BUT the DOM has
    already hydrated to the fragment-targeted historic match (DOM date differs
    from the stale JSON date), the scraper must take the PR #54 DOM-first path:
    NO hash-resync is attempted and the match is NOT dropped. Resyncing here is
    impossible (the embedded JSON id never updates to the fragment) so the
    issue #60 resync-or-drop logic must not regress these matches.
    """
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    mocks["playwright_manager_mock"].timezone_id = "UTC"

    # SSR JSON = stale recent match (id "STALE_recent7", 2025-04 startDate),
    # while the DOM is hydrated to the requested 2020 historic match.
    stale_json = (
        '{"eventBody": {"startDate": 1745000000, "homeResult": 0, "awayResult": 1, '
        '"partialresult": "0:0, 0:1", "venue": "Camp Nou", "venueTown": "Barcelona", '
        '"venueCountry": "Spain"}, "eventData": {"id": "STALE_recent7", '
        '"home": "Leganes", "away": "Barcelona", "tournamentName": "LaLiga 2024/2025"}}'
    )
    page_mock.content = AsyncMock(
        return_value=f"""
        <html><body>
          <div id="react-event-header" data='{stale_json}'></div>
          <section>
            <div data-testid="game-time-item"><p>Tue</p><p>16 Jun 2020,</p><p>20:00</p></div>
            <div data-testid="game-host"><p>Barcelona</p></div>
            <div data-testid="game-guest"><p>Leganes</p></div>
            <div data-testid="breadcrumbs-line"><a data-testid="3">LaLiga 2019/2020</a></div>
            <div><div class="flex flex-wrap">Final result 2:0 (1:0, 1:0)</div></div>
          </section>
        </body></html>
        """
    )
    page_mock.evaluate = AsyncMock()
    page_mock.wait_for_function = AsyncMock()

    result = await scraper._extract_match_details_event_header(
        page=page_mock,
        match_link="https://www.oddsportal.com/football/h2h/barcelona-x/leganes-y/#hYV97ShC",
    )

    # PR #54 path taken: match kept, DOM (2020) values win, no resync attempted.
    assert result is not None
    assert result["match_date"] == "2020-06-16 20:00:00 UTC"
    assert result["home_team"] == "Barcelona"
    assert result["away_team"] == "Leganes"
    assert result["home_score"] == "2"
    assert result["away_score"] == "0"
    page_mock.evaluate.assert_not_awaited()
    page_mock.wait_for_function.assert_not_awaited()


# -- base_url storage and match-link join -------------------------------------

_SERIE_A_HREF = "/football/italy/serie-a/match-xyz/"
_SERIE_A_HTML = f"""
<html><body>
  <div class="eventRow">
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
