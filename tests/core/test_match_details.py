from datetime import datetime
import logging
from unittest.mock import patch

from bs4 import BeautifulSoup
import pytest
from tests.clock import SUMMER_NOW, WINTER_NOW, page_clock
from tests.dom_builders import live_block, match_header, page

from oddsharvester.core.match_details import (
    _history_reference,
    _parse_league_from_dom,
    _parse_live_info,
    _parse_match_date_from_dom,
    _parse_results_from_dom,
    _parse_teams_from_dom,
)

SCRAPER_LOGGER = logging.getLogger("BaseScraper")


def _make_date_html(date_str: str = "06 Aug 2022,", time_str: str = "11:30") -> str:
    return match_header(weekday="Saturday,", date=date_str, time=time_str)


def test_parse_match_date_from_dom_parses_utc_nominal():
    soup = BeautifulSoup(_make_date_html(), "html.parser")
    assert _parse_match_date_from_dom(soup, "UTC", {}, SCRAPER_LOGGER) == "2022-08-06 11:30:00 UTC"


def test_parse_match_date_from_dom_converts_local_tz_to_utc():
    # Scraped in summer, Brussels shows every time at UTC+2, so 13:30 Brussels = 11:30 UTC
    soup = BeautifulSoup(_make_date_html(time_str="13:30"), "html.parser")
    with page_clock(SUMMER_NOW):
        assert _parse_match_date_from_dom(soup, "Europe/Brussels", {}, SCRAPER_LOGGER) == "2022-08-06 11:30:00 UTC"


def test_parse_match_date_from_dom_reads_a_january_date_at_the_summer_page_offset():
    """Djokovic - Sinner, 26 Jan 2024 at 03:45 UTC, shows 04:45 when scraped in BST (gotchas §10)."""
    soup = BeautifulSoup(_make_date_html(date_str="26 Jan 2024,", time_str="04:45"), "html.parser")
    with page_clock(SUMMER_NOW):
        assert _parse_match_date_from_dom(soup, "Europe/London", {}, SCRAPER_LOGGER) == "2024-01-26 03:45:00 UTC"


def test_parse_match_date_from_dom_reads_a_july_date_at_the_winter_page_offset():
    soup = BeautifulSoup(_make_date_html(date_str="04 Jul 2026,", time_str="19:00"), "html.parser")
    with page_clock(WINTER_NOW):
        assert _parse_match_date_from_dom(soup, "Europe/London", {}, SCRAPER_LOGGER) == "2026-07-04 19:00:00 UTC"


@pytest.mark.parametrize("now", [SUMMER_NOW, WINTER_NOW])
def test_parse_match_date_from_dom_in_utc_does_not_depend_on_the_season(now):
    soup = BeautifulSoup(_make_date_html(date_str="26 Jan 2024,", time_str="03:45"), "html.parser")
    with page_clock(now):
        assert _parse_match_date_from_dom(soup, "UTC", {}, SCRAPER_LOGGER) == "2024-01-26 03:45:00 UTC"


def test_parse_match_date_from_dom_returns_none_when_div_missing():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert _parse_match_date_from_dom(soup, None, {}, SCRAPER_LOGGER) is None


def test_parse_match_date_from_dom_returns_none_on_unparseable_text(caplog):
    soup = BeautifulSoup(_make_date_html(date_str="32 Aug 2022,", time_str="??:??"), "html.parser")
    with caplog.at_level(logging.WARNING):
        result = _parse_match_date_from_dom(soup, "UTC", {}, SCRAPER_LOGGER)
    assert result is None
    assert any("DOM parse failed for match_date" in rec.message for rec in caplog.records)


def _make_teams_html(home: str | None = "Fulham", away: str | None = "Liverpool") -> str:
    return match_header(home=home if home is not None else "", away=away if away is not None else "")


def test_parse_teams_from_dom_returns_both_when_present():
    soup = BeautifulSoup(_make_teams_html(), "html.parser")
    assert _parse_teams_from_dom(soup, SCRAPER_LOGGER) == ("Fulham", "Liverpool")


