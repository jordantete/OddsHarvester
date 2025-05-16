import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from src.cli.cli_argument_validator import CLIArgumentValidator
from src.utils.sport_market_constants import Sport

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
        markets=["1x2", "btts"],
        proxies=None,
        browser_user_agent=None,
        browser_locale_timezone=None,
        browser_timezone_id=None,
        match_links=None,
        scrape_odds_history=False,
        target_bookmaker=None
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

@pytest.mark.parametrize("invalid_sport", ["invalid_sport", "handball", 123, None])
def test_validate_sport_invalid(invalid_sport):
    """Test validation of invalid sports."""
    validator = CLIArgumentValidator()
    
    with pytest.raises(ValueError) as exc_info:
        validator._validate_sport(sport=invalid_sport)
    
    expected_sports = ', '.join(s.value for s in Sport)
    if isinstance(invalid_sport, str):
        assert f"Invalid sport: '{invalid_sport}'. Supported sports are: {expected_sports}." in str(exc_info.value)
    else:
        assert f"Invalid sport: {invalid_sport}. Expected one of {[s.value for s in Sport]}." in str(exc_info.value)

def test_validate_sport_valid():
    """Test validation of valid sports."""
    validator = CLIArgumentValidator()
    valid_sports = [s.value for s in Sport]
    
    for sport in valid_sports:
        errors = validator._validate_sport(sport=sport)
        assert not errors, f"Validation failed for valid sport: {sport}"

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
    mock_args.match_links = None

    with pytest.raises(ValueError, match="Invalid date format: '25-02-2025'. Expected format is YYYYMMDD \\(e.g., 20250227\\)."):
        validator.validate_args(mock_args)

def test_validate_date_past_date(validator, mock_args):
    mock_args.date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    mock_args.match_links = None
    
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

def test_validate_markets_rugby_union():
    """Test validation of Rugby Union markets."""
    validator = CLIArgumentValidator()
    
    # Test valid markets
    valid_markets = ["1x2", "home_away", "over_under_43_5", "handicap_-13_5"]
    errors = validator._validate_markets(sport=Sport.RUGBY_UNION, markets=valid_markets)
    assert not errors, "Validation failed for valid Rugby Union markets"
    
    # Test invalid markets
    invalid_markets = ["invalid_market", "btts"]  # BTTS n'existe pas en Rugby Union
    errors = validator._validate_markets(sport=Sport.RUGBY_UNION, markets=invalid_markets)
    assert len(errors) == 2, "Validation should fail for invalid Rugby Union markets"

def test_validate_league_rugby_union():
    """Test validation of Rugby Union leagues."""
    validator = CLIArgumentValidator()
    
    # Test valid leagues
    valid_leagues = ["six-nations", "france-top-14", "world-cup"]
    for league in valid_leagues:
        errors = validator._validate_league(sport=Sport.RUGBY_UNION, league=league)
        assert not errors, f"Validation failed for valid Rugby Union league: {league}"
    
    # Test invalid league
    errors = validator._validate_league(sport=Sport.RUGBY_UNION, league="invalid-league")
    assert len(errors) == 1, "Validation should fail for invalid Rugby Union league"
    assert "Invalid league: 'invalid-league' for sport 'rugby-union'" in errors[0]