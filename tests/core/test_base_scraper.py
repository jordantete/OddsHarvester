import pytest, json, asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import Page, TimeoutError
from src.core.base_scraper import BaseScraper
from src.core.playwright_manager import PlaywrightManager
from src.core.browser_helper import BrowserHelper
from src.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from src.utils.constants import ODDSPORTAL_BASE_URL

@pytest.fixture
def setup_base_scraper_mocks():
    """Setup common mocks for BaseScraper tests."""
    # Create mocks for dependencies
    playwright_manager_mock = MagicMock(spec=PlaywrightManager)
    browser_helper_mock = MagicMock(spec=BrowserHelper)
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
    
    # Create scraper instance with mocks
    scraper = BaseScraper(
        playwright_manager=playwright_manager_mock,
        browser_helper=browser_helper_mock,
        market_extractor=market_extractor_mock
    )
    
    return {
        "scraper": scraper,
        "playwright_manager_mock": playwright_manager_mock,
        "browser_helper_mock": browser_helper_mock,
        "market_extractor_mock": market_extractor_mock,
        "page_mock": page_mock,
        "context_mock": context_mock
    }

@pytest.mark.asyncio
async def test_set_odds_format(setup_base_scraper_mocks):
    """Test setting odds format on the page."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    
    # Mock the dropdown button
    dropdown_button_mock = AsyncMock()
    dropdown_button_mock.inner_text = AsyncMock(return_value="Decimal")
    page_mock.query_selector.return_value = dropdown_button_mock
    
    # Test when odds format is already set
    await scraper.set_odds_format(page=page_mock, odds_format="Decimal")
    
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
    format_option1.inner_text = AsyncMock(return_value="Decimal")
    format_option2 = AsyncMock()
    format_option2.inner_text = AsyncMock(return_value="Fractional")
    
    page_mock.query_selector_all.return_value = [format_option1, format_option2]
    
    # Test selecting a different format
    await scraper.set_odds_format(page=page_mock, odds_format="Decimal")
    
    dropdown_button_mock.click.assert_called_once()
    page_mock.query_selector_all.assert_called_once()
    format_option1.inner_text.assert_called_once()
    format_option1.click.assert_called_once()

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
@patch("src.core.base_scraper.BeautifulSoup")
@patch("src.core.base_scraper.re")
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
    link3 = {"href": "/"} # Should be filtered out
    
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
        f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/liverpool-man-utd/efgh5678"
    ]
    assert sorted(result) == sorted(expected_links)

@pytest.mark.asyncio
@patch("src.core.base_scraper.BeautifulSoup")
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

@pytest.mark.asyncio
async def test_extract_match_odds(setup_base_scraper_mocks):
    """Test extracting odds for multiple match links concurrently."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    context_mock = mocks["context_mock"]
    page_mock = mocks["page_mock"]
    
    # Mock _scrape_match_data to return data directly
    scraper._scrape_match_data = AsyncMock(side_effect=[
        {"match": "data1"},
        {"match": "data2"}
    ])
    
    # Call the method under test
    match_links = [
        "https://oddsportal.com/match1",
        "https://oddsportal.com/match2"
    ]
    
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
    with patch('asyncio.gather', side_effect=mock_gather):
        result = await scraper.extract_match_odds(
            sport="football",
            match_links=match_links,
            markets=["1x2"],
            scrape_odds_history=False
        )
    
    # Verify new_page was called for each match link
    assert context_mock.new_page.call_count == 2
    
    # Verify the result
    assert len(result) == 2
    assert {"match": "data1"} in result
    assert {"match": "data2"} in result

