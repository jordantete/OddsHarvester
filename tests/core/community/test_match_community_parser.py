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
    assert rec["kickoff"] == "Today, 24 Aug 2026, 21:00"
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
