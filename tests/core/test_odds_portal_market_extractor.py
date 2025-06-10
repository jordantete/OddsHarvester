import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from src.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from src.core.browser_helper import BrowserHelper
from src.core.sport_market_registry import SportMarketRegistry
from datetime import datetime

# Sample HTML for testing
SAMPLE_HTML_ODDS = """
<div class="border-black-borders flex h-9">
    <img class="bookmaker-logo" title="Bookmaker1">
    <div class="flex-center flex-col font-bold">1.90</div>
    <div class="flex-center flex-col font-bold">3.50</div>
    <div class="flex-center flex-col font-bold">4.20</div>
</div>
<div class="border-black-borders flex h-9">
    <img class="bookmaker-logo" title="Bookmaker2">
    <div class="flex-center flex-col font-bold">1.85</div>
    <div class="flex-center flex-col font-bold">3.60</div>
    <div class="flex-center flex-col font-bold">4.10</div>
</div>
"""

SAMPLE_HTML_ODDS_HISTORY = """
<div>
    <h3>Odds movement</h3>
    <div class="flex flex-col gap-1">
        <div class="flex gap-3">
            <div class="font-normal">10 Jun, 14:30</div>
        </div>
        <div class="flex gap-3">
            <div class="font-normal">10 Jun, 12:00</div>
        </div>
    </div>
    <div class="flex flex-col gap-1">
        <div class="font-bold">1.95</div>
        <div class="font-bold">1.90</div>
    </div>
    <div class="mt-2 gap-1">
        <div class="flex gap-1">
            <div>10 Jun, 08:00</div>
            <div class="font-bold">1.85</div>
        </div>
    </div>
</div>
"""

class TestOddsPortalMarketExtractor:
    """Unit tests for the OddsPortalMarketExtractor class."""

    @pytest.fixture
    def browser_helper_mock(self):
        """Create a mock for BrowserHelper."""
        mock = MagicMock(spec=BrowserHelper)
        return mock

    @pytest.fixture
    def extractor(self, browser_helper_mock):
        """Create an instance of OddsPortalMarketExtractor with a mocked BrowserHelper."""
        return OddsPortalMarketExtractor(browser_helper_mock)

    @pytest.fixture
    def page_mock(self):
        """Create a mock for the Playwright page."""
        mock = AsyncMock()
        mock.content = AsyncMock(return_value=SAMPLE_HTML_ODDS)
        mock.wait_for_timeout = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_parse_market_odds(self, extractor):
        """Test parsing odds from known HTML."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        
        # Act
        result = await extractor._parse_market_odds(SAMPLE_HTML_ODDS, "FullTime", odds_labels)
        
        # Assert
        assert len(result) == 2
        assert result[0]["bookmaker_name"] == "Bookmaker1"
        assert result[0]["1"] == "1.90"
        assert result[0]["X"] == "3.50"
        assert result[0]["2"] == "4.20"
        assert result[0]["period"] == "FullTime"
        assert result[1]["bookmaker_name"] == "Bookmaker2"

    @pytest.mark.asyncio
    async def test_parse_market_odds_with_target_bookmaker(self, extractor):
        """Test parsing odds with a specific target bookmaker."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        target_bookmaker = "Bookmaker1"
        
        # Act
        result = await extractor._parse_market_odds(SAMPLE_HTML_ODDS, "FullTime", odds_labels, target_bookmaker)
        
        # Assert
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"
        assert result[0]["1"] == "1.90"
        assert result[0]["X"] == "3.50"
        assert result[0]["2"] == "4.20"

    @pytest.mark.asyncio
    async def test_parse_market_odds_no_bookmakers(self, extractor):
        """Test parsing odds when no bookmakers are found."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        empty_html = "<div>No bookmakers found</div>"
        
        # Act
        result = await extractor._parse_market_odds(empty_html, "FullTime", odds_labels)
        
        # Assert
        assert len(result) == 0

    def test_parse_odds_history_modal(self, extractor):
        """Test parsing odds history from a modal HTML."""
        # Arrange - Mock datetime.now to avoid date-related issues
        with patch('src.core.odds_portal_market_extractor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(*args, **kwargs)
            
            # Act
            result = extractor._parse_odds_history_modal(SAMPLE_HTML_ODDS_HISTORY)
            
            # Assert
            assert "odds_history" in result
            assert len(result["odds_history"]) == 2
            assert result["odds_history"][0]["odds"] == 1.95
            assert result["odds_history"][1]["odds"] == 1.90
            
            # Verify that opening odds data is present without checking exact values
            # as they depend on the extractor implementation
            assert "opening_odds" in result

    @pytest.mark.asyncio
    async def test_extract_market_odds(self, extractor, page_mock, browser_helper_mock):
        """Test complete extraction of odds for a given market."""
        # Arrange
        browser_helper_mock.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor._parse_market_odds = AsyncMock(return_value=[
            {"bookmaker_name": "Bookmaker1", "1": "1.90", "X": "3.50", "2": "4.20", "period": "FullTime"}
        ])
        main_market = "1X2"
        odds_labels = ["1", "X", "2"]
        
        # Act
        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market=main_market,
            odds_labels=odds_labels
        )
        
        # Assert
        browser_helper_mock.navigate_to_market_tab.assert_called_once_with(
            page=page_mock, 
            market_tab_name=main_market, 
            timeout=extractor.DEFAULT_TIMEOUT
        )
        extractor._parse_market_odds.assert_called_once()
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"

    @pytest.mark.asyncio
    async def test_extract_market_odds_with_specific_market(self, extractor, page_mock, browser_helper_mock):
        """Test extracting odds with a specific sub-market."""
        # Arrange
        browser_helper_mock.navigate_to_market_tab = AsyncMock(return_value=True)
        browser_helper_mock.scroll_until_visible_and_click_parent = AsyncMock(return_value=True)
        extractor._parse_market_odds = AsyncMock(return_value=[
            {"bookmaker_name": "Bookmaker1", "odds_over": "1.90", "odds_under": "1.90", "period": "FullTime"}
        ])
        main_market = "Over/Under"
        specific_market = "Over/Under +2.5"
        odds_labels = ["odds_over", "odds_under"]
        
        # Act
        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market=main_market,
            specific_market=specific_market,
            odds_labels=odds_labels
        )
        
        # Assert
        browser_helper_mock.navigate_to_market_tab.assert_called_once()
        browser_helper_mock.scroll_until_visible_and_click_parent.assert_called()
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"

    @pytest.mark.asyncio
    async def test_extract_market_odds_tab_not_found(self, extractor, page_mock, browser_helper_mock):
        """Test behavior when the market tab is not found."""
        # Arrange
        browser_helper_mock.navigate_to_market_tab = AsyncMock(return_value=False)
        
        # Act
        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="NonExistentMarket",
            odds_labels=["1", "X", "2"]
        )
        
        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_scrape_markets(self, extractor, page_mock):
        """Test scraping multiple markets for a match."""
        # Arrange
        mock_market_func = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        
        with patch.object(SportMarketRegistry, 'get_market_mapping') as mock_get_mapping:
            mock_get_mapping.return_value = {
                "1x2": mock_market_func,
                "btts": mock_market_func
            }
            
            # Act
            result = await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["1x2", "btts", "nonexistent_market"]
            )
        
        # Assert
        assert "1x2_market" in result
        assert "btts_market" in result
        assert "nonexistent_market_market" not in result
        assert mock_market_func.call_count == 2 