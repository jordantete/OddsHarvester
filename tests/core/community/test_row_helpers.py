from datetime import UTC, datetime
from unittest.mock import patch

from bs4 import BeautifulSoup
import pytest
from tests.clock import frozen_clock
from tests.dom_builders import community_row

from oddsharvester.core.community.row_helpers import extract_datetime_and_market, to_float, to_pct


def test_to_float_parses_valid_and_rejects_garbage():
    assert to_float("2.05") == 2.05
    assert to_float("-") is None


def test_to_pct_extracts_integer_percent():
    assert to_pct("87%") == 87
    assert to_pct("no pct") == 0


def test_extract_datetime_handles_duplicated_responsive_date():
    """Redesign rows render the date twice (mobile + desktop variants):
    '20/Jun 12:10 20/Jun, 12:10 CS' must still yield a kickoff."""
    from bs4 import BeautifulSoup

    from oddsharvester.core.community.row_helpers import extract_datetime_and_market

    html = """
    <div data-testid="game-row">
      <div data-testid="date-time-item"><p>20/Jun</p><p>12:10</p><p>20/Jun, 12:10</p><p>CS</p></div>
    </div>
    """
    row = BeautifulSoup(html, "lxml").find(attrs={"data-testid": "game-row"})
    _kickoff_text, kickoff, market = extract_datetime_and_market(row, "UTC")
    assert market == "CS"
    assert kickoff is not None
    assert kickoff.endswith("T12:10")
    assert "-06-20" in kickoff


SUMMER_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
WINTER_NOW = datetime(2027, 1, 15, 12, 0, tzinfo=UTC)


def _kickoff(date: str, time: str, tz_name: str, now: datetime) -> tuple[str, str | None]:
    """kickoff_text and kickoff of one row, with the clock frozen for the year rule and for the page offset."""
    row = BeautifulSoup(community_row("/football/h2h/a/b/#x", "", date=date, time=time), "lxml").find("a")
    clock = frozen_clock(now)
    with (
        patch("oddsharvester.core.base_scraper.datetime", clock),
        patch("oddsharvester.utils.page_time.datetime", clock),
    ):
        kickoff_text, kickoff, _market = extract_datetime_and_market(row, tz_name)
    return kickoff_text, kickoff


def test_a_january_kickoff_shown_in_summer_is_read_one_hour_earlier():
    """Scraped in BST, a 17:30 GMT kickoff shows 18:30; kickoff_text keeps what the page shows."""
    assert _kickoff("10/Jan", "18:30", "Europe/London", SUMMER_NOW) == (
        "10/Jan 18:30 10/Jan, 18:30 1X2",
        "2027-01-10T17:30",
    )


def test_a_july_kickoff_shown_in_winter_is_read_one_hour_later():
    assert _kickoff("04/Jul", "18:00", "Europe/London", WINTER_NOW)[1] == "2027-07-04T19:00"


@pytest.mark.parametrize("now", [SUMMER_NOW, WINTER_NOW])
def test_a_utc_kickoff_is_read_as_shown(now):
    assert _kickoff("10/Jan", "18:30", "UTC", now)[1] == "2027-01-10T18:30"


def test_a_kickoff_shown_just_after_midnight_on_new_year_moves_back_a_year():
    """Shown 00:30 on 1 January in BST is 23:30 GMT on 31 December."""
    assert _kickoff("01/Jan", "00:30", "Europe/London", SUMMER_NOW)[1] == "2026-12-31T23:30"


@pytest.mark.parametrize(("label", "kickoff"), [("Tomorr.", "2026-10-01T18:45"), ("Yest.", "2026-09-29T18:45")])
def test_an_abbreviated_relative_day_is_read(label, kickoff):
    """Rows of the day before and after the page is read say "Yest." and "Tomorr." (gotchas §10)."""
    assert _kickoff(label, "18:45", "UTC", SUMMER_NOW) == (f"{label} 18:45 {label}, 18:45 1X2", kickoff)
