import click
import pytest

from oddsharvester.cli.validators import validate_markets


class _Ctx:
    """Mimics a click context's `.params` dict access used by validate_markets."""

    def __init__(self, sport):
        self.params = {"sport": sport}


def test_accepts_regular_markets_for_football():
    assert validate_markets(_Ctx("football"), None, ["1x2", "btts"]) == ["1x2", "btts"]


@pytest.mark.parametrize(
    ("sport", "umbrellas"),
    [
        ("football", ["over_under", "asian_handicap"]),
        ("basketball", ["over_under", "asian_handicap"]),
        ("american-football", ["over_under", "asian_handicap"]),
        ("handball", ["over_under", "asian_handicap"]),
        ("ice-hockey", ["over_under"]),
        ("baseball", ["over_under"]),
        ("rugby-league", ["over_under", "handicap"]),
        ("rugby-union", ["over_under", "handicap"]),
    ],
)
def test_accepts_the_umbrella_tokens_of_each_sport(sport, umbrellas):
    assert validate_markets(_Ctx(sport), None, umbrellas) == umbrellas


def test_rejects_unknown_market_for_football():
    with pytest.raises(click.BadParameter):
        validate_markets(_Ctx("football"), None, ["definitely_not_a_market"])


@pytest.mark.parametrize(
    ("sport", "market"),
    [
        ("tennis", "over_under"),
        ("volleyball", "over_under"),
        ("cricket", "over_under"),
        ("ice-hockey", "asian_handicap"),
        ("baseball", "asian_handicap"),
        ("rugby-league", "asian_handicap"),
    ],
)
def test_rejects_an_umbrella_token_the_sport_does_not_offer(sport, market):
    with pytest.raises(click.BadParameter):
        validate_markets(_Ctx(sport), None, [market])


@pytest.mark.parametrize("sport", ["rugby-league", "rugby-union", "ice-hockey"])
def test_the_bad_market_message_lists_each_supported_token_once(sport):
    with pytest.raises(click.BadParameter) as excinfo:
        validate_markets(_Ctx(sport), None, ["definitely_not_a_market"])

    listed = str(excinfo.value).split("Supported: ", 1)[1].split(", ")
    assert sorted({token for token in listed if listed.count(token) > 1}) == []