def test_parse_teams_from_dom_returns_none_pair_when_home_missing():
    soup = BeautifulSoup(_make_teams_html(home=None), "html.parser")
    assert _parse_teams_from_dom(soup, SCRAPER_LOGGER) == (None, None)


def test_parse_teams_from_dom_returns_none_pair_when_away_missing():
    soup = BeautifulSoup(_make_teams_html(away=None), "html.parser")
    assert _parse_teams_from_dom(soup, SCRAPER_LOGGER) == (None, None)


def test_parse_teams_from_dom_returns_none_pair_when_both_missing():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert _parse_teams_from_dom(soup, SCRAPER_LOGGER) == (None, None)


def _make_league_html(text: str | None = "Premier League 2024/2025", with_link: bool = True) -> str:
    if not with_link:
        return page("<ul></ul>")
    return match_header(
        breadcrumb=(
            ("/", "Home"),
            ("/football/", "Football"),
            ("/football/england/", "England"),
            (f"/football/england/{text}/", text),
        )
    )


def test_parse_league_from_dom_strips_season_suffix():
    soup = BeautifulSoup(_make_league_html("Premier League 2024/2025"), "html.parser")
    assert _parse_league_from_dom(soup, SCRAPER_LOGGER) == "Premier League"


def test_parse_league_from_dom_keeps_name_without_suffix():
    soup = BeautifulSoup(_make_league_html("LaLiga"), "html.parser")
    assert _parse_league_from_dom(soup, SCRAPER_LOGGER) == "LaLiga"


def test_parse_league_from_dom_handles_multiple_spaces_before_suffix():
    soup = BeautifulSoup(_make_league_html("LaLiga  2019/2020"), "html.parser")
    assert _parse_league_from_dom(soup, SCRAPER_LOGGER) == "LaLiga"


def test_parse_league_from_dom_returns_none_when_link_missing():
    soup = BeautifulSoup(_make_league_html(with_link=False), "html.parser")
    assert _parse_league_from_dom(soup, SCRAPER_LOGGER) is None


def test_parse_league_from_dom_returns_none_when_breadcrumb_missing():
    soup = BeautifulSoup("<html><body></body></html>", "html.parser")
    assert _parse_league_from_dom(soup, SCRAPER_LOGGER) is None


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


def test_parse_results_from_dom_extracts_score_and_partial():
    soup = BeautifulSoup(_make_results_html(), "html.parser")
    home, away, partial = _parse_results_from_dom(soup, SCRAPER_LOGGER)
    assert home == "2"
    assert away == "1"
    assert partial == "(1:0, 1:1)"


def test_parse_results_from_dom_extracts_score_without_partial():
    soup = BeautifulSoup(_make_results_html(score_text="Final result 4:0"), "html.parser")
    home, away, partial = _parse_results_from_dom(soup, SCRAPER_LOGGER)
    assert home == "4"
    assert away == "0"
    assert partial is None


def test_parse_results_from_dom_returns_none_when_pattern_absent():
    soup = BeautifulSoup('<html><body><div data-testid="game-time-item"></div></body></html>', "html.parser")
    assert _parse_results_from_dom(soup, SCRAPER_LOGGER) == (None, None, None)


def test_parse_results_from_dom_returns_none_when_game_time_div_missing():
    soup = BeautifulSoup("<html><body><div>Final result 2:1 (1:0, 1:1)</div></body></html>", "html.parser")
    assert _parse_results_from_dom(soup, SCRAPER_LOGGER) == (None, None, None)


def test_parse_results_from_dom_normalizes_nbsp_in_partial():
    # OddsPortal renders non-breaking spaces (\xa0) between partial-result tokens.
    soup = BeautifulSoup(_make_results_html("Final result 2:1 (1:0,\xa01:1)"), "html.parser")
    home, away, partial = _parse_results_from_dom(soup, SCRAPER_LOGGER)
    assert home == "2"
    assert away == "1"
    assert partial == "(1:0, 1:1)"


