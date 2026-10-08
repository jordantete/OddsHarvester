import pytest
from tests.dom_builders import (
    EMPTY_SEARCH_TAB,
    listing_row,
    search_match,
    search_next,
    search_page,
    search_participant,
    search_results,
    trap_row,
)

from oddsharvester.core.exceptions import PageNotFoundError, ParsingError
from oddsharvester.core.search.search_parser import MatchPage, parse_candidates, parse_matches

_QUERY_URL = "https://www.oddsportal.com/search/results/Nacional/football/"
_RESULTS_URL = "https://www.oddsportal.com/search/results/:hUyau0Vc/"
_TEAM = "hUyau0Vc"
_LINK = "https://www.oddsportal.com/football/h2h/nacional-potosi-hUyau0Vc/real-oruro-KG3q1tio/#jgMzUSAC"


def _candidates_page(*participants: dict) -> str:
    keyed = {str(n): participant for n, participant in enumerate(participants)}
    return search_page({"tableHidden": True, "participants": keyed}, search_string="Nacional")


def test_a_candidate_carries_its_id_plain_name_country_sport_and_team_url():
    [candidate] = parse_candidates(_candidates_page(search_participant()), url=_QUERY_URL)

    assert candidate == {
        "team_id": "hUyau0Vc",
        "name": "Nacional Potosi",
        "country": "Bolivia",
        "sport": "football",
        "team_url": "https://www.oddsportal.com/football/team/nacional-potosi/hUyau0Vc/",
    }


def test_candidates_come_most_relevant_first():
    """The payload keys participants by numeric id, so its own order is not the page's."""
    html = _candidates_page(
        search_participant(team_id="tSCiHj0I", name="Inter<strong>nacional</strong>", score=144.1),
        search_participant(team_id="UykdNnHh", name="<strong>Nacional</strong>-AM", score=40.5),
        search_participant(team_id="C23omttL", name="Atl.&nbsp;<strong>Nacional</strong>", score=197.4),
    )

    candidates = parse_candidates(html, url=_QUERY_URL)

    assert [c["team_id"] for c in candidates] == ["C23omttL", "tSCiHj0I", "UykdNnHh"]
    assert [c["name"] for c in candidates] == ["Atl. Nacional", "Internacional", "Nacional-AM"]


def test_a_search_with_no_candidate_is_an_empty_list():
    """An empty collection arrives as a JSON list, not an object."""
    html = search_page({"tableHidden": True, "participants": []}, search_string="Zzzz")

    assert parse_candidates(html, url=_QUERY_URL) == []


def test_a_candidate_sport_is_the_cli_name():
    html = _candidates_page(search_participant(sport="hockey", slug="nacional-hc"))

    [candidate] = parse_candidates(html, url=_QUERY_URL)

    assert candidate["sport"] == "ice-hockey"
    assert candidate["team_url"] == "https://www.oddsportal.com/hockey/team/nacional-hc/hUyau0Vc/"


def test_candidate_urls_follow_the_base_url():
    [candidate] = parse_candidates(
        _candidates_page(search_participant()), url=_QUERY_URL, base_url="https://www.centroquote.it"
    )

    assert candidate["team_url"].startswith("https://www.centroquote.it/football/team/")


def test_a_played_match_carries_every_field():
    page = parse_matches(search_page(search_results([search_match()])), url=_RESULTS_URL, team_id=_TEAM, tab="results")

    assert page.rows == [
        {
            "match_link": _LINK,
            "kickoff_utc": "2026-10-03 21:15:00 UTC",
            "tab": "results",
            "home_team": "Nacional Potosi",
            "home_team_id": "hUyau0Vc",
            "away_team": "Real Oruro",
            "away_team_id": "KG3q1tio",
            "home_score": "2",
            "away_score": "0",
            "tournament": "Copa Pacena",
            "league_url": "https://www.oddsportal.com/football/bolivia/copa-pacena/",
            "country": "Bolivia",
            "sport": "football",
        }
    ]


def test_an_upcoming_match_has_no_score():
    html = search_page(search_next([search_match(home_result="", away_result="")]))

    [row] = parse_matches(html, url=_RESULTS_URL, team_id=_TEAM, tab="next").rows

    assert row["tab"] == "next"
    assert (row["home_score"], row["away_score"]) == (None, None)


@pytest.mark.parametrize("zero", ["0", 0])
def test_a_zero_score_stays_a_score(zero):
    html = search_page(search_results([search_match(home_result=zero, away_result=zero)]))

    [row] = parse_matches(html, url=_RESULTS_URL, team_id=_TEAM, tab="results").rows

    assert (row["home_score"], row["away_score"]) == ("0", "0")


def test_a_results_page_gives_its_total_and_page_count():
    html = search_page(search_results([search_match()], total=79, page_count=4))

    page = parse_matches(html, url=_RESULTS_URL, team_id=_TEAM, tab="results")

    assert (page.total, page.page_count) == (79, 4)


def test_an_empty_tab_of_a_known_team_is_an_empty_page():
    page = parse_matches(search_page(EMPTY_SEARCH_TAB), url=_RESULTS_URL, team_id=_TEAM, tab="next")

    assert page == MatchPage(rows=[], total=0, page_count=1)


def test_an_unknown_team_id_does_not_exist_on_oddsportal():
    """The site answers an unknown id with an empty tab; only the blank team name tells it from a quiet team."""
    html = search_page(EMPTY_SEARCH_TAB, search_string="")

    with pytest.raises(PageNotFoundError, match="Team id zzzzzzzz does not exist on OddsPortal"):
        parse_matches(html, url=_RESULTS_URL, team_id="zzzzzzzz", tab="results")


def test_a_page_without_the_team_name_key_is_not_called_unknown():
    html = search_page(EMPTY_SEARCH_TAB, search_string=None)

    assert parse_matches(html, url=_RESULTS_URL, team_id=_TEAM, tab="results").rows == []


def test_the_trap_row_in_the_dom_never_reaches_the_rows():
    trap = trap_row(listing_row("/football/h2h/nacional-potosi-105e5a7c/real-potosi-c1ef4423/"))
    html = search_page(search_results([search_match()]), dom=trap)

    rows = parse_matches(html, url=_RESULTS_URL, team_id=_TEAM, tab="results").rows

    assert [row["match_link"].rsplit("#", 1)[-1] for row in rows] == ["jgMzUSAC"]


def test_the_payload_is_found_past_other_chunks_and_survives_braces_in_names():
    match = search_match(tournament=("Copa {Pacena}", "/football/bolivia/copa-pacena/"))
    html = search_page(search_results([match]), chunks_before=4)

    [row] = parse_matches(html, url=_RESULTS_URL, team_id=_TEAM, tab="results").rows

    assert row["tournament"] == "Copa {Pacena}"


def test_match_urls_follow_the_base_url():
    html = search_page(search_results([search_match()]))

    [row] = parse_matches(
        html, url=_RESULTS_URL, team_id=_TEAM, tab="results", base_url="https://www.centroquote.it"
    ).rows

    assert row["match_link"].startswith("https://www.centroquote.it/football/h2h/")
    assert row["league_url"] == "https://www.centroquote.it/football/bolivia/copa-pacena/"


@pytest.mark.parametrize("parse", [
    lambda html: parse_candidates(html, url=_QUERY_URL),
    lambda html: parse_matches(html, url=_RESULTS_URL, team_id=_TEAM, tab="results"),
])  # fmt: skip
def test_a_page_without_payload_is_a_parsing_error(parse):
    with pytest.raises(ParsingError, match="no searchData payload"):
        parse("<main><h1>Search Results for: </h1></main>")
