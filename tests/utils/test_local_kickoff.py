from oddsharvester.utils.local_kickoff import compute_local_kickoff


def test_converts_utc_to_venue_local_single_tz_country():
    tz, local = compute_local_kickoff("2022-05-01 15:00:00 UTC", "England", None)
    assert tz == "Europe/London"
    # London is BST (UTC+1) on 2022-05-01
    assert local == "2022-05-01 16:00:00 BST+0100"


def test_converts_utc_to_venue_local_multi_tz_country():
    tz, local = compute_local_kickoff("2022-05-01 23:00:00 UTC", "USA", "New York")
    assert tz == "America/New_York"
    # EDT (UTC-4) on 2022-05-01
    assert local == "2022-05-01 19:00:00 EDT-0400"


def test_dst_boundary_uses_correct_offset_per_date():
    # Same venue, winter date => EST (UTC-5)
    tz, local = compute_local_kickoff("2022-01-15 23:00:00 UTC", "USA", "New York")
    assert tz == "America/New_York"
    assert local == "2022-01-15 18:00:00 EST-0500"


def test_unresolved_venue_returns_none_pair():
    assert compute_local_kickoff("2022-05-01 15:00:00 UTC", "Atlantis", "Poseidonis") == (None, None)


def test_missing_match_date_returns_none_pair():
    assert compute_local_kickoff(None, "England", None) == (None, None)


def test_unparseable_match_date_returns_tz_but_no_local():
    tz, local = compute_local_kickoff("not-a-date", "England", None)
    assert tz == "Europe/London"
    assert local is None
