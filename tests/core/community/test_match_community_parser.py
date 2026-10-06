from datetime import datetime
import logging
from unittest.mock import patch

import pytest
from tests.clock import SUMMER_NOW, WINTER_NOW, frozen_clock
from tests.dom_builders import live_block, match_view

from oddsharvester.core.community.match_community_parser import parse_match_community_dom

_PREMATCH_HTML = match_view(
    home="Fulham",
    away="Chelsea",
    weekday="Today,",
    date="24 Aug 2026,",
    votes=["5%", "11%", "84%"],
)


def test_prematch_vote_percentages_parsed():
    rec = parse_match_community_dom(
        _PREMATCH_HTML, "https://www.oddsportal.com/football/h2h/x/y/#C2Nfvg77", event_id="C2Nfvg77"
    )
    assert rec["mode"] == "match"
    assert rec["event_id"] == "C2Nfvg77"
    assert rec["home_team"] == "Fulham"
    assert rec["away_team"] == "Chelsea"
    assert rec["kickoff"] == "Monday, 24 Aug 2026, 21:00"
    assert rec["is_prematch"] is True
    assert rec["markets"] == [
        {
            "market": "1X2",
            "scope": "Full Time",
            "outcomes": [
                {"outcome": "1", "votes_pct": 5},
                {"outcome": "X", "votes_pct": 11},
                {"outcome": "2", "votes_pct": 84},
            ],
        }
    ]


def test_started_match_detected_via_score():
    html = match_view(
        home="Fulham",
        away="Chelsea",
        home_score="1",
        away_score="0",
        votes=["5%", "11%", "84%"],
    )

    assert parse_match_community_dom(html, "url")["is_prematch"] is False


def test_live_match_detected_via_live_block():
    html = match_view(
        home="Fulham",
        away="Chelsea",
        date_row_extra=live_block("2nd Half", "1:2", partial="0:1, 1:1"),
        votes=["5%", "11%", "84%"],
    )

    assert parse_match_community_dom(html, "url")["is_prematch"] is False


def test_non_hydrated_page_yields_no_markets():
    rec = parse_match_community_dom("<html><body><h1>X - Y</h1></body></html>", "url")
    assert rec["markets"] == []
    assert rec["home_team"] is None


def _kickoff(weekday: str, date: str, time: str, tz_name: str | None, now: datetime = SUMMER_NOW) -> str | None:
    html = match_view(weekday=weekday, date=date, time=time, votes=["5%", "11%", "84%"])
    with patch("oddsharvester.utils.page_time.datetime", frozen_clock(now)):
        return parse_match_community_dom(html, "url", tz_name=tz_name)["kickoff"]


def test_a_january_kickoff_shown_in_summer_is_read_one_hour_earlier():
    """Man City - Chelsea kicked off 17:30 GMT; scraped in BST under Europe/London the header shows 18:30."""
    assert _kickoff("Sunday,", "04 Jan 2026,", "18:30", "Europe/London") == "Sunday, 04 Jan 2026, 17:30"


def test_a_july_kickoff_shown_in_winter_is_read_one_hour_later():
    assert _kickoff("Saturday,", "04 Jul 2026,", "18:00", "Europe/London", WINTER_NOW) == "Saturday, 04 Jul 2026, 19:00"


@pytest.mark.parametrize("now", [SUMMER_NOW, WINTER_NOW])
def test_a_utc_kickoff_is_read_as_shown(now):
    assert _kickoff("Sunday,", "04 Jan 2026,", "17:30", "UTC", now) == "Sunday, 04 Jan 2026, 17:30"


@pytest.mark.parametrize("label", ["Today,", "Tomorrow,", "Yesterday,"])
def test_a_relative_day_label_is_written_as_the_weekday(label):
    """The header names the day relative to the day it is read, which a stored kickoff must not depend on."""
    assert _kickoff(label, "24 Aug 2026,", "21:00", "UTC") == "Monday, 24 Aug 2026, 21:00"


def test_a_kickoff_shown_just_after_midnight_moves_to_the_previous_day():
    """Shown 00:30 on 1 January in BST is 23:30 GMT on Thursday 31 December."""
    assert _kickoff("Friday,", "01 Jan 2027,", "00:30", "Europe/London") == "Thursday, 31 Dec 2026, 23:30"


def test_a_september_kickoff_shown_as_sept_is_read():
    assert _kickoff("Wednesday,", "30 Sept 2026,", "20:00", "Europe/London") == "Wednesday, 30 Sep 2026, 20:00"


@pytest.mark.parametrize(
    ("weekday", "date", "time"),
    [
        ("lundi,", "24 août 2026,", "21:00"),
        ("Monday,", "24 Aug 2026,", "Postponed"),
        ("Monday,", "24 Aug 2026,", "25:00"),
    ],
)
def test_a_kickoff_of_another_shape_is_kept_as_shown(caplog, weekday, date, time):
    html = match_view(weekday=weekday, date=date, time=time, votes=["5%", "11%", "84%"])

    with caplog.at_level(logging.DEBUG, logger="oddsharvester.core.community.match_community_parser"):
        kickoff = parse_match_community_dom(html, "url", tz_name="Europe/London")["kickoff"]

    assert kickoff == f"{weekday} {date} {time}"
    assert f"Kickoff {kickoff!r} is not 'Weekday, DD Mon YYYY, HH:MM'; kept as shown." in caplog.text
