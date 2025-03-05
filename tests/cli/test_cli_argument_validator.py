import pytest, re
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from src.cli.cli_argument_validator import CLIArgumentValidator

@pytest.fixture
def validator():
    return CLIArgumentValidator()

@pytest.fixture
def mock_args():
    return MagicMock(
        command="scrape_upcoming",
        sport="football",
        league="england-premier-league",
        date=(datetime.now() + timedelta(days=1)).strftime("%Y%m%d"),  # Corrected format (YYYYMMDD)
        storage="local",
        format="json",
        file_path="data.json",
        headless=True,
        markets=["1x2", "btts"]
    )

def test_validate_args_valid(validator, mock_args):
    try:
        validator.validate_args(mock_args)
    except ValueError as e:
        pytest.fail(f"Unexpected ValueError: {e}")

def test_validate_command_invalid(validator, mock_args):
    mock_args.command = "invalid_command"
    with pytest.raises(ValueError, match="Invalid command 'invalid_command'. Supported commands are: scrape_upcoming, scrape_historic."):
        validator.validate_args(mock_args)

def test_validate_sport_invalid(validator, mock_args):
    mock_args.sport = "invalid_sport"
    expected_error = "Invalid sport: 'invalid_sport'. Supported sports are: football, tennis."

    with pytest.raises(ValueError, match=re.escape(expected_error)):
        validator.validate_args(mock_args)

def test_validate_markets_invalid(validator, mock_args):
    mock_args.markets = ["invalid_market"]
    with pytest.raises(ValueError, match="Invalid market: invalid_market. Supported markets for football: "):
        validator.validate_args(mock_args)

def test_validate_league_invalid(validator, mock_args):
    mock_args.league = "invalid_league"
    with pytest.raises(ValueError, match="Invalid league: 'invalid_league' for sport 'football'."):
        validator.validate_args(mock_args)

def test_validate_date_invalid_format(validator, mock_args):
    mock_args.date = "25-02-2025"

    with pytest.raises(ValueError, match="Invalid date format: '25-02-2025'. Expected format is YYYYMMDD \\(e.g., 20250227\\)."):
        validator.validate_args(mock_args)

def test_validate_date_past_date(validator, mock_args):
    mock_args.date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

    with pytest.raises(ValueError, match="Date .* must be today or in the future."):
        validator.validate_args(mock_args)

def test_validate_storage_invalid(validator, mock_args):
    mock_args.storage = "invalid_storage"
    with pytest.raises(ValueError, match="Invalid storage type: 'invalid_storage'. Supported storage types are: "):
        validator.validate_args(mock_args)

def test_validate_file_path_invalid_extension(validator, mock_args):
    mock_args.file_path = "data.invalid"
    with pytest.raises(ValueError, match="Mismatch between file format 'json' and file path extension 'invalid'."):
        validator.validate_args(mock_args)

def test_validate_file_format_mismatch(validator, mock_args):
    mock_args.file_path = "data.json"
    mock_args.format = "csv"
    with pytest.raises(ValueError, match="Mismatch between file format 'csv' and file path extension 'json'."):
        validator.validate_args(mock_args)