from unittest.mock import MagicMock, patch

import pytest

from oddsharvester.core.market_extraction.odds_parser import OddsParser, parse_odds_value


class TestOddsParser:
    """Unit tests for the OddsParser class."""

    @pytest.fixture
    def odds_parser(self):
        """Create an instance of OddsParser."""
        return OddsParser()

    # Table-based odds markup (2026-08 redesign). One leaf <tr> per bookmaker;
    # odds cells carry data-testid='odd-container*'.
    @staticmethod
    def _bm_row(name="Bookmaker1", odds=("1.90", "3.50", "4.20"), name_via="testid", blocked=()):
        if name_via == "testid":
            name_html = f'<a data-testid="outrights-expanded-bookmaker-name">{name}</a>'
        elif name_via == "a_title":
            name_html = f'<a title="{name}"><img src="logo.png"></a>'
        elif name_via == "img_alt":
            name_html = f'<img alt="{name}" src="logo.png">'
        else:
            name_html = ""
        cells = "".join(
            f'<td><div data-testid="odd-container">'
            f"{'<span class=' + chr(34) + 'line-through' + chr(34) + '>' + o + '</span>' if i in blocked else o}"
            f"</div></td>"
            for i, o in enumerate(odds)
        )
        return (
            f'<tr class="h-9 cursor-pointer"><td>'
            f'<div data-testid="outrights-expanded-bookmaker-logo"><img data-testid="bookie-logo" src="x.png"></div>'
            f"{name_html}"
            f'<div data-testid="outrights-expanded-bonus-icon">claim bonus</div></td>'
            f'{cells}<td><div data-testid="payout-container">94.1%</div></td></tr>'
        )

    @classmethod
    def _table(cls, rows, extra_rows=""):
        return (
            "<table><thead><tr><th>Bookmakers</th><th>1</th><th>X</th><th>2</th><th>Payout</th></tr></thead>"
            f"<tbody>{''.join(rows)}{extra_rows}</tbody></table>"
        )

    @property
    def SAMPLE_HTML_ODDS(self):  # noqa: N802 - keeps the historical fixture name
        return self._table(
            [
                self._bm_row("Bookmaker1", ("1.90", "3.50", "4.20")),
                self._bm_row("Bookmaker2", ("1.85", "3.60", "4.10")),
            ]
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

    def test_parse_market_odds_success(self, odds_parser):
        """Test successful parsing of market odds."""
        # Arrange
        odds_labels = ["1", "X", "2"]

        # Act
        result = odds_parser.parse_market_odds(self.SAMPLE_HTML_ODDS, "FullTime", odds_labels)

        # Assert
        assert len(result) == 2
        assert result[0]["bookmaker_name"] == "Bookmaker1"
        assert result[0]["1"] == "1.90"
        assert result[0]["X"] == "3.50"
        assert result[0]["2"] == "4.20"
        assert result[0]["period"] == "FullTime"
        assert result[1]["bookmaker_name"] == "Bookmaker2"

    def test_parse_market_odds_with_target_bookmaker(self, odds_parser):
        """Test parsing odds with a specific target bookmaker."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        target_bookmaker = "Bookmaker1"

        # Act
        result = odds_parser.parse_market_odds(self.SAMPLE_HTML_ODDS, "FullTime", odds_labels, target_bookmaker)

        # Assert
        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"
        assert result[0]["1"] == "1.90"
        assert result[0]["X"] == "3.50"
        assert result[0]["2"] == "4.20"

    def test_parse_market_odds_no_bookmakers(self, odds_parser):
        """Test parsing odds when no bookmakers are found."""
        # Arrange
        odds_labels = ["1", "X", "2"]
        empty_html = "<div>No bookmakers found</div>"

        # Act
        result = odds_parser.parse_market_odds(empty_html, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0

    def test_parse_market_odds_missing_data(self, odds_parser):
        """Test parsing odds when a bookmaker has incomplete data."""
        # Arrange
        odds_labels = ["1", "X", "2", "Extras"]

        # Act
        result = odds_parser.parse_market_odds(self.SAMPLE_HTML_ODDS, "FullTime", odds_labels)

        # Assert
        assert len(result) == 0

    def test_parse_market_odds_error_handling(self, odds_parser):
        """A bookmaker row with no odds cells at all is not a bookmaker row."""
        odds_labels = ["1", "X", "2"]
        broken_html = self._table(
            ['<tr><td><a data-testid="outrights-expanded-bookmaker-name">Bookmaker1</a></td></tr>']
        )

        result = odds_parser.parse_market_odds(broken_html, "FullTime", odds_labels)

        assert len(result) == 0

    def test_parse_market_odds_duplicate_odds_removal(self, odds_parser):
        """Doubled odds strings ('1.901.90') are collapsed to a single value."""
        html = self._table([self._bm_row("Bookmaker1", ("1.901.90", "3.50"))])

        result = odds_parser.parse_market_odds(html, "FullTime", ["1", "X"])

        assert len(result) == 1
        assert result[0]["1"] == "1.90"

    def test_parse_market_odds_skips_nested_wrapper_rows(self, odds_parser):
        """An expanded submarket <tr> wraps a nested table; only leaf rows count."""
        inner = self._table([self._bm_row("Bookmaker1", ("1.90", "3.50", "4.20"))])
        html = f"<table><tbody><tr><td>{inner}</td></tr></tbody></table>"

        result = odds_parser.parse_market_odds(html, "FullTime", ["1", "X", "2"])

        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Bookmaker1"

    def test_parse_odds_history_modal_success(self, odds_parser):
        """Test successful parsing of odds history modal."""
        # Arrange
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: __import__("datetime").datetime.strptime(
                *args, **kwargs
            )

            # Act
            result = odds_parser.parse_odds_history_modal(self.SAMPLE_HTML_ODDS_HISTORY)

            # Assert
            assert "odds_history" in result
            assert len(result["odds_history"]) == 2
            assert result["odds_history"][0]["odds"] == 1.95
            assert result["odds_history"][1]["odds"] == 1.90
            assert "opening_odds" in result

    def test_parse_odds_history_modal_invalid_html(self, odds_parser):
        """Test parsing odds history from invalid HTML."""
        # Arrange
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: __import__("datetime").datetime.strptime(
                *args, **kwargs
            )

            # Act
            invalid_html = "<div>Invalid HTML content</div>"
            result = odds_parser.parse_odds_history_modal(invalid_html)

            # Assert
            assert result == {}

    def test_parse_odds_history_modal_invalid_date(self, odds_parser):
        """Test parsing odds history with invalid date format."""
        # Arrange
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            # Force ValueError on strptime
            mock_datetime.strptime.side_effect = ValueError("Invalid date format")

            # Act
            result = odds_parser.parse_odds_history_modal(self.SAMPLE_HTML_ODDS_HISTORY)

            # Assert
            assert "odds_history" in result
            assert len(result["odds_history"]) == 0

    def test_parse_odds_history_modal_fractional_odds(self, odds_parser):
        """Test parsing odds history when bookmaker returns fractional odds."""
        fractional_html = """
        <div class="flex w-max flex-col gap-2">
            <h3 class="text-sm font-semibold uppercase leading-6">Odds movement</h3>
            <div class="flex flex-row gap-3">
                <div class="flex flex-col gap-1">
                    <div class="text-[10px] font-normal">10 Jun, 14:30</div>
                    <div class="text-[10px] font-normal">10 Jun, 12:00</div>
                </div>
                <div class="flex flex-col gap-1">
                    <div class="text-[10px] font-bold">4/5</div>
                    <div class="text-[10px] font-bold">21/20</div>
                </div>
                <div class="flex flex-col gap-1">
                    <div class="text-[10px] font-bold text-green-dark">-0.11</div>
                </div>
            </div>
            <div class="mt-2 gap-1">
                <div class="text-[10px] font-bold">Opening odds:</div>
                <div class="flex gap-1"><div class="font-normal">10 Jun, 08:00</div>
                <div class="font-bold">9/2</div></div>
            </div>
        </div>
        """
        with patch("oddsharvester.core.market_extraction.odds_parser.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.year = 2025
            mock_datetime.now.return_value = mock_now
            mock_datetime.strptime.side_effect = lambda *args, **kwargs: __import__("datetime").datetime.strptime(
                *args, **kwargs
            )

            result = odds_parser.parse_odds_history_modal(fractional_html)

            assert "odds_history" in result
            assert len(result["odds_history"]) == 2
            assert result["odds_history"][0]["odds"] == pytest.approx(1.8)  # 4/5 + 1
            assert result["odds_history"][1]["odds"] == pytest.approx(2.05)  # 21/20 + 1
            assert result["opening_odds"]["odds"] == pytest.approx(5.5)  # 9/2 + 1

    def test_parse_market_odds_bookmaker_name_fallback_a_tag(self, odds_parser):
        """Name resolution falls back to <a title> when the name testid is absent."""
        html = self._table([self._bm_row("Betfred", ("1.90", "2.10"), name_via="a_title")])

        result = odds_parser.parse_market_odds(html, "FullTime", ["home", "away"])

        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Betfred"

    def test_parse_market_odds_bookmaker_name_cta_normalised(self, odds_parser):
        """CTA-style <a title> values are normalised to clean bookmaker names."""
        html = self._table([self._bm_row("Go to Betfair Exchange website!", ("1.90", "2.10"), name_via="a_title")])

        result = odds_parser.parse_market_odds(html, "FullTime", ["home", "away"])

        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Betfair Exchange"

    def test_parse_market_odds_bookmaker_name_fallback_img_alt(self, odds_parser):
        """Name resolution falls back to img[alt] as last resort."""
        html = self._table([self._bm_row("BetVictor", ("1.90", "2.10"), name_via="img_alt")])

        result = odds_parser.parse_market_odds(html, "FullTime", ["home", "away"])

        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "BetVictor"

    def test_parse_market_odds_no_bookmaker_name_skips_row(self, odds_parser):
        """Collapsed submarket line rows carry odd-container-default cells and must
        never be parsed as bookmakers, even when a decorative <img alt="arrow">
        would resolve a name through the fallback chain (live regression)."""
        html = self._table(
            [
                '<tr class="h-9 cursor-pointer"><td><span class="max-sm:hidden">Over/Under +2.5</span>'
                '<img alt="arrow" src="arrow.svg"></td>'
                '<td><div data-testid="odd-container-default">1.68</div></td>'
                '<td><div data-testid="odd-container-default">1.98</div></td>'
                "<td>89.2%</td></tr>"
            ]
        )

        result = odds_parser.parse_market_odds(html, "FullTime", ["odds_over", "odds_under"])

        assert len(result) == 0

    def test_parse_market_odds_skips_peripheral_and_exchange_rows(self, odds_parser):
        """My coupon / User Predictions / OddsAlert rows and the Betting Exchanges
        table (Back/Lay prices) must not be parsed as bookmaker odds."""
        coupon = (
            '<tr><td>My coupon</td><td><div data-testid="my-coupon-row">'
            '<div data-testid="odd-container">+</div></div></td></tr>'
        )
        predictions = (
            '<tr data-testid="user-predictions-row"><td>User Predictions</td>'
            '<td><div data-testid="odd-container">0%</div></td></tr>'
        )
        exchanges = (
            '<div data-testid="betting-exchanges-section"><table><tbody>'
            + self._bm_row("bwin.fr", ("1.68", "1.95"))
            + "</tbody></table></div>"
        )
        html = self._table([self._bm_row("Betclic.fr", ("1.10", "14.00", "7.05"))], extra_rows=coupon + predictions)
        html += exchanges

        result = odds_parser.parse_market_odds(html, "FullTime", ["1", "X", "2"])

        assert [r["bookmaker_name"] for r in result] == ["Betclic.fr"]

    def test_parse_market_odds_flags_fully_blocked_row(self, odds_parser):
        """A row whose every odds cell is struck through reports all labels and keeps its values."""
        html = self._table([self._bm_row("Betclic.fr", ("1.60", "3.30", "4.75"), blocked=(0, 1, 2))])

        result = odds_parser.parse_market_odds(html, "FullTime", ["1", "X", "2"])

        assert len(result) == 1
        assert result[0]["bookmaker_name"] == "Betclic.fr"
        assert result[0]["blocked_outcomes"] == ["1", "X", "2"]
        # A struck-through price is still the last price the bookmaker showed.
        assert result[0]["1"] == "1.60"
        assert result[0]["X"] == "3.30"
        assert result[0]["2"] == "4.75"

    def test_parse_market_odds_flags_partially_blocked_row(self, odds_parser):
        """Only the struck-through outcome is reported, in odds_labels order."""
        html = self._table([self._bm_row("Winamax", ("1.44", "4.10", "5.00"), blocked=(1,))])

        result = odds_parser.parse_market_odds(html, "FullTime", ["1", "X", "2"])

        assert len(result) == 1
        assert result[0]["blocked_outcomes"] == ["X"]
        assert result[0]["1"] == "1.44"
        assert result[0]["X"] == "4.10"
        assert result[0]["2"] == "5.00"

    def test_parse_market_odds_flags_blocked_odds_link_variant(self, odds_parser):
        """The line-through class must be detected on <a> odds links too."""
        row = (
            '<tr><td><a data-testid="outrights-expanded-bookmaker-name">Bet365</a></td>'
            '<td><div data-testid="odd-container"><a class="odds-link underline line-through" '
            'href="https://example.test/betslip">1.85</a></div></td>'
            '<td><div data-testid="odd-container">3.40</div></td></tr>'
        )
        html = self._table([row])

        result = odds_parser.parse_market_odds(html, "FullTime", ["1", "X"])

        assert len(result) == 1
        assert result[0]["blocked_outcomes"] == ["1"]
        assert result[0]["1"] == "1.85"
        assert result[0]["X"] == "3.40"

    def test_parse_market_odds_omits_key_when_nothing_blocked(self, odds_parser):
        """Output for the nominal case is unchanged: no blocked_outcomes key at all."""
        result = odds_parser.parse_market_odds(self.SAMPLE_HTML_ODDS, "FullTime", ["1", "X", "2"])

        assert len(result) == 2
        assert "blocked_outcomes" not in result[0]
        assert "blocked_outcomes" not in result[1]

    def test_parse_market_odds_does_not_flag_bookmaker_without_odds(self, odds_parser):
        """A bookmaker with no price renders '-' with no line-through class:
        'no odds' and 'blocked' must stay distinguishable."""
        html = self._table([self._bm_row("Bets.io", ("-", "-"))])

        result = odds_parser.parse_market_odds(html, "FullTime", ["home", "away"])

        assert len(result) == 1
        assert "blocked_outcomes" not in result[0]
        assert result[0]["home"] == "-"

    def test_logger_initialization(self, odds_parser):
        """Test that logger is properly initialized."""
        assert odds_parser.logger is not None
        assert odds_parser.logger.name == "OddsParser"


class TestParseOddsValue:
    """Unit tests for the parse_odds_value helper."""

    def test_decimal_passthrough(self):
        assert parse_odds_value("1.90") == 1.90

    def test_fractional_simple(self):
        assert parse_odds_value("4/5") == pytest.approx(1.8)

    def test_fractional_evens(self):
        assert parse_odds_value("1/1") == pytest.approx(2.0)

    def test_fractional_long_odds(self):
        assert parse_odds_value("9/2") == pytest.approx(5.5)

    def test_fractional_short_odds(self):
        assert parse_odds_value("1/5") == pytest.approx(1.2)

    def test_fractional_large_denominator(self):
        assert parse_odds_value("87/100") == pytest.approx(1.87)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_odds_value("abc")
