from tests.dom_builders import community_column, community_row, profile_page, statistics_row

from oddsharvester.core.community.user_profile_parser import parse_user_profile

_PREDICTION_COLUMNS = (
    community_column("1", "2.05", "87%", picked=True)
    + community_column("X", "3.50", "9%")
    + community_column("2", "3.95", "4%")
)

_PUBLIC_HTML = profile_page(
    statistics=statistics_row("06/2026", ["15", "5.28", "9", "-3.72", "-24.8%"])
    + statistics_row("Total", ["26", "13.72", "9", "4.72", "18.2%"]),
    rows=community_row(
        "/football/h2h/turkey/paraguay/",
        _PREDICTION_COLUMNS,
        date="20/Jun,",
        time="05:00",
        home="Turkey",
        away="Paraguay",
        scores=("0", "1"),
    ),
)

_PRIVATE_HTML = profile_page(
    username="zywrelip",
    roi="245.30%",
    member_since="16 Sep 2025",
    country="Italy",
    privacy="Private",
)


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
        "lost": 9.0,
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
    assert pred["score"] == "0-1"
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


_FEED_HTML = profile_page(
    rows=community_row(
        "/tennis/h2h/sabalenka-a/pegula-j/#abc123",
        community_column("2:5", "2.08", "50%", picked=True),
        date="20/Jun",
        time="12:10",
        market="CS",
        home="Sabalenka A.",
        away="Pegula J.",
    )
)


def test_feed_predictions_parsed():
    from oddsharvester.core.community.user_profile_parser import parse_profile_feed_predictions

    preds = parse_profile_feed_predictions(_FEED_HTML, tz_name="UTC")
    assert len(preds) == 1
    pred = preds[0]
    assert pred["home_team"] == "Sabalenka A."
    assert pred["away_team"] == "Pegula J."
    assert pred["market"] == "CS"
    assert pred["outcomes"] == [{"odds": 2.08, "community_pct": 50, "picked": True}]
    assert pred["pick_odds"] == 2.08
    assert pred["match_url"].endswith("#abc123")
