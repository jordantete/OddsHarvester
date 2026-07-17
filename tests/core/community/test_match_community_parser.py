from oddsharvester.core.community.match_community_parser import parse_match_community

_COMMUNITY = {
    "total": {
        "E-10620747_1_2_0_0.00": 22,
        "E-10620747_5_2_0_1.00": 1,
        "E-10620747_4_2_0_0.00": 3,
        "E-10620747_13_2_0_0.00": 1,
        "E-10620747_2_2_0_3.50": 1,
        "E-10620747_99_2_0_0.00": 5,
    },
    "count": {
        "enc_1a": 20,
        "enc_1b": 1,
        "enc_1c": 1,
        "enc_ah": 1,
        "enc_dc": 3,
        "enc_btts": 1,
        "enc_ou": 1,
        "enc_unknown": 5,
    },
    "group": {
        "enc_1a": "E-10620747_1_2_0_0.00",
        "enc_1b": "E-10620747_1_2_0_0.00",
        "enc_1c": "E-10620747_1_2_0_0.00",
        "enc_ah": "E-10620747_5_2_0_1.00",
        "enc_dc": "E-10620747_4_2_0_0.00",
        "enc_btts": "E-10620747_13_2_0_0.00",
        "enc_ou": "E-10620747_2_2_0_3.50",
        "enc_unknown": "E-10620747_99_2_0_0.00",
    },
}

_RAW = {
    "communityData": _COMMUNITY,
    "startDate": 1784282400,
    "home_team": "Nordsjaelland",
    "away_team": "Sparta Prague",
    "is_started": False,
    "is_finished": False,
    "pick_text": "Sparta Prague To win",
}


def test_prematch_markets_decoded_sorted_and_labeled():
    rec = parse_match_community(_RAW, "https://www.oddsportal.com/football/h2h/x/y/")
    assert rec["mode"] == "match"
    assert rec["event_id"] == "10620747"
    assert rec["is_prematch"] is True
    assert rec["top_community_pick"] == "Sparta Prague To win"
    # Most-voted market first; 1X2 = 22 votes, per-outcome counts sorted desc summing to total.
    top = rec["markets"][0]
    assert top["market"] == "1X2"
    assert top["scope"] == "Full Time"
    assert top["betting_type_id"] == 1
    assert top["total_votes"] == 22
    assert top["outcome_counts"] == [20, 1, 1]
    assert sum(top["outcome_counts"]) == top["total_votes"]


def test_unknown_betting_type_falls_back_without_crashing():
    rec = parse_match_community(_RAW, "url")
    unknown = next(m for m in rec["markets"] if m["betting_type_id"] == 99)
    assert unknown["market"] == "betting_type_99"


def test_kickoff_from_start_date_is_utc_iso():
    rec = parse_match_community(_RAW, "url")
    assert rec["kickoff"].startswith("2026-07-")
    assert rec["kickoff"].endswith("+00:00")


def test_finished_match_has_no_markets():
    raw = {**_RAW, "communityData": None, "is_started": True, "is_finished": True}
    rec = parse_match_community(raw, "url")
    assert rec["markets"] == []
    assert rec["is_prematch"] is False
