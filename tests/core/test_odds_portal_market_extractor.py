from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tests.dom_builders import bookmaker_row, odds_table

from oddsharvester.core.browser.selection import PERIOD_STRATEGY, SelectionManager
from oddsharvester.core.exceptions import MarketDataError
from oddsharvester.core.odds_portal_market_extractor import OddsPortalMarketExtractor
from oddsharvester.core.sport_market_registry import MarketSpec, SportMarketRegistry
from oddsharvester.core.sport_period_registry import SportPeriodRegistry
from oddsharvester.utils.bookies_filter_enum import BookiesFilter

ONE_X_TWO = MarketSpec("1X2", odds_labels=("1", "X", "2"))
BTTS = MarketSpec("Both Teams to Score", odds_labels=("btts_yes", "btts_no"))


def over_under(line: str) -> MarketSpec:
    return MarketSpec("Over/Under", f"Over/Under +{line}", ("odds_over", "odds_under"))


# Sample odds table: one leaf <tr> per bookmaker
SAMPLE_HTML_ODDS = odds_table(
    bookmaker_row("Bookmaker1", ["1.90", "3.50", "4.20"], payout="94.1%")
    + bookmaker_row("Bookmaker2", ["1.85", "3.60", "4.10"], payout="94.0%")
)

SAMPLE_HTML_ODDS_HISTORY = """
<div class="flex w-max flex-col gap-2">
    <h3 class="text-sm font-semibold uppercase leading-6">Odds movement</h3>
    <div class="flex flex-row gap-3">
        <div class="flex flex-col gap-1">
            <div class="text-[10px] font-normal">10 Jun, 14:30</div>
            <div class="text-[10px] font-normal">10 Jun, 12:00</div>
        </div>
        <div class="flex flex-col gap-1">
            <div class="text-[10px] font-bold">1.95</div>
            <div class="text-[10px] font-bold">1.90</div>
        </div>
        <div class="flex flex-col gap-1">
            <div class="text-[10px] font-bold text-green-dark">+0.05</div>
        </div>
    </div>
    <div class="mt-2 gap-1">
        <div class="text-[10px] font-bold">Opening odds:</div>
        <div class="flex gap-1"><div class="font-normal">10 Jun, 08:00</div><div class="font-bold">1.85</div></div>
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

    async def test_extract_market_odds(self, extractor, page_mock):
        """Test complete extraction of odds for a given market."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
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

    async def test_a_flat_market_is_read_right_after_the_switch(self, extractor, page_mock):
        """R8 on a flat market: the switch already waited for the view, so the table is read at once."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.select_specific_market = AsyncMock()

        result = await extractor.extract_market_odds(page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"])

        assert [entry["bookmaker_name"] for entry in result] == ["Bookmaker1", "Bookmaker2"]
        extractor.navigation_manager.select_specific_market.assert_not_awaited()
        page_mock.wait_for_timeout.assert_not_awaited()
        page_mock.wait_for_function.assert_not_awaited()

    async def test_extract_market_odds_with_specific_market(self, extractor, page_mock):
        """Test extracting odds with a specific sub-market."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.scroller.click_line_row = AsyncMock(return_value=True)
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
        extractor.navigation_manager.scroller.click_line_row.assert_called()
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"

    async def test_extract_market_odds_stamps_submarket_name(self, extractor, page_mock):
        """Line markets: every odds dict carries the rendered line via submarket_name (issue #78)."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.scroller.click_line_row = AsyncMock(return_value=True)
        extractor.navigation_manager.close_specific_market = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[
                {"bookmaker_name": "Bookmaker1", "odds_over": "1.90", "odds_under": "1.90", "period": "FullTime"},
                {"bookmaker_name": "Bookmaker2", "odds_over": "1.85", "odds_under": "1.95", "period": "FullTime"},
            ]
        )
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="Over/Under",
            specific_market="Over/Under +2.5",
            odds_labels=["odds_over", "odds_under"],
        )

        # Assert
        assert [entry["submarket_name"] for entry in result] == ["Over/Under +2.5", "Over/Under +2.5"]

    async def test_extract_market_odds_stamps_main_market_name(self, extractor, page_mock):
        """Main markets (no specific_market): dicts carry the market label itself."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"bookmaker_name": "Bookmaker1", "1": "1.90", "X": "3.50", "2": "4.20", "period": "FullTime"}]
        )
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        # Act
        result = await extractor.extract_market_odds(page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"])

        # Assert
        assert result[0]["submarket_name"] == "1X2"

    async def test_extract_market_odds_main_market_stamp_lands_last(self, extractor, page_mock):
        """The stamp is appended, never inserted before the odds or the bookmaker."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"btts_yes": "1.72", "btts_no": "2.12", "bookmaker_name": "Bookmaker1", "period": "FullTime"}]
        )
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock, main_market="Both Teams to Score", odds_labels=["btts_yes", "btts_no"]
        )

        # Assert
        assert list(result[0]) == ["btts_yes", "btts_no", "bookmaker_name", "period", "submarket_name"]

    async def test_extract_market_odds_main_market_does_not_overwrite_existing_name(self, extractor, page_mock):
        """A name already set upstream wins over the main market label."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"bookmaker_name": "Bookmaker1", "1": "1.90", "submarket_name": "Already set"}]
        )
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        # Act
        result = await extractor.extract_market_odds(page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"])

        # Assert
        assert result[0]["submarket_name"] == "Already set"

    async def test_extract_market_odds_preserves_passive_submarket_name(self, extractor, page_mock):
        """Preview passive dicts already carry submarket_name; stamping must never overwrite it."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.submarket_extractor.extract_visible_submarkets_passive = AsyncMock(
            return_value=[
                {
                    "submarket_name": "Over/Under +1.5",
                    "period": "FullTime",
                    "market_type": "Over/Under",
                    "extraction_mode": "passive",
                    "odds_over": "1.30",
                    "odds_under": "3.40",
                }
            ]
        )

        # Act
        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="Over/Under",
            specific_market="Over/Under +2.5",
            odds_labels=["odds_over", "odds_under"],
            preview_submarkets_only=True,
        )

        # Assert
        assert result[0]["submarket_name"] == "Over/Under +1.5"

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

    async def test_extract_market_odds_specific_market_not_found(self, extractor, page_mock):
        """Test behavior when the specific market is not found."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.navigation_manager.scroller.click_line_row = AsyncMock(return_value=False)

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

    async def test_extract_market_odds_with_odds_history(self, extractor, page_mock):
        """Each outcome gets its block; a modal that could not be read becomes the empty block."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"1": "1.90", "X": "3.50", "2": "4.20", "bookmaker_name": "Bookmaker1", "period": "FullTime"}]
        )
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker = AsyncMock(
            return_value=[SAMPLE_HTML_ODDS_HISTORY, None, SAMPLE_HTML_ODDS_HISTORY]
        )
        parsed = {
            "odds_history": [{"timestamp": "2025-06-10T14:30:00", "odds": 1.95}],
            "opening_odds": {"timestamp": "2025-06-10T08:00:00", "odds": 1.85},
        }
        extractor.odds_parser.parse_odds_history_modal = MagicMock(return_value=parsed)
        page_mock.content = AsyncMock(return_value="<div>test</div>")
        reference = datetime(2025, 6, 11, 20, 0)

        result = await extractor.extract_market_odds(
            page=page_mock,
            main_market="1X2",
            odds_labels=["1", "X", "2"],
            scrape_odds_history=True,
            history_reference=reference,
            history_timezone="Europe/London",
        )

        extractor.odds_history_extractor.extract_odds_history_for_bookmaker.assert_awaited_once_with(
            page_mock, "Bookmaker1", 3
        )
        assert extractor.odds_parser.parse_odds_history_modal.call_count == 2
        extractor.odds_parser.parse_odds_history_modal.assert_called_with(
            SAMPLE_HTML_ODDS_HISTORY, reference=reference, tz_name="Europe/London"
        )
        assert result[0]["odds_history_data"] == [parsed, {"odds_history": [], "opening_odds": None}, parsed]
        assert list(result[0])[-1] == "odds_history_data"

    async def test_odds_history_pads_missing_modals_with_empty_blocks(self, extractor, page_mock):
        """Fewer modals than outcomes still gives one block per outcome."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"1": "1.90", "X": "3.50", "2": "4.20", "bookmaker_name": "Bookmaker1", "period": "FullTime"}]
        )
        extractor.odds_history_extractor.extract_odds_history_for_bookmaker = AsyncMock(return_value=[None])
        page_mock.content = AsyncMock(return_value="<div>test</div>")

        result = await extractor.extract_market_odds(
            page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], scrape_odds_history=True
        )

        assert result[0]["odds_history_data"] == [{"odds_history": [], "opening_odds": None}] * 3

    async def test_normal_mode_scrapes_each_market_with_its_spec_and_the_call_arguments(self, extractor, page_mock):
        reference = datetime(2026, 1, 4, 18, 30)
        with (
            patch.object(SportMarketRegistry, "get_market_mapping", return_value={"over_under_2_5": over_under("2.5")}),
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock, return_value=[]) as mock_extract,
        ):
            await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under_2_5"],
                period="FirstHalf",
                scrape_odds_history=True,
                target_bookmaker="bet365",
                history_reference=reference,
                history_timezone="Europe/London",
                bookies_filter=BookiesFilter.CRYPTO,
            )

        mock_extract.assert_awaited_once_with(
            page=page_mock,
            main_market="Over/Under",
            specific_market="Over/Under +2.5",
            period="FirstHalf",
            odds_labels=("odds_over", "odds_under"),
            scrape_odds_history=True,
            target_bookmaker="bet365",
            preview_submarkets_only=False,
            sport="football",
            history_reference=reference,
            history_timezone="Europe/London",
            bookies_filter=BookiesFilter.CRYPTO,
        )

    async def test_scrape_markets_forwards_the_history_zone_in_preview_mode(self, extractor, page_mock):
        with (
            patch.object(SportMarketRegistry, "get_market_mapping", return_value={"over_under_2_5": over_under("2.5")}),
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock, return_value=[]) as mock_extract,
        ):
            await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under_2_5"],
                preview_submarkets_only=True,
                history_timezone="Europe/London",
                bookies_filter=BookiesFilter.ALL,
            )

        assert mock_extract.await_args.kwargs["history_timezone"] == "Europe/London"
        assert mock_extract.await_args.kwargs["bookies_filter"] == BookiesFilter.ALL

    async def test_extract_market_odds_exception(self, extractor, page_mock):
        """Test handling of exceptions during market extraction."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(side_effect=Exception("Test exception"))

        # Act
        result = await extractor.extract_market_odds(page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"])

        # Assert
        assert result == []

    async def test_scrape_markets(self, extractor, page_mock):
        """Test scraping multiple markets for a match."""
        # Arrange
        extractor.extract_market_odds = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": ONE_X_TWO, "btts": BTTS}

            # Act
            result = await extractor.scrape_markets(
                page=page_mock, sport="football", markets=["1x2", "btts", "nonexistent_market"]
            )

        # Assert
        assert "1x2_market" in result
        assert "btts_market" in result
        assert "nonexistent_market_market" not in result
        assert extractor.extract_market_odds.await_count == 2

    @staticmethod
    def _tennis_over_under_markets():
        def line(label, line_axis):
            return MarketSpec("Over/Under", label, ("odds_over", "odds_under"), line_axis=line_axis)

        return {
            "over_under_sets_6_5": line("Over/Under +6.5", "sets"),
            "over_under_games_6_5": line("Over/Under +6.5", "games"),
            "over_under_games_39_5": line("Over/Under +39.5", "games"),
        }

    async def test_scrape_markets_refuses_a_line_another_axis_may_hold(self, extractor, page_mock, caplog):
        """Tennis sets 6.5 falls in the games axis's range: the market comes back empty, never guessed."""
        extractor.extract_market_odds = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])

        with (
            patch.object(SportMarketRegistry, "get_market_mapping", return_value=self._tennis_over_under_markets()),
            caplog.at_level("WARNING"),
        ):
            result = await extractor.scrape_markets(
                page=page_mock, sport="tennis", markets=["over_under_sets_6_5", "over_under_games_39_5"]
            )

        assert result == {
            "over_under_sets_6_5_market": [],
            "over_under_games_39_5_market": [{"bookmaker_name": "Bookmaker1"}],
        }
        extractor.extract_market_odds.assert_awaited_once()
        assert extractor.extract_market_odds.await_args.kwargs["specific_market"] == "Over/Under +39.5"
        assert (
            "Market 'over_under_sets_6_5' refused: its line may also be a games line, "
            "and the page does not tell them apart." in caplog.text
        )

    async def test_scrape_markets_refuses_a_shared_line_in_preview_mode(self, extractor, page_mock):
        extractor.extract_market_odds = AsyncMock(return_value=[{"submarket_name": "Over/Under +6.5"}])

        with patch.object(SportMarketRegistry, "get_market_mapping", return_value=self._tennis_over_under_markets()):
            result = await extractor.scrape_markets(
                page=page_mock, sport="tennis", markets=["over_under_games_6_5"], preview_submarkets_only=True
            )

        assert result == {"over_under_games_6_5_market": []}
        extractor.extract_market_odds.assert_not_awaited()

    async def test_scrape_markets_expands_over_under_umbrella(self, extractor, page_mock):
        """Test that an umbrella token expands into one `{token}_market` entry per discovered line."""
        # Arrange
        extractor.extract_market_odds = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        extractor._discover_line_names = AsyncMock(return_value=["Over/Under +2.5", "Over/Under +3.5"])

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {
                "over_under_2_5": over_under("2.5"),
                "over_under_3_5": over_under("3.5"),
            }

            # Act
            result = await extractor.scrape_markets(
                page=page_mock, sport="football", markets=["over_under"], bookies_filter=BookiesFilter.ALL
            )

        # Assert
        assert "over_under_2_5_market" in result
        assert "over_under_3_5_market" in result
        assert "over_under_market" not in result
        assert extractor.extract_market_odds.await_count == 2
        extractor._discover_line_names.assert_called_once_with(
            page=page_mock, main_market="Over/Under", period="FullTime", bookies_filter=BookiesFilter.ALL
        )

    async def test_scrape_markets_expands_the_umbrella_from_localized_line_names(self, extractor, page_mock):
        """--base-url https://www.cuotasahora.com renders 'Más/Menos de +2.5'; the tokens are the .com ones."""
        extractor.extract_market_odds = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        extractor._discover_line_names = AsyncMock(return_value=["Más/Menos de +2.5", "Más/Menos de +3.5"])

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"over_under_2_5": over_under("2.5"), "over_under_3_5": over_under("3.5")}

            result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["over_under"])

        assert set(result) == {"over_under_2_5_market", "over_under_3_5_market"}

    async def test_scrape_markets_skips_the_umbrella_when_no_name_ends_with_a_line(self, extractor, page_mock, caplog):
        extractor._discover_line_names = AsyncMock(return_value=["Más/Menos de +2.5 Goles"])

        with patch.object(SportMarketRegistry, "get_market_mapping", return_value={}), caplog.at_level("WARNING"):
            result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["over_under"])

        assert result == {}
        assert "Umbrella market 'over_under' discovered no lines on the page; skipping." in caplog.text

    async def test_scrape_markets_non_umbrella_markets_unchanged(self, extractor, page_mock):
        """Test that non-umbrella markets bypass line discovery entirely."""
        # Arrange
        extractor.extract_market_odds = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        extractor._discover_line_names = AsyncMock()

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": ONE_X_TWO, "btts": BTTS}

            # Act
            result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["1x2", "btts"])

        # Assert
        assert "1x2_market" in result
        assert "btts_market" in result
        extractor._discover_line_names.assert_not_called()

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

    async def test_scrape_markets_umbrella_discovery_exception_isolated(self, extractor, page_mock, caplog):
        """Test that an exception during umbrella line discovery is isolated to that umbrella only."""
        # Arrange
        extractor.extract_market_odds = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        extractor._discover_line_names = AsyncMock(side_effect=Exception("boom"))

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": ONE_X_TWO}

            # Act
            with caplog.at_level("WARNING"):
                result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["over_under", "1x2"])

        # Assert: the umbrella contributes no keys, but the rest of match's market_data is unaffected
        assert "over_under_market" not in result
        assert "1x2_market" in result
        assert result["1x2_market"] is not None
        assert any("over_under" in message for message in caplog.messages)

    async def test_scrape_markets_umbrella_preview_submarkets_routing(self, extractor, page_mock):
        """Test that umbrella expansion composes with preview_submarkets_only grouping.

        markets=["over_under"] should expand to the discovered lines and then be routed through
        the preview-mode grouping path, producing one key per discovered line (not a single
        `over_under_market` key).
        """
        # Arrange
        extractor._discover_line_names = AsyncMock(return_value=["Over/Under +2.5", "Over/Under +3.5"])

        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock) as mock_extract,
        ):
            mock_get_mapping.return_value = {
                "over_under_2_5": over_under("2.5"),
                "over_under_3_5": over_under("3.5"),
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

    async def test_scrape_markets_mixed_umbrella_and_explicit_token_deduped(self, extractor, page_mock):
        """Test that an umbrella token and an explicit literal token it would also produce are deduped.

        markets=["over_under", "over_under_2_5"]: the umbrella discovers a line mapping to
        "over_under_2_5" (already explicitly requested) plus another line "over_under_3_5".
        The extraction function for over_under_2_5 must run only once, and both line keys must exist.
        """
        # Arrange
        extractor.extract_market_odds = AsyncMock(return_value=[{"bookmaker_name": "Bookmaker1"}])
        extractor._discover_line_names = AsyncMock(return_value=["Over/Under +2.5", "Over/Under +3.5"])

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {
                "over_under_2_5": over_under("2.5"),
                "over_under_3_5": over_under("3.5"),
            }

            # Act
            result = await extractor.scrape_markets(
                page=page_mock, sport="football", markets=["over_under", "over_under_2_5"]
            )

        # Assert
        assert "over_under_2_5_market" in result
        assert "over_under_3_5_market" in result
        assert [call.kwargs["specific_market"] for call in extractor.extract_market_odds.await_args_list] == [
            "Over/Under +2.5",
            "Over/Under +3.5",
        ]

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

    async def test_discover_line_names_returns_submarket_names(self, extractor, page_mock):
        """Test that _discover_line_names navigates the tab and returns rendered submarket names."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.submarket_extractor.extract_visible_submarkets_passive = AsyncMock(
            return_value=[
                {"submarket_name": "Over/Under +2.5"},
                {"submarket_name": "Over/Under +3.5"},
            ]
        )

        # Act
        result = await extractor._discover_line_names(page=page_mock, main_market="Over/Under", period="FullTime")

        # Assert
        assert result == ["Over/Under +2.5", "Over/Under +3.5"]
        extractor.navigation_manager.navigate_to_market_tab.assert_called_once_with(
            page=page_mock, market_tab_name="Over/Under"
        )

    async def test_discover_line_names_tab_not_found_returns_empty(self, extractor, page_mock):
        """Test that _discover_line_names returns [] when the market tab can't be found."""
        # Arrange
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=False)

        # Act
        result = await extractor._discover_line_names(page=page_mock, main_market="Over/Under", period="FullTime")

        # Assert
        assert result == []

    async def test_scrape_markets_with_exception(self, extractor, page_mock):
        """Test scraping markets where one market throws an exception."""
        # Arrange
        extractor.extract_market_odds = AsyncMock(
            side_effect=[[{"bookmaker_name": "Bookmaker1"}], Exception("Test exception")]
        )

        with patch.object(SportMarketRegistry, "get_market_mapping") as mock_get_mapping:
            mock_get_mapping.return_value = {"1x2": ONE_X_TWO, "btts": BTTS}

            # Act
            result = await extractor.scrape_markets(page=page_mock, sport="football", markets=["1x2", "btts"])

        # Assert
        assert "1x2_market" in result
        assert "btts_market" in result
        assert result["1x2_market"] is not None
        assert result["btts_market"] is None

    async def test_scrape_markets_preview_mode_groups_markets(self, extractor, page_mock):
        """Preview mode scrapes a main market once, with its spec's labels, and gives each token that result."""
        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock) as mock_extract,
        ):
            mock_mapping.return_value = {"over_under_1_5": over_under("1.5"), "over_under_2_5": over_under("2.5")}
            mock_extract.return_value = [{"submarket_name": "Over/Under 1.5", "odds_over": "1.50"}]

            result = await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under_1_5", "over_under_2_5"],
                preview_submarkets_only=True,
            )

        assert result == {
            "over_under_1_5_market": mock_extract.return_value,
            "over_under_2_5_market": mock_extract.return_value,
        }
        mock_extract.assert_awaited_once()
        assert mock_extract.await_args.kwargs["main_market"] == "Over/Under"
        assert mock_extract.await_args.kwargs["specific_market"] is None
        assert mock_extract.await_args.kwargs["odds_labels"] == ("odds_over", "odds_under")
        assert mock_extract.await_args.kwargs["preview_submarkets_only"] is True

    async def test_scrape_markets_preview_mode_exception_sets_none(self, extractor, page_mock):
        """Test that grouped market exception in preview mode sets all group entries to None."""
        with (
            patch.object(SportMarketRegistry, "get_market_mapping") as mock_mapping,
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock, side_effect=Exception("boom")),
        ):
            mock_mapping.return_value = {"over_under_1_5": over_under("1.5"), "over_under_2_5": over_under("2.5")}

            result = await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under_1_5", "over_under_2_5"],
                preview_submarkets_only=True,
            )

        assert result["over_under_1_5_market"] is None
        assert result["over_under_2_5_market"] is None

    async def test_preview_mode_keeps_the_order_of_its_groups(self, extractor, page_mock):
        """Interleaved main markets: each is scraped once, the record lists a group's tokens together."""
        with (
            patch.object(
                SportMarketRegistry,
                "get_market_mapping",
                return_value={
                    "over_under_1_5": over_under("1.5"),
                    "over_under_2_5": over_under("2.5"),
                    "1x2": ONE_X_TWO,
                },
            ),
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock, return_value=[]) as mock_extract,
        ):
            result = await extractor.scrape_markets(
                page=page_mock,
                sport="football",
                markets=["over_under_2_5", "1x2", "over_under_1_5"],
                preview_submarkets_only=True,
            )

        assert list(result) == ["over_under_2_5_market", "over_under_1_5_market", "1x2_market"]
        assert [call.kwargs["main_market"] for call in mock_extract.await_args_list] == ["Over/Under", "1X2"]

    async def test_preview_mode_leaves_refused_and_unsupported_tokens_out_of_the_group(self, extractor, page_mock):
        """A refused line stays [], an unsupported token gets no key, the valid line of that main market is scraped."""
        with (
            patch.object(SportMarketRegistry, "get_market_mapping", return_value=self._tennis_over_under_markets()),
            patch.object(
                extractor, "extract_market_odds", new_callable=AsyncMock, return_value=[{"odds_over": "1.90"}]
            ) as mock_extract,
        ):
            result = await extractor.scrape_markets(
                page=page_mock,
                sport="tennis",
                markets=["over_under_sets_6_5", "over_under_99_5", "over_under_games_39_5"],
                preview_submarkets_only=True,
            )

        assert result == {"over_under_sets_6_5_market": [], "over_under_games_39_5_market": [{"odds_over": "1.90"}]}
        assert list(result) == ["over_under_sets_6_5_market", "over_under_games_39_5_market"]
        mock_extract.assert_awaited_once()
        assert mock_extract.await_args.kwargs["odds_labels"] == ("odds_over", "odds_under")

    async def test_preview_mode_scrapes_a_group_with_its_first_market_labels(self, extractor, page_mock):
        points = MarketSpec(
            "Asian Handicap", "Asian Handicap +3.5", ("points_handicap_team_1", "points_handicap_team_2")
        )
        sets = MarketSpec("Asian Handicap", "Asian Handicap +0.5", ("sets_handicap_team_1", "sets_handicap_team_2"))
        with (
            patch.object(SportMarketRegistry, "get_market_mapping", return_value={"points": points, "sets": sets}),
            patch.object(extractor, "extract_market_odds", new_callable=AsyncMock, return_value=[]) as mock_extract,
        ):
            await extractor.scrape_markets(
                page=page_mock, sport="volleyball", markets=["points", "sets"], preview_submarkets_only=True
            )

        mock_extract.assert_awaited_once()
        assert mock_extract.await_args.kwargs["odds_labels"] == ("points_handicap_team_1", "points_handicap_team_2")

    async def test_extract_market_odds_uses_scope_code_when_verified(
        self, extractor, page_mock, selection_manager_mock
    ):
        """Verified periods (football FullTime=scope 2) select by scope, not localized label."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
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

    async def test_extract_market_odds_falls_back_to_label_when_no_scope(
        self, extractor, page_mock, selection_manager_mock
    ):
        """Unverified periods fall back to localized-label selection (select_by_scope -> None)."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"1": "1.70", "2": "2.10", "bookmaker_name": "B1", "period": "SecondSet"}]
        )
        extractor.period_selector.select_by_scope = AsyncMock(return_value=None)
        selection_manager_mock.ensure_selected = AsyncMock(return_value=True)

        mock_period = MagicMock()
        mock_period.get_display_label = MagicMock(return_value="2nd Set")
        with patch.object(SportPeriodRegistry, "from_internal_value", return_value=mock_period):
            result = await extractor.extract_market_odds(
                page=page_mock, main_market="Over/Under", odds_labels=["1", "2"], sport="tennis", period="SecondSet"
            )

        selection_manager_mock.ensure_selected.assert_called_once_with(
            page=page_mock,
            target_value="2nd Set",
            display_label="2nd Set",
            strategy=PERIOD_STRATEGY,
        )
        assert result == [
            {"1": "1.70", "2": "2.10", "bookmaker_name": "B1", "period": "SecondSet", "submarket_name": "Over/Under"}
        ]

    async def test_extract_market_odds_period_not_found_skips(self, extractor, page_mock, selection_manager_mock):
        """Test that period selection is skipped when period enum is not found."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(return_value=[])
        extractor.period_selector.select_by_scope = AsyncMock(return_value=True)

        with patch.object(SportPeriodRegistry, "from_internal_value", return_value=None):
            await extractor.extract_market_odds(
                page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], sport="football", period="FullTime"
            )

        selection_manager_mock.ensure_selected.assert_not_called()
        extractor.period_selector.select_by_scope.assert_not_called()

    @pytest.mark.parametrize("scope_result", [None, False])
    async def test_unverified_scope_falls_back_to_label(
        self, extractor, page_mock, selection_manager_mock, scope_result
    ):
        """Both an unknown scope (None) and a failed scope switch (False) try the label tab."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"1": "1.80", "2": "2.00", "bookmaker_name": "B1", "period": "FirstSet"}]
        )
        extractor.period_selector.select_by_scope = AsyncMock(return_value=scope_result)
        selection_manager_mock.ensure_selected = AsyncMock(return_value=True)

        result = await extractor.extract_market_odds(
            page=page_mock, main_market="Home/Away", odds_labels=["1", "2"], sport="tennis", period="FirstSet"
        )

        selection_manager_mock.ensure_selected.assert_awaited_once()
        assert len(result) == 1

    async def test_unverified_non_default_period_returns_no_odds(self, extractor, page_mock, selection_manager_mock):
        """Tennis 1st set not reachable by scope nor label: no odds rather than full-time odds labelled FirstSet."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"1": "1.80", "2": "2.00", "bookmaker_name": "B1", "period": "FirstSet"}]
        )
        extractor.period_selector.select_by_scope = AsyncMock(return_value=False)
        selection_manager_mock.ensure_selected = AsyncMock(return_value=False)

        result = await extractor.extract_market_odds(
            page=page_mock, main_market="Home/Away", odds_labels=["1", "2"], sport="tennis", period="FirstSet"
        )

        assert result == []
        extractor.odds_parser.parse_market_odds.assert_not_called()

    async def test_unverified_default_period_keeps_the_odds(self, extractor, page_mock, selection_manager_mock):
        """Football full time is the page's default: an unverified selection keeps today's behaviour."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"1": "1.90", "X": "3.50", "2": "4.20", "bookmaker_name": "B1", "period": "FullTime"}]
        )
        extractor.period_selector.select_by_scope = AsyncMock(return_value=False)
        selection_manager_mock.ensure_selected = AsyncMock(return_value=False)

        result = await extractor.extract_market_odds(
            page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], sport="football", period="FullTime"
        )

        assert len(result) == 1

    async def test_label_fallback_on_the_default_period_keeps_the_odds(
        self, extractor, page_mock, selection_manager_mock, caplog
    ):
        """A label switch that succeeds on the default period returns the odds, without the unverified warning."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.odds_parser.parse_market_odds = MagicMock(
            return_value=[{"1": "1.90", "X": "3.50", "2": "4.20", "bookmaker_name": "B1", "period": "FullTime"}]
        )
        extractor.period_selector.select_by_scope = AsyncMock(return_value=None)
        selection_manager_mock.ensure_selected = AsyncMock(return_value=True)

        with caplog.at_level("WARNING"):
            result = await extractor.extract_market_odds(
                page=page_mock, main_market="1X2", odds_labels=["1", "X", "2"], sport="football", period="FullTime"
            )

        selection_manager_mock.ensure_selected.assert_awaited_once_with(
            page=page_mock, target_value="Full Time", display_label="Full Time", strategy=PERIOD_STRATEGY
        )
        assert result == [
            {
                "1": "1.90",
                "X": "3.50",
                "2": "4.20",
                "bookmaker_name": "B1",
                "period": "FullTime",
                "submarket_name": "1X2",
            }
        ]
        assert "not verified" not in caplog.text

    async def test_extract_market_odds_preview_mode_passive(self, extractor, page_mock):
        """Test preview mode uses passive submarket extraction."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
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

    async def test_extract_market_odds_preview_mode_fallback_to_active(self, extractor, page_mock):
        """Test preview mode falls back to normal scraping when passive returns no data."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
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

    async def test_extract_market_odds_preview_fallback_specific_market_not_found(self, extractor, page_mock):
        """Test preview fallback returns [] when specific market can't be selected."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
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

    async def test_extract_market_odds_history_skips_filtered_bk(self, extractor, page_mock):
        """Test that odds history is skipped for bookmakers not matching target."""
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
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
            page_mock, "Bookmaker1", 1
        )


