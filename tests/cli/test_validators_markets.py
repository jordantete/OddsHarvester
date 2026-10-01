import click
import pytest

from oddsharvester.cli.validators import validate_markets


class _Ctx:
    """Mimics a click context's `.params` dict access used by validate_markets."""

    def __init__(self, sport):
        self.params = {"sport": sport}


def test_accepts_regular_markets_for_football():
    assert validate_markets(_Ctx("football"), None, ["1x2", "btts"]) == ["1x2", "btts"]


def test_accepts_umbrella_tokens_for_football():
    value = ["over_under", "asian_handicap"]
    assert validate_markets(_Ctx("football"), None, value) == value


def test_rejects_unknown_market_for_football():
    with pytest.raises(click.BadParameter):
        validate_markets(_Ctx("football"), None, ["definitely_not_a_market"])


def test_rejects_umbrella_tokens_for_non_football_sport():
    with pytest.raises(click.BadParameter):
        validate_markets(_Ctx("tennis"), None, ["over_under"])


@pytest.mark.parametrize("sport", ["rugby-league", "rugby-union", "ice-hockey"])
def test_the_bad_market_message_lists_each_supported_token_once(sport):
    with pytest.raises(click.BadParameter) as excinfo:
        validate_markets(_Ctx(sport), None, ["definitely_not_a_market"])

    listed = str(excinfo.value).split("Supported: ", 1)[1].split(", ")
    assert sorted({token for token in listed if listed.count(token) > 1}) == []
