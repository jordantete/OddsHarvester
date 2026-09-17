import pytest
from tests.dom_builders import form_event, team_page

from oddsharvester.core.exceptions import ParsingError
from oddsharvester.core.team.team_parser import parse_team_page

_URL = "https://www.oddsportal.com/football/team/x/lId4TMwf/"


def test_parses_a_complete_team_record():
    record = parse_team_page(team_page(), team_id="lId4TMwf", team_url=_URL)

    assert record["team_id"] == "lId4TMwf"
    assert record["name"] == "Liverpool"
    assert record["full_name"] == "Liverpool Football Club"
    assert record["country"] == "England"
    assert record["town"] == "Liverpool"
    assert record["venue"] == "Anfield"
    assert record["coach"] == "Iraola Andoni"
    assert record["sport"] == "football"


def test_logo_url_is_absolute_and_stripped_of_its_version_stamp():
    record = parse_team_page(team_page(), team_id="lId4TMwf", team_url=_URL)

    assert record["logo_url"] == ("https://www.oddsportal.com/proxy/serve/images/team-logo/Men/K00665Rc-KCp4zq5F.png")


def test_form_is_a_flat_string_and_percentages_are_numbers():
    """The CSV writer only handles top-level scalars, and a spreadsheet needs to compute."""
    record = parse_team_page(team_page(), team_id="lId4TMwf", team_url=_URL)

    assert record["form"] == "W,D,W,W,D,D"
    assert record["btts_pct"] == 67.0
    assert record["over_2_5_pct"] == 33.0
    assert record["avg_goals_scored"] == 1.8
    assert record["avg_goals_conceded"] == 1.0


def test_list_name_is_resolved_from_the_side_carrying_the_team_id():
    """The team sits home in one entry and away in the other; both must yield the same name."""
    record = parse_team_page(team_page(), team_id="lId4TMwf", team_url=_URL)

    assert record["list_name"] == "Liverpool"


def test_list_name_survives_a_page_showing_no_odds_rows():
    """Barcelona FC renders zero rows from a French IP, yet the form block still names it."""
    html = team_page(
        name="Barcelona FC",
        full_name="Barcelona de Ilheus",
        logo_src="/proxy/serve/images/team-logo/Men/W0eABFPt-f5FmjcSH.png?260917091420",
        basic_info={
            "countryImage": "https://cci2.oddsportal.com/country-flags/br.svg",
            "venueCountry": None,
            "venueTown": None,
            "venue": None,
            "coach": "Paulo Sales",
        },
        last_performance={
            "form": ["D", "D", "L"],
            "formEvents": [
                form_event(
                    "1:1 (Jequie - Barcelona) 22.02.2026",
                    "https://www.oddsportal.com/football/h2h/barcelona-fc-WGt8En5I/jequie-ARKkmIRH/#CfvH0CCs/",
                ),
                form_event(
                    "0:0 (Barcelona - Juazeirense) 19.02.2026",
                    "https://www.oddsportal.com/football/h2h/barcelona-fc-WGt8En5I/juazeirense-6HMrrrMF/#d8cBge5E/",
                ),
            ],
            "avgGoalsScored": "0.7",
            "avgGoalsConceded": "2.5",
            "scoredBtsPercent": "67%",
            "scoredOverPercent": "33%",
        },
    )

    record = parse_team_page(html, team_id="WGt8En5I", team_url=_URL)

    assert record["list_name"] == "Barcelona"
    assert record["name"] == "Barcelona FC"
    assert record["full_name"] == "Barcelona de Ilheus"
    assert record["coach"] == "Paulo Sales"
    assert record["country"] is None
    assert record["town"] is None
    assert record["venue"] is None


def test_team_url_is_rebuilt_from_the_canonical_slug_in_the_form_events():
    record = parse_team_page(team_page(), team_id="lId4TMwf", team_url=_URL)

    assert record["team_url"] == "https://www.oddsportal.com/football/team/liverpool/lId4TMwf/"


def test_an_empty_form_block_leaves_the_derived_fields_null():
    html = team_page(last_performance={"form": [], "formEvents": []})

    record = parse_team_page(html, team_id="lId4TMwf", team_url=_URL)

    assert record["list_name"] is None
    assert record["sport"] is None
    assert record["form"] is None
    assert record["team_url"] == _URL, "with no canonical slug to recover, the requested URL is kept"
    assert record["name"] == "Liverpool", "identity still comes from the page itself"


def test_a_page_without_payload_is_an_error_not_an_empty_record():
    """A wrong id renders a page whose heading and breadcrumb are built from the slug."""
    html = team_page(with_payload=False)

    with pytest.raises(ParsingError) as excinfo:
        parse_team_page(html, team_id="zzzzzzzz", team_url=_URL)

    assert excinfo.value.is_retryable is False, "a wrong id will never grow a payload on retry"


@pytest.mark.parametrize("missing", ["coach", "venue", "venueTown", "venueCountry"])
def test_missing_basic_info_fields_are_null(missing):
    basic_info = {
        "venueCountry": "England",
        "venueTown": "Liverpool",
        "venue": "Anfield",
        "coach": "Iraola Andoni",
    }
    basic_info[missing] = None

    record = parse_team_page(team_page(basic_info=basic_info), team_id="lId4TMwf", team_url=_URL)

    assert record[{"venueTown": "town", "venueCountry": "country"}.get(missing, missing)] is None


def test_tournament_is_read_from_the_fixture_rows():
    html = team_page(
        leagues=(
            ("/football/england/premier-league/", "Premier League"),
            ("/football/europe/champions-league/", "Champions League"),
        )
    )

    assert parse_team_page(html, team_id="lId4TMwf", team_url=_URL)["tournament"] == "Premier League"


def test_tournament_is_null_when_no_fixture_row_is_rendered():
    """Fixture rows follow the IP's selected bookmakers, so they are often absent."""
    assert parse_team_page(team_page(), team_id="lId4TMwf", team_url=_URL)["tournament"] is None


def test_an_unreadable_payload_is_an_error_naming_the_page():
    """Site drift that breaks the payload must surface as a typed error, not a crash."""
    html = '<main><main><script>self.__next_f.push([1,"{\\"basicInfo\\":{\\"coach\\":}}"])</script></main></main>'

    with pytest.raises(ParsingError) as excinfo:
        parse_team_page(html, team_id="lId4TMwf", team_url=_URL)

    assert _URL in str(excinfo.value)
