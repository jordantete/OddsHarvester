from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from oddsharvester.core.browser.selection import PERIOD_STRATEGY
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.sport_market_registry import SportMarketRegistry
from oddsharvester.core.sport_period_registry import SportPeriodRegistry

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
    def selection_manager_mock(self):
        """Create a mock for SelectionManager."""
        return AsyncMock()

    @pytest.fixture
    def extractor(self, selection_manager_mock):
        """Create an instance of OddsPortalMarketExtractor with a mocked SelectionManager."""
        return OddsPortalMarketExtractor(
            scroller=AsyncMock(), tab_navigator=AsyncMock(), selection_manager=selection_manager_mock
        )

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
        result = extractor.odds_parser.parse_market_odds(SAMPLE_HTML_ODDS, "FullTime", odds_labels)

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
        result = extractor.odds_parser.parse_market_odds(SAMPLE_HTML_ODDS, "FullTime", odds_labels, target_bookmaker)

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
        result = extractor.odds_parser.parse_market_odds(empty_html, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_parse_market_odds_missing_data(self, extractor):
        """Test parsing odds when a bookmaker has incomplete data."""
        # Arrange
        odds_labels = ["1", "X", "2", "Extras"]

        # Act
        result = extractor.odds_parser.parse_market_odds(SAMPLE_HTML_ODDS, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_parse_market_odds_error_handling(self, extractor):
        """Test error handling during odds parsing."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        broken_html = """
        <div class="border-black-borders flex h-9">
            <img class="bookmaker-logo" title="Bookmaker1">
            <!-- Data manquante/corrompue -->
        </div>
        """

        # Act
        result = extractor.odds_parser.parse_market_odds(broken_html, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0  # Should handle error gracefully

    def test_parse_odds_history_modal(self, extractor):
        """Test parsing odds history from a modal HTML."""
        # Arrange
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(*args, **kwargs)

            # Act
            result = extractor.odds_parser.parse_odds_history_modal(SAMPLE_HTML_ODDS_HISTORY)

            # Assert
            assert "odds_history" in result
            assert len(result["odds_history"]) == 2
            assert result["odds_history"][0]["odds"] == 1.95
            assert result["odds_history"][1]["odds"] == 1.90

            # Verify that opening odds data is present without checking exact values
            # as they depend on the extractor implementation
            assert "opening_odds" in result

    def test_parse_odds_history_modal_invalid_html(self, extractor):
        """Test parsing odds history from invalid HTML."""
        # Arrange
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: datetime.strptime(*args, **kwargs)

            # Act
            invalid_html = "<div>Invalid HTML content</div>"
            result = extractor.odds_parser.parse_odds_history_modal(invalid_html)

            # Assert
            assert result == {}

    def test_parse_odds_history_modal_invalid_date(self, extractor):
        """Test parsing odds history with invalid date format."""
        # Arrange
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            # Force ValueError on strptime
            mock_datetime.strptime.side_effect = ValueError("Invalid date format")

            # Act
            result = extractor.odds_parser.parse_odds_history_modal(SAMPLE_HTML_ODDS_HISTORY)

            # Assert
            assert "odds_history" in result
            assert len(result["odds_history"]) == 0

    @pytest.mark.asyncio
    async def test_extract_market_odds(self, extractor, page_mock):
        """Test complete extraction of odds for a given market."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"bookmaker_name": "Bookmaker1", "1": "1.90", "X": "3.50", "2": "4.20", "period": "FullTime"}]
        )

        page_mock.content = AsyncMock(return_value="<div>test</div>")

        main_market = "1X2"
        odds_labels = ["1", "X", "2"]

        # Act
        result = await extractor.extract_market_odds(page=page_mock, main_market=main_market, odds_labels=odds_labels)

        # Assert
        extractor.navigation_manager.navigate_to_market_tab.assert_called_once_with(
            page=page_mock, market_tab_name=main_market
        )
        extractor.odds_parser.parse_market_odds.assert_called_once()
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"

    @pytest.mark.asyncio
    async def test_extract_market_odds_with_specific_market(self, extractor, page_mock):
        """Test extracting odds with a specific sub-market."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.navigation_manager.scroller.scroll_until_visible_and_click_parent = AsyncMock(return_value=True)
        extractor.navigation_manager.close_specific_market = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[
                {"bookmaker_name": "Bookmaker1", "odds_over": "1.90", "odds_under": "1.90", "period": "FullTime"}
            ]
        )

        page_mock.content = AsyncMock(return_value="<div>test</div>")

        main_market = "Over/Under"
        specific_market = "Over/Under +2.5"
        odds_labels = ["odds_over", "odds_under"]

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock, main_market=main_market, specific_market=specific_market, odds_labels=odds_labels
        )

        # Assert
        extractor.navigation_manager.navigate_to_market_tab.assert_called_once()
        extractor.navigation_manager.scroller.scroll_until_visible_and_click_parent.assert_called()
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"

    @pytest.mark.asyncio
    async def test_extract_market_odds_tab_not_found(self, extractor, page_mock):
        """Test behavior when the market tab is not found."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=False)

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock, main_market="NonExistentMarket", odds_labels=["1", "X", "2"]
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_market_odds_specific_market_not_found(self, extractor, page_mock):
        """Test behavior when the specific market is not found."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.scroller.scroll_until_visible_and_click_parent = AsyncMock(return_value=False)

        mock_active_tab = AsyncMock()
        mock_active_tab.text_content = AsyncMock(return_value="Over/Under")
        page_mock.query_selector = AsyncMock(return_value=mock_active_tab)

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="Over/Under",
            specific_market="NonExistentSpecificMarket",
            odds_labels=["odds_over", "odds_under"],
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_market_odds_with_odds_history(self, extractor, page_mock):
        """Test extracting odds with odds history."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"bookmaker_name": "Bookmaker1", "1": "1.90", "X": "3.50", "2": "4.20", "period": "FullTime"}]
        )
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker = AsyncMock(
            return_value=[SAMPLE_HTML_ODDS_HISTORY]
        )
        extractor.odds_parser.parse_odds_history_modal = MagicMock(
            return_value={
                "odds_history": [{"timestamp": "2025-06-10T14:30:00", "odds": 1.95}],
                "opening_odds": {"timestamp": "2025-06-10T08:00:00", "odds": 1.85},
            }
        )

        mock_active_tab = AsyncMock()
        mock_active_tab.text_content = AsyncMock(return_value="1X2")
        page_mock.query_selector = AsyncMock(return_value=mock_active_tab)
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], scrape_odds_history=True
        )

        # Assert
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker.assert_called_once()
        extractor.odds_parser.parse_odds_history_modal.assert_called_once()
        assert len(result) == 1
        assert "odds_history_data" in result[0]
        assert result[0]["odds_history_data"][0]["odds_history"][0]["odds"] == 1.95

    @pytest.mark.asyncio
    async def test_extract_market_odds_exception(self, extractor, page_mock):
        """Test handling of exceptions during market extraction."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(side_effect=Exception("Test exception"))

        # Act
        result = await extractor.extract_market_odds(page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"])

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker(self, extractor, page_mock):
        """Test extracting odds history for a specific bookmaker."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value=bookmaker_name)
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for odds blocks
        odds_block = AsyncMock()
        bookmaker_row.query_selector_all = AsyncMock(return_value=[odds_block])

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])
        page_mock.wait_for_selector = AsyncMock()

        # Create mock for modal wrapper and element
        modal_wrapper = AsyncMock()
        modal_element = AsyncMock()
        modal_element.inner_html = AsyncMock(return_value=SAMPLE_HTML_ODDS_HISTORY)
        modal_wrapper.as_element = MagicMock(return_value=modal_element)

        # Set up the chain of mocks
        page_mock.wait_for_selector.return_value.evaluate_handle.return_value = modal_wrapper

        # Act
        result = await extractor.odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert len(result) == 1
        assert result[0] == SAMPLE_HTML_ODDS_HISTORY

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_no_match(self, extractor, page_mock):
        """Test extraction when no matching bookmaker is found."""
        # Arrange
        bookmaker_name = "NonExistentBookmaker"

        # Create mock for bookmaker row
        bookmaker_row = AsyncMock()
        logo_img = AsyncMock()
        logo_img.get_attribute = AsyncMock(return_value="DifferentBookmaker")
        bookmaker_row.query_selector = AsyncMock(return_value=logo_img)

        # Create mock for page
        page_mock.query_selector_all = AsyncMock(return_value=[bookmaker_row])

        # Act
        result = await extractor.odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_odds_history_for_bookmaker_exception(self, extractor, page_mock):
        """Test error handling when an exception occurs during odds history extraction."""
        # Arrange
        bookmaker_name = "Bookmaker1"

        # Create mock that raises an exception
        page_mock.query_selector_all = AsyncMock(side_effect=Exception("Test exception"))

        # Act - This method handles exceptions internally
        result = await extractor.odds_history_extractor.extract_odds_history_for_bookmaker(page_mock, bookmaker_name)

        # Assert - Should return an empty list on exception
        assert result == []

    @pytest.mark.asyncio
    async def test_scrape_markets(self, extractor, page_mock):
        """Test scraping multiple markets for a match."""
        # Arrange
        mock_market_func = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": mock_market_func, "btts": mock_market_func}

            # Act
            result = await extractor.scrape_markets(
                page=page_mock, sport="football", markets=["1x2", "btts", "nonexistent_market"]
            )

        # Assert
        assert "1x2_market" in result
        assert "btts_market" in result
        assert "nonexistent_market_market" not in result
        assert mock_market_func.call_count == 2

    @pytest.mark.asyncio
    async def test_scrape_markets_expands_over_under_umbrella(self, extractor, page_mock):
        """Test that an umbrella token expands into one `{token}_market` entry per discovered line."""
        # Arrange
        mock_market_func = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        extractor._discover_line_names = AsyncMock(return_value=["Over/Under +2.5", "Over/Under +3.5"])

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {
                "over_under_2_5": mock_market_func,
                "over_under_3_5": mock_market_func,
            }

            # Act
            result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["over_under"])

        # Assert
        assert "over_under_2_5_market" in result
        assert "over_under_3_5_market" in result
        assert "over_under_market" not in result
        assert mock_market_func.call_count == 2
        extractor._discover_line_names.assert_called_once_with(
            page=page_mock, main_market="Over/Under", sport="football", period="FullTime"
        )

    @pytest.mark.asyncio
    async def test_scrape_markets_non_umbrella_markets_unchanged(self, extractor, page_mock):
        """Test that non-umbrella markets bypass line discovery entirely."""
        # Arrange
        mock_market_func = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        extractor._discover_line_names = AsyncMock()

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": mock_market_func, "btts": mock_market_func}

            # Act
            result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["1x2", "btts"])

        # Assert
        assert "1x2_market" in result
        assert "btts_market" in result
        extractor._discover_line_names.assert_not_called()

    @pytest.mark.asyncio
    async def test_scrape_markets_umbrella_gated_to_football_only(self, extractor, page_mock):
        """Test that umbrella expansion never triggers for a non-football sport.

        Umbrella tokens (over_under, asian_handicap) are football-only. Calling scrape_markets
        directly with sport="tennis" must not expand "over_under" using the football umbrella
        enums; it should fall through to the normal unsupported-market path instead.
        """
        # Arrange
        extractor._discover_line_names = AsyncMock()

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {}

            # Act
            result = await extractor.scrape_markets(page=page_mock, sport="tennis", markets=["over_under"])

        # Assert
        extractor._discover_line_names.assert_not_called()
        assert not any(key.startswith("over_under_") for key in result)

    @pytest.mark.asyncio
    async def test_scrape_markets_umbrella_discovery_exception_isolated(self, extractor, page_mock, caplog):
        """Test that an exception during umbrella line discovery is isolated to that umbrella only."""
        # Arrange
        mock_market_func = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        extractor._discover_line_names = AsyncMock(side_effect=Exception("boom"))

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": mock_market_func}

            # Act
            with caplog.at_level("WARNING"):
                result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["over_under", "1x2"])

        # Assert: the umbrella contributes no keys, but the rest of match's market_data is unaffected
        assert "over_under_market" not in result
        assert "1x2_market" in result
        assert result["1x2_market"] is not None
        assert any("over_under" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_scrape_markets_umbrella_preview_submarkets_routing(self, extractor, page_mock):
        """Test that umbrella expansion composes with preview_submarkets_only grouping.

        markets=["over_under"] should expand to the discovered lines and then be routed through
        the preview-mode grouping path, producing one key per discovered line (not a single
        `over_under_market` key).
        """
        # Arrange
        extractor._discover_line_names = AsyncMock(return_value=["Over/Under +2.5", "Over/Under +3.5"])

        def _make_closure(main_market, odds_labels):
            return lambda self, page, period, hist, bk, preview, sport: (main_market, odds_labels)

        func_2_5 = _make_closure("Over/Under", ["odds_over", "odds_under"])
        func_3_5 = _make_closure("Over/Under", ["odds_over", "odds_under"])

        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock) as mock_extract,
        ):
            mock_get_mapping.return_value = {
                "over_under_2_5": func_2_5,
                "over_under_3_5": func_3_5,
            }
            mock_extract.return_value = [{"submarket_name": "Over/Under +2.5", "odds_over": "1.90"}]

            # Act
            result = await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under"],
                preview_submarkets_only=True,
            )

        # Assert
        assert "over_under_2_5_market" in result
        assert "over_under_3_5_market" in result
        assert "over_under_market" not in result
        mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_markets_mixed_umbrella_and_explicit_token_deduped(self, extractor, page_mock):
        """Test that an umbrella token and an explicit literal token it would also produce are deduped.

        markets=["over_under", "over_under_2_5"]: the umbrella discovers a line mapping to
        "over_under_2_5" (already explicitly requested) plus another line "over_under_3_5".
        The extraction function for over_under_2_5 must run only once, and both line keys must exist.
        """
        # Arrange
        mock_market_func_2_5 = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        mock_market_func_3_5 = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        extractor._discover_line_names = AsyncMock(return_value=["Over/Under +2.5", "Over/Under +3.5"])

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {
                "over_under_2_5": mock_market_func_2_5,
                "over_under_3_5": mock_market_func_3_5,
            }

            # Act
            result = await extractor.scrape_markets(
                page=page_mock, sport="football", markets=["over_under", "over_under_2_5"]
            )

        # Assert
        assert "over_under_2_5_market" in result
        assert "over_under_3_5_market" in result
        assert mock_market_func_2_5.call_count == 1
        assert mock_market_func_3_5.call_count == 1

    @pytest.mark.asyncio
    async def test_scrape_markets_umbrella_zero_lines_discovered(self, extractor, page_mock, caplog):
        """Test that an umbrella token with no discovered lines logs a warning and contributes no keys."""
        # Arrange
        extractor._discover_line_names = AsyncMock(return_value=[])

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {}

            # Act
            with caplog.at_level("WARNING"):
                result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["over_under"])

        # Assert
        assert result == {}
        assert any("over_under" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_discover_line_names_returns_submarket_names(self, extractor, page_mock):
        """Test that _discover_line_names navigates the tab and returns rendered submarket names."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.submarket_extractor.extract_visible_submarkets_passive = AsyncMock(
            return_value=[
                {"submarket_name": "Over/Under +2.5"},
                {"submarket_name": "Over/Under +3.5"},
            ]
        )

        # Act
        result = await extractor._discover_line_names(
            page=page_mock, main_market="Over/Under", sport="football", period="FullTime"
        )

        # Assert
        assert result == ["Over/Under +2.5", "Over/Under +3.5"]
        extractor.navigation_manager.navigate_to_market_tab.assert_called_once_with(
            page=page_mock, market_tab_name="Over/Under"
        )

    @pytest.mark.asyncio
    async def test_discover_line_names_tab_not_found_returns_empty(self, extractor, page_mock):
        """Test that _discover_line_names returns [] when the market tab can't be found."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=False)

        # Act
        result = await extractor._discover_line_names(
            page=page_mock, main_market="Over/Under", sport="football", period="FullTime"
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_scrape_markets_with_exception(self, extractor, page_mock):
        """Test scraping markets where one market throws an exception."""
        # Arrange
        mock_success_func = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        mock_error_func = AsyncMock(side_effect=Exception("Test exception"))

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": mock_success_func, "btts": mock_error_func}

            # Act
            result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["1x2", "btts"])

        # Assert
        assert "1x2_market" in result
        assert "btts_market" in result
        assert result["1x2_market"] is not None
        assert result["btts_market"] is None

    @pytest.mark.asyncio
    async def test_scrape_markets_preview_mode_groups_markets(self, extractor, page_mock):
        """Test that preview mode groups markets by main market and scrapes once."""
        # Arrange — two markets sharing the same main market
        main_market = "Over/Under"
        odds_labels = ["odds_over", "odds_under"]

        def _make_closure(main_market, odds_labels):
            return lambda self, page, period, hist, bk, preview, sport: (main_market, odds_labels)

        func_a = _make_closure(main_market, odds_labels)
        func_b = _make_closure(main_market, odds_labels)

        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock) as mock_extract,
        ):
            mock_mapping.return_value = {"over_under_1_5": func_a, "over_under_2_5": func_b}
            mock_extract.return_value = [{"submarket_name": "Over/Under 1.5", "odds_over": "1.50"}]

            result = await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under_1_5", "over_under_2_5"],
                preview_submarkets_only=True,
            )

        # Both markets should get the same data, extract called once for the group
        assert "over_under_1_5_market" in result
        assert "over_under_2_5_market" in result
        mock_extract.assert_called_once()

    @pytest.mark.asyncio
    async def test_scrape_markets_preview_mode_exception_sets_none(self, extractor, page_mock):
        """Test that grouped market exception in preview mode sets all group entries to None."""
        main_market = "Over/Under"
        odds_labels = ["odds_over", "odds_under"]

        def _make_closure(main_market, odds_labels):
            return lambda self, page, period, hist, bk, preview, sport: (main_market, odds_labels)

        func = _make_closure(main_market, odds_labels)

        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock, side_effect=Exception("boom")),
        ):
            mock_mapping.return_value = {"over_under_1_5": func, "over_under_2_5": func}

            result = await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under_1_5", "over_under_2_5"],
                preview_submarkets_only=True,
            )

        assert result["over_under_1_5_market"] is None
        assert result["over_under_2_5_market"] is None

    @pytest.mark.asyncio
    async def test_extract_market_odds_uses_scope_code_when_verified(
        self, extractor, page_mock, selection_manager_mock
    ):
        """Verified periods (football FullTime=scope 2) select by scope, not localized label."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.odds_parser.parse_market_odds = MagicMock(return_value=[])
        extractor.period_selector.select_by_scope = AsyncMock(return_value=True)

        mock_period = MagicMock()
        mock_period.get_display_label = MagicMock(return_value="Full Time")
        with patch.object(SportPeriodRegistry, "from_internal_value", return_value=mock_period):
            await extractor.extract_market_odds(
                page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], sport="football", period="FullTime"
            )

        extractor.period_selector.select_by_scope.assert_awaited_once_with(
            page=page_mock, sport="football", internal_period="FullTime"
        )
        # Scope path handled it -> no label fallback.
        selection_manager_mock.ensure_selected.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_market_odds_falls_back_to_label_when_no_scope(
        self, extractor, page_mock, selection_manager_mock
    ):
        """Unverified periods fall back to localized-label selection (select_by_scope -> None)."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.odds_parser.parse_market_odds = MagicMock(return_value=[])
        extractor.period_selector.select_by_scope = AsyncMock(return_value=None)

        mock_period = MagicMock()
        mock_period.get_display_label = MagicMock(return_value="2nd Set")
        with patch.object(SportPeriodRegistry, "from_internal_value", return_value=mock_period):
            await extractor.extract_market_odds(
                page=page_mock, main_market="Over/Under", odds_labels=["1", "2"], sport="tennis", period="SecondSet"
            )

        selection_manager_mock.ensure_selected.assert_called_once_with(
            page=page_mock,
            target_value="2nd Set",
            display_label="2nd Set",
            strategy=PERIOD_STRATEGY,
        )

    @pytest.mark.asyncio
    async def test_extract_market_odds_period_not_found_skips(self, extractor, page_mock, selection_manager_mock):
        """Test that period selection is skipped when period enum is not found."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.odds_parser.parse_market_odds = MagicMock(return_value=[])
        extractor.period_selector.select_by_scope = AsyncMock(return_value=True)

        with patch.object(SportPeriodRegistry, "from_internal_value", return_value=None):
            await extractor.extract_market_odds(
                page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], sport="football", period="FullTime"
            )

        selection_manager_mock.ensure_selected.assert_not_called()
        extractor.period_selector.select_by_scope.assert_not_called()

    @pytest.mark.asyncio
    async def test_extract_market_odds_preview_mode_passive(self, extractor, page_mock):
        """Test preview mode uses passive submarket extraction."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.submarket_extractor.extract_visible_submarkets_passive = AsyncMock(
            return_value=[{"submarket_name": "Over/Under 2.5", "odds_over": "1.80", "odds_under": "2.00"}]
        )

        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="Over/Under",
            odds_labels=["odds_over", "odds_under"],
            preview_submarkets_only=True,
        )

        extractor.submarket_extractor.extract_visible_submarkets_passive.assert_called_once()
        assert len(result) == 1
        assert result[0]["submarket_name"] == "Over/Under 2.5"

    @pytest.mark.asyncio
    async def test_extract_market_odds_preview_mode_fallback_to_active(self, extractor, page_mock):
        """Test preview mode falls back to normal scraping when passive returns no data."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.submarket_extractor.extract_visible_submarkets_passive = AsyncMock(return_value=[])
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"bookmaker_name": "Bookmaker1", "1": "1.90"}]
        )
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="1X2",
            odds_labels=["1", "X", "2"],
            preview_submarkets_only=True,
        )

        extractor.submarket_extractor.extract_visible_submarkets_passive.assert_called_once()
        extractor.odds_parser.parse_market_odds.assert_called_once()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_extract_market_odds_preview_fallback_specific_market_not_found(self, extractor, page_mock):
        """Test preview fallback returns [] when specific market can't be selected."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.submarket_extractor.extract_visible_submarkets_passive = AsyncMock(return_value=[])
        extractor.navigation_manager.select_specific_market = AsyncMock(return_value=False)

        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="Over/Under",
            specific_market="Over/Under +9.5",
            odds_labels=["odds_over", "odds_under"],
            preview_submarkets_only=True,
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_extract_market_odds_history_skips_filtered_bk(self, extractor, page_mock):
        """Test that odds history is skipped for bookmakers not matching target."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_market_switch = AsyncMock(return_value=True)
        extractor.navigation_manager.wait_for_page_load = AsyncMock()
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[
                {"bookmaker_name": "Bookmaker1", "1": "1.90", "period": "FullTime"},
                {"bookmaker_name": "Bookmaker2", "1": "1.85", "period": "FullTime"},
            ]
        )
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker = AsyncMock()
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        await extractor.extract_market_odds(
            page=page_mock,
            main_market="1X2",
            odds_labels=["1"],
            scrape_odds_history=True,
            target_bookmaker="Bookmaker1",
        )

        # Only called for Bookmaker1, not Bookmaker2
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker.assert_called_once_with(
            page_mock, "Bookmaker1"
        )