@pytest.mark.asyncio
async def test_scrape_match_data(setup_base_scraper_mocks):
    """Test scraping data for a specific match."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    
    # Mock _extract_match_details_event_header
    scraper._extract_match_details_event_header = AsyncMock(
        return_value={
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "match_date": "2023-05-01 20:00:00 UTC"
        }
    )
    
    # Mock market_extractor.scrape_markets
    mocks["market_extractor_mock"].scrape_markets = AsyncMock(
        return_value={
            "1x2": {
                "odds": [2.0, 3.5, 4.0],
                "bookmakers": ["bet365", "bwin", "unibet"]
            },
            "over_under_2_5": {
                "odds": [1.8, 2.1],
                "bookmakers": ["bet365", "bwin"]
            }
        }
    )
    
    # Call the method under test
    result = await scraper._scrape_match_data(
        page=page_mock,
        sport="football",
        match_link="https://oddsportal.com/football/england/arsenal-chelsea/123456",
        markets=["1x2", "over_under_2_5"],
        scrape_odds_history=True,
        target_bookmaker="bet365"
    )
    
    # Verify interactions
    page_mock.goto.assert_called_once_with(
        "https://oddsportal.com/football/england/arsenal-chelsea/123456",
        timeout=5000,
        wait_until="domcontentloaded"
    )
    
    scraper._extract_match_details_event_header.assert_called_once_with(page_mock)
    
    mocks["market_extractor_mock"].scrape_markets.assert_called_once_with(
        page=page_mock,
        sport="football",
        markets=["1x2", "over_under_2_5"],
        period="FullTime",
        scrape_odds_history=True,
        target_bookmaker="bet365"
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
    
    # Call the method under test
    result = await scraper._scrape_match_data(
        page=page_mock,
        sport="football",
        match_link="https://oddsportal.com/football/england/arsenal-chelsea/123456",
        markets=["1x2"]
    )
    
    # Verify result is None when no match details are found
    assert result is None
    # Verify market_extractor.scrape_markets was not called
    mocks["market_extractor_mock"].scrape_markets.assert_not_called()

@pytest.mark.asyncio
@patch("src.core.base_scraper.BeautifulSoup")
@patch("src.core.base_scraper.json")
async def test_extract_match_details_event_header(json_mock, bs4_mock, setup_base_scraper_mocks):
    """Test extracting match details from the react event header."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    
    # Mock BeautifulSoup and its find method
    soup_mock = MagicMock()
    bs4_mock.return_value = soup_mock
    
    # Mock the div with event header data
    event_header_div = MagicMock()
    event_header_div.__getitem__.return_value = '{"eventBody": {"startDate": 1681753200, "homeResult": 2, "awayResult": 1, "partialresult": "1-0", "venue": "Emirates Stadium", "venueTown": "London", "venueCountry": "England"}, "eventData": {"home": "Arsenal", "away": "Chelsea", "tournamentName": "Premier League"}}'
    soup_mock.find.return_value = event_header_div
    
    # Mock JSON parsing
    parsed_data = {
        "eventBody": {
            "startDate": 1681753200,
            "homeResult": 2,
            "awayResult": 1,
            "partialresult": "1-0",
            "venue": "Emirates Stadium",
            "venueTown": "London",
            "venueCountry": "England"
        },
        "eventData": {
            "home": "Arsenal",
            "away": "Chelsea",
            "tournamentName": "Premier League"
        }
    }
    json_mock.loads.return_value = parsed_data
    
    # Call the method under test
    result = await scraper._extract_match_details_event_header(page=page_mock)
    
    # Verify interactions
    page_mock.content.assert_called_once()
    bs4_mock.assert_called_once_with(page_mock.content.return_value, 'html.parser')
    soup_mock.find.assert_called_once_with('div', id='react-event-header')
    json_mock.loads.assert_called_once()
    
    # Verify the result has expected fields
    assert result["home_team"] == "Arsenal"
    assert result["away_team"] == "Chelsea"
    assert result["league_name"] == "Premier League"
    assert result["home_score"] == 2
    assert result["away_score"] == 1
    assert result["partial_results"] == "1-0"
    assert result["venue"] == "Emirates Stadium"
    assert result["venue_town"] == "London"
    assert result["venue_country"] == "England"
    assert "match_date" in result
    assert "scraped_date" in result

@pytest.mark.asyncio
@patch("src.core.base_scraper.BeautifulSoup")
async def test_extract_match_details_missing_div(bs4_mock, setup_base_scraper_mocks):
    """Test extracting match details when the header div is missing."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    
    # Mock BeautifulSoup and its find method returning None
    soup_mock = MagicMock()
    bs4_mock.return_value = soup_mock
    soup_mock.find.return_value = None
    
    # Call the method under test
    result = await scraper._extract_match_details_event_header(page=page_mock)
    
    # Verify result is None when the div is missing
    assert result is None

@pytest.mark.asyncio
@patch("src.core.base_scraper.BeautifulSoup")
@patch("src.core.base_scraper.json")
async def test_extract_match_details_invalid_json(json_mock, bs4_mock, setup_base_scraper_mocks):
    """Test extracting match details with invalid JSON data."""
    mocks = setup_base_scraper_mocks
    scraper = mocks["scraper"]
    page_mock = mocks["page_mock"]
    
    # Mock BeautifulSoup and its find method
    soup_mock = MagicMock()
    bs4_mock.return_value = soup_mock
    
    # Mock the div with invalid data
    event_header_div = MagicMock()
    event_header_div.__getitem__.return_value = "invalid JSON"
    soup_mock.find.return_value = event_header_div
    
    # Mock JSON parsing error
    json_mock.loads.side_effect = json.JSONDecodeError("Invalid JSON", "invalid JSON", 0)
    
    # Call the method under test
    result = await scraper._extract_match_details_event_header(page=page_mock)
    
    # Verify result is None when JSON is invalid
    assert result is None 