def _sub_nav_tab(label: str, active: bool, events: list):
    """A bookies-filter button: a click makes it the selected one."""
    tab = MagicMock()
    state = {"active": active}
    tab.text_content = AsyncMock(return_value=label)
    tab.get_attribute = AsyncMock(side_effect=lambda _name: "font-weight: 700;" if state["active"] else None)

    async def click():
        events.append(f"click {label}")
        state["active"] = True

    tab.click = AsyncMock(side_effect=click)
    return tab


class TestBookiesFilterAfterEachSwitch:
    """Every market or period switch renders the default Classic panel; the requested one is shown before the read."""

    @staticmethod
    def _setup(shown: str | None):
        events: list = []
        extractor = OddsPortalMarketExtractor(
            scroller=AsyncMock(), tab_navigator=AsyncMock(), selection_manager=SelectionManager()
        )
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(
            side_effect=lambda **kwargs: events.append("switch") or True
        )
        labels = ("All Bookies", "Classic Bookies", "Crypto Bookies") if shown else ()
        tabs = {label: _sub_nav_tab(label, label == shown, events) for label in labels}
        page = AsyncMock()
        page.query_selector_all = AsyncMock(return_value=list(tabs.values()))
        page.wait_for_function = AsyncMock(return_value=MagicMock())

        async def content():
            events.append("read")
            return SAMPLE_HTML_ODDS

        page.content = AsyncMock(side_effect=content)
        return extractor, page, tabs, events

    async def test_the_requested_panel_is_clicked_after_the_switch_and_before_the_read(self):
        extractor, page, _tabs, events = self._setup(shown="Classic Bookies")

        result = await extractor.extract_market_odds(
            page=page, main_market="1X2", odds_labels=["1", "X", "2"], bookies_filter=BookiesFilter.ALL
        )

        assert events == ["switch", "click All Bookies", "read"]
        assert len(result) == 2

    async def test_a_panel_already_shown_is_not_clicked(self):
        extractor, page, tabs, events = self._setup(shown="Crypto Bookies")

        await extractor.extract_market_odds(
            page=page, main_market="1X2", odds_labels=["1", "X", "2"], bookies_filter=BookiesFilter.CRYPTO
        )

        assert events == ["switch", "read"]
        assert not any(tab.click.await_count for tab in tabs.values())

    async def test_a_panel_that_cannot_be_shown_warns_and_the_market_is_read_as_shown(self, caplog):
        extractor, page, _tabs, events = self._setup(shown=None)

        with caplog.at_level("WARNING"):
            result = await extractor.extract_market_odds(
                page=page, main_market="1X2", odds_labels=["1", "X", "2"], bookies_filter=BookiesFilter.ALL
            )

        assert "bookies-filter navigation not found on page" in caplog.text
        assert events == ["switch", "read"]
        assert len(result) == 2

    async def test_the_panel_is_shown_after_the_period_switch(self):
        extractor, page, _tabs, events = self._setup(shown="Classic Bookies")
        extractor._select_period = AsyncMock(side_effect=lambda *args: events.append("period") or True)

        await extractor.extract_market_odds(
            page=page,
            main_market="1X2",
            period="FirstHalf",
            odds_labels=["1", "X", "2"],
            sport="football",
            bookies_filter=BookiesFilter.ALL,
        )

        assert events == ["switch", "period", "click All Bookies", "read"]

    async def test_no_requested_panel_leaves_the_shown_one(self):
        extractor, page, _tabs, events = self._setup(shown="Classic Bookies")

        await extractor.extract_market_odds(page=page, main_market="1X2", odds_labels=["1", "X", "2"])

        assert events == ["switch", "read"]
        page.query_selector_all.assert_not_awaited()

    async def test_umbrella_lines_are_read_with_the_requested_panel(self):
        extractor, page, _tabs, events = self._setup(shown="Classic Bookies")

        await extractor._discover_line_names(
            page=page, main_market="Over/Under", period="FullTime", bookies_filter=BookiesFilter.ALL
        )

        assert events == ["switch", "click All Bookies", "read"]


