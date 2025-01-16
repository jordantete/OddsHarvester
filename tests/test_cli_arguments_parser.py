import pytest
from argparse import Namespace
from src.utils.cli_arguments_parser import validate_args, parse_args
from src.utils.constants import SUPPORTED_SPORTS, SUPPORTED_MARKETS, FOOTBALL_LEAGUES_URLS_MAPPING

# Valid arguments for testing
VALID_ARGS = Namespace(
    sport=SUPPORTED_SPORTS[0],  # Dynamically use a valid sport
    league=list(FOOTBALL_LEAGUES_URLS_MAPPING.keys())[0],  # Use the first valid league
    season="2023-2024",
    date="2025-01-01",
    storage="local",
    headless=True,
    markets=SUPPORTED_MARKETS[:2]  # Use the first two valid markets
)

def test_validate_args_valid():
    try:
        validate_args(VALID_ARGS)  # Should not raise an exception
    except ValueError as e:
        pytest.fail(f"validate_args raised an exception unexpectedly: {e}")

def test_validate_args_invalid_market():
    invalid_args = Namespace(**vars(VALID_ARGS))
    invalid_args.markets = ["invalid_market"]

    with pytest.raises(ValueError, match="Invalid markets"):
        validate_args(invalid_args)

def test_validate_args_invalid_sport():
    invalid_args = Namespace(**vars(VALID_ARGS))
    invalid_args.sport = "invalid_sport"

    with pytest.raises(ValueError, match="Invalid sport"):
        validate_args(invalid_args)

def test_validate_args_invalid_league():
    invalid_args = Namespace(**vars(VALID_ARGS))
    invalid_args.league = "invalid-league"

    with pytest.raises(ValueError, match="Invalid league"):
        validate_args(invalid_args)

def test_validate_args_invalid_date():
    invalid_args = Namespace(**vars(VALID_ARGS))
    invalid_args.date = "01-01-2025"  # Invalid format

    with pytest.raises(ValueError, match="Invalid date format"):
        validate_args(invalid_args)

def test_validate_args_invalid_storage():
    invalid_args = Namespace(**vars(VALID_ARGS))
    invalid_args.storage = "invalid_storage"

    with pytest.raises(ValueError, match="Invalid storage type"):
        validate_args(invalid_args)

def test_parse_args_valid(mocker):
    mocker.patch("argparse.ArgumentParser.parse_args", return_value=VALID_ARGS)
    args = parse_args()
    assert args.sport == SUPPORTED_SPORTS[0]
    assert args.league == list(FOOTBALL_LEAGUES_URLS_MAPPING.keys())[0]
    assert args.season == "2023-2024"
    assert args.date == "2025-01-01"
    assert args.storage == "local"
    assert args.headless is True
    assert args.markets == SUPPORTED_MARKETS[:2]

def test_parse_args_defaults(mocker):
    default_args = Namespace(
        sport="football",
        league=None,
        season=None,
        date=None,
        storage="local",
        headless=False,
        markets=["1x2"]
    )
    mocker.patch("argparse.ArgumentParser.parse_args", return_value=default_args)
    args = parse_args()
    assert args.sport == "football"
    assert args.league is None
    assert args.season is None
    assert args.date is None
    assert args.storage == "local"
    assert args.headless is False
    assert args.markets == ["1x2"]

def test_combination_valid_invalid_args():
    invalid_args = Namespace(**vars(VALID_ARGS))
    invalid_args.markets = ["1x2", "invalid_market"]

    with pytest.raises(ValueError, match="Invalid markets"):
        validate_args(invalid_args)