def test_parse_results_from_dom_logs_and_returns_none_on_an_unexpected_error(caplog):
    soup = BeautifulSoup(_make_results_html(), "html.parser")

    with (
        patch("oddsharvester.core.match_details.OddsPortalSelectors.match_date_cell", side_effect=RuntimeError("boom")),
        caplog.at_level(logging.WARNING),
    ):
        assert _parse_results_from_dom(soup, SCRAPER_LOGGER) == (None, None, None)

    assert "DOM parse failed for results: boom" in caplog.text


# -- parse live info -------------------------------------------------------

LIVE_INFO_TENNIS_HTML = page(live_block("2nd Set", "1:0", partial="6:4, 0:0"))

LIVE_INFO_FOOTBALL_STYLE_HTML = page(live_block("65'", "2:1"))


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
        result = _parse_live_info(self._soup(page(live_block("HT", "2\u20131"))))
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
        html = page(live_block("4'", "1:0", partial="1:0"))
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
        html = page(live_block("Final\u00a0result", "0:2"))
        assert _parse_live_info(self._soup(html)) is None

    def test_returns_none_for_finished_match_single_chunk(self):
        """2026-08 redesign: the persistent live-info can serve the whole terminal
        text as one chunk ("Final result 1:2 (0:1, 1:1)")."""
        html = page('<div><p class="result-live"></p>Final result 1:2 (0:1, 1:1)</div>')
        assert _parse_live_info(self._soup(html)) is None

    def test_normalizes_non_breaking_space_in_period(self):
        html = page(live_block("1st\u00a0Set", "0:0"))
        assert _parse_live_info(self._soup(html))["live_period"] == "1st Set"

    def test_missing_score_yields_none_ints_and_keeps_period(self):
        result = _parse_live_info(self._soup(page('<div><p class="result-live"></p><div>HT</div></div>')))
        assert result == {
            "live_period": "HT",
            "live_score_home": None,
            "live_score_away": None,
            "live_score_raw": None,
        }


def test_parse_match_date_from_dom_uses_browser_month_aliases():
    """DOM match dates must support month names supplied by the browser locale."""
    month_names = {
        "localized-month-09": 9,
    }

    soup = BeautifulSoup(
        _make_date_html(
            date_str="16 localized-month-09 2026,",
            time_str="18:45",
        ),
        "html.parser",
    )

    assert _parse_match_date_from_dom(soup, "UTC", month_names, SCRAPER_LOGGER) == "2026-09-16 18:45:00 UTC"


def test_history_reference_converts_kickoff_to_the_browser_timezone():
    assert _history_reference("2026-06-04 18:30:00 UTC", "Europe/London") == datetime(2026, 6, 4, 19, 30)


def test_history_reference_crosses_new_year_in_the_browser_timezone():
    assert _history_reference("2025-12-31 23:30:00 UTC", "Asia/Tokyo") == datetime(2026, 1, 1, 8, 30)


def test_history_reference_follows_the_london_clock_changes():
    """Kickoffs on the two 2026 Europe/London clock-change days, either side of the switch."""
    assert _history_reference("2026-03-29 00:30:00 UTC", "Europe/London") == datetime(2026, 3, 29, 0, 30)
    assert _history_reference("2026-03-29 14:00:00 UTC", "Europe/London") == datetime(2026, 3, 29, 15, 0)
    assert _history_reference("2026-10-25 00:30:00 UTC", "Europe/London") == datetime(2026, 10, 25, 1, 30)
    assert _history_reference("2026-10-25 14:00:00 UTC", "Europe/London") == datetime(2026, 10, 25, 14, 0)


def test_history_reference_defaults_to_utc():
    assert _history_reference("2026-01-04 18:30:00 UTC", None) == datetime(2026, 1, 4, 18, 30)
    assert _history_reference("2026-01-04 18:30:00 UTC", "Not/AZone") == datetime(2026, 1, 4, 18, 30)


def test_history_reference_is_none_without_a_usable_match_date():
    assert _history_reference(None, "UTC") is None
    assert _history_reference("not a date", "UTC") is None