class TestAMarketWithoutItsData:
    """A market whose data OddsPortal did not deliver fails the match: the table still shows the previous market."""

    @pytest.fixture
    def extractor(self):
        return OddsPortalMarketExtractor(scroller=AsyncMock(), tab_navigator=AsyncMock(), selection_manager=AsyncMock())

    @pytest.fixture
    def page_mock(self):
        mock = AsyncMock()
        mock.content = AsyncMock(return_value=SAMPLE_HTML_ODDS)
        return mock

    async def test_the_market_switch_raises_instead_of_reading_the_previous_table(self, extractor, page_mock):
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(side_effect=MarketDataError("no data"))

        with pytest.raises(MarketDataError):
            await extractor.extract_market_odds(
                page=page_mock, main_market="Both Teams to Score", odds_labels=["y", "n"]
            )

        page_mock.content.assert_not_awaited()

    async def test_the_period_switch_raises_instead_of_reading_the_previous_table(self, extractor, page_mock):
        extractor.navigation_manager.navigate_to_market_tab = AsyncMock(return_value=True)
        extractor.period_selector.select_by_scope = AsyncMock(side_effect=MarketDataError("no data"))

        with pytest.raises(MarketDataError):
            await extractor.extract_market_odds(
                page=page_mock, main_market="1X2", period="FirstHalf", odds_labels=["1", "X", "2"], sport="football"
            )

        page_mock.content.assert_not_awaited()

    async def test_the_next_markets_are_not_read_once_one_lost_its_data(self, extractor, page_mock):
        extractor.extract_market_odds = AsyncMock(side_effect=[[{"bookmaker_name": "B1"}], MarketDataError("no data")])

        double_chance = MarketSpec("Double Chance", odds_labels=("1X", "12", "X2"))
        mapping = {"1x2": ONE_X_TWO, "btts": BTTS, "double_chance": double_chance}

        with patch.object(SportMarketRegistry, "get_market_mapping", return_value=mapping):
            with pytest.raises(MarketDataError):
                await extractor.scrape_markets(
                    page=page_mock, sport="football", markets=["1x2", "btts", "double_chance"]
                )

        assert extractor.extract_market_odds.await_count == 2

    async def test_an_umbrella_whose_lines_lost_their_data_raises(self, extractor, page_mock):
        extractor.extract_market_odds = AsyncMock(return_value=[{"bookmaker_name": "B1"}])
        extractor._discover_line_names = AsyncMock(side_effect=MarketDataError("no data"))

        with patch.object(SportMarketRegistry, "get_market_mapping", return_value={"1x2": ONE_X_TWO}):
            with pytest.raises(MarketDataError):
                await extractor.scrape_markets(page=page_mock, sport="football", markets=["over_under", "1x2"])

        extractor.extract_market_odds.assert_not_awaited()

    async def test_a_preview_group_that_lost_its_data_raises(self, extractor, page_mock):
        extractor.extract_market_odds = AsyncMock(side_effect=MarketDataError("no data"))
        markets = {"over_under_2_5": over_under("2.5"), "over_under_3_5": over_under("3.5")}

        with patch.object(SportMarketRegistry, "get_market_mapping", return_value=markets):
            with pytest.raises(MarketDataError):
                await extractor.scrape_markets(
                    page=page_mock,
                    sport="football",
                    markets=["over_under_2_5", "over_under_3_5"],
                    preview_submarkets_only=True,
                )
