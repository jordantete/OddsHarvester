from oddsharvester.core.community.user_profile_parser import parse_user_profile

_PUBLIC_HTML = """
<html><body>
<div data-testid="username">BLAPRO</div>
<div data-testid="user-roi">ROI 18.20%</div>
<div data-testid="member-info">Member since: 23 May 2026 Country: France Profile Privacy: Public</div>
<div>
  <div data-testid="stats-table-header-line">
    <span>Month</span><span>Total Predictions</span><span>Won</span><span>Lost</span><span>+ / -</span><span>ROI</span>
  </div>
  <div><span>06/2026</span><span>15</span><span>5.28</span><span>9</span><span>-3.72</span><span>-24.8%</span></div>
  <div><span>Total</span><span>26</span><span>13.72</span><span>9</span><span>4.72</span><span>18.2%</span></div>
</div>
<div data-testid="game-row">
  <a href="/football/h2h/turkey/paraguay/"></a>
  <div data-testid="date-time-item"><span>20/Jun,</span><span>05:00</span><span>1X2</span></div>
  <div data-testid="event-participants">
    <p class="participant-name">Turkey</p><span>0 - 1</span><p class="participant-name">Paraguay</p>
  </div>
  <p data-testid="odd-container-default">2.05</p><div data-testid="prediction-container">87%</div>
  <span data-testid="prediction-pick-item">PICK</span>
  <p data-testid="odd-container-default">3.50</p><div data-testid="prediction-container">9%</div>
  <p data-testid="odd-container-default">3.95</p><div data-testid="prediction-container">4%</div>
</div>
</body></html>
"""

_PRIVATE_HTML = """
<html><body>
<div data-testid="username">zywrelip</div>
<div data-testid="user-roi">ROI 245.30%</div>
<div data-testid="member-info">Member since: 16 Sep 2025 Country: Italy Profile Privacy: Private</div>
<div>Private Profile - Chosen by the user. This user's predictions are private.</div>
</body></html>
"""


def test_public_profile_header_parsed():
    rec = parse_user_profile(_PUBLIC_HTML)
    assert rec["mode"] == "user"
    assert rec["username"] == "BLAPRO"
    assert rec["roi_pct"] == 18.20
    assert rec["country"] == "France"
    assert rec["privacy"] == "public"
    assert rec["member_since"] == "2026-05-23"


def test_public_profile_statistics_rows():
    rec = parse_user_profile(_PUBLIC_HTML)
    assert rec["statistics"][0] == {
        "month": "06/2026",
        "total_predictions": 15,
        "won": 5.28,
        "lost": 9,
        "plus_minus": -3.72,
        "roi_pct": -24.8,
    }
    assert rec["statistics"][-1]["month"] == "Total"


def test_public_profile_predictions_positional_pick():
    rec = parse_user_profile(_PUBLIC_HTML)
    pred = rec["predictions"][0]
    assert pred["market"] == "1X2"
    assert pred["home_team"] == "Turkey"
    assert pred["away_team"] == "Paraguay"
    assert pred["score"] == "0 - 1"
    assert pred["outcomes"] == [
        {"odds": 2.05, "community_pct": 87, "picked": True},
        {"odds": 3.50, "community_pct": 9, "picked": False},
        {"odds": 3.95, "community_pct": 4, "picked": False},
    ]
    assert pred["pick_odds"] == 2.05
    assert pred["match_url"].endswith("/football/h2h/turkey/paraguay/")


def test_private_profile_header_only():
    rec = parse_user_profile(_PRIVATE_HTML)
    assert rec["privacy"] == "private"
    assert rec["username"] == "zywrelip"
    assert rec["statistics"] == []
    assert rec["predictions"] == []
