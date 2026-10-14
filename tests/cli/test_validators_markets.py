import re

import click
import pytest

from oddsharvester.cli.validators import validate_markets
from oddsharvester.utils.sport_market_constants import Sport
from oddsharvester.utils.utils import get_supported_markets


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


def _bad_market_message(sport: str, market: str = "definitely_not_a_market") -> str:
    with pytest.raises(click.BadParameter) as excinfo:
        validate_markets(_Ctx(sport), None, [market])
    return str(excinfo.value)


def test_the_bad_market_message_names_the_sports_umbrellas():
    assert "Umbrellas (every line on the page): over_under, handicap." in _bad_market_message("rugby-union")


def test_the_bad_market_message_names_no_umbrella_for_a_sport_without_one():
    assert "Umbrellas" not in _bad_market_message("tennis")


def test_the_bad_market_message_offers_the_closest_tokens():
    message = _bad_market_message("rugby-union", "handicap_2_5x")

    assert "Closest: handicap_-2_5, handicap_+2_5" in message


def test_the_bad_market_message_sums_up_each_line_family_by_its_ends():
    message = _bad_market_message("rugby-union")

    assert "Supported: 1x2, home_away, dnb, double_chance," in message
    assert "over_under_20_5 ... over_under_90_5 (141)" in message
    assert "handicap_-45_5 ... handicap_+45_5 (183)" in message


def test_the_bad_market_message_gives_a_family_its_lowest_and_highest_line():
    """The tennis games handicaps are registered from +2.5 up to +8.5, then from -2.5 down to -8.5."""
    assert "asian_handicap_-8_5_games ... asian_handicap_+8_5_games (14)" in _bad_market_message("tennis")


@pytest.mark.parametrize("sport", ["tennis", "volleyball"])
def test_the_bad_market_message_lists_each_correct_score(sport):
    """A correct score is not a line: 6:4 and 3:1 cannot be told from a range's ends."""
    message = _bad_market_message(sport)

    scores = [token for token in get_supported_markets(sport) if token.startswith("correct_score_")]
    assert scores
    assert all(score in message for score in scores)
    assert " ... correct_score_" not in message


@pytest.mark.parametrize("sport", [sport.value for sport in Sport])
def test_the_bad_market_message_counts_each_supported_token_once_and_stays_short(sport):
    message = _bad_market_message(sport)

    listed = message.split("Supported: ", 1)[1].rstrip(".").replace(",\n", ", ")
    entries = [entry.strip() for entry in listed.split(", ")]
    counted = sum(int(m.group(1)) if (m := re.search(r"\((\d+)\)$", entry)) else 1 for entry in entries)
    assert counted == len(get_supported_markets(sport))
    assert len(message) < 1000
