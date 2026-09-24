import click
import pytest

from oddsharvester.cli.validators import validate_leagues


class _Ctx:
    def __init__(self, sport):
        self.params = {"sport": sport}


def test_accepts_a_known_league_slug():
    assert validate_leagues(_Ctx("football"), None, ["england-premier-league"]) == ["england-premier-league"]


def test_accepts_a_league_path_of_the_same_sport():
    assert validate_leagues(_Ctx("football"), None, ["football/bhutan/premier-league"]) == [
        "football/bhutan/premier-league"
    ]


def test_accepts_a_full_oddsportal_league_url():
    url = "https://www.oddsportal.com/football/bhutan/premier-league/"
    assert validate_leagues(_Ctx("football"), None, [url]) == [url]


def test_rejects_a_league_path_of_another_sport():
    with pytest.raises(click.BadParameter, match="tennis/atp/us-open"):
        validate_leagues(_Ctx("football"), None, ["tennis/atp/us-open"])


def test_rejects_an_unknown_slug_that_is_not_a_path():
    with pytest.raises(click.BadParameter, match="bhutan-premier-league"):
        validate_leagues(_Ctx("football"), None, ["bhutan-premier-league"])
