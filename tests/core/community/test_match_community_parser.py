from oddsharvester.core.community.match_community_parser import parse_match_community_dom

_PREMATCH_HTML = """
<html><body>
<div data-testid="game-participants">
  <div data-testid="game-host"><a data-testid="participant-name">Fulham</a></div>
  <div data-testid="game-guest"><a data-testid="participant-name">Chelsea</a></div>
</div>
<div data-testid="game-time-item"><p>Today,</p><p>24 Aug 2026,</p><p>21:00</p></div>
<div data-testid="sports-nav-active-tab">1X2</div>
<div data-testid="sub-nav-active-tab">All Bookies</div>
<div data-testid="sub-nav-active-tab">Full Time</div>
<div data-testid="betting-tip-header">1</div>
<div data-testid="betting-tip-header">X</div>
<div data-testid="betting-tip-header">2</div>
<div data-testid="user-predictions-row">
  <p>User Predictions</p>
  <div data-testid="prediction-container">5%</div>
  <div data-testid="prediction-container">11%</div>
  <div data-testid="prediction-container">84%</div>
</div>
</body></html>
"""


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


def test_started_match_detected_via_red_score():
    html = _PREMATCH_HTML.replace(
        '<div data-testid="game-guest"><a data-testid="participant-name">Chelsea</a></div>',
        '<div data-testid="game-guest"><a data-testid="participant-name">Chelsea</a></div>'
        '<div class="shrink-0 text-red-dark">1</div><div class="shrink-0 text-red-dark">0</div>',
    )
    rec = parse_match_community_dom(html, "url")
    assert rec["is_prematch"] is False


def test_finished_match_detected_via_live_info():
    html = _PREMATCH_HTML.replace(
        '<div data-testid="user-predictions-row">',
        '<div data-testid="live-info">Final result 1:2 (0:1, 1:1)</div><div data-testid="user-predictions-row">',
    )
    rec = parse_match_community_dom(html, "url")
    assert rec["is_prematch"] is False


def test_non_hydrated_page_yields_no_markets():
    rec = parse_match_community_dom("<html><body><h1>X - Y</h1></body></html>", "url")
    assert rec["markets"] == []
    assert rec["home_team"] is None
