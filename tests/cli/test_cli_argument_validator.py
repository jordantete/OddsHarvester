from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

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
        target_bookmaker=None,
    )


def test_validate_args_valid(validator, mock_args):
    try:
        validator.validate_args(mock_args)
    except ValueError as e:
        pytest.fail(f"Unexpected ValueError: {e}")


def test_validate_command_invalid(validator, mock_args):
    mock_args.command = "invalid_command"
    with pytest.raises(
        ValueError, match="Invalid command 'invalid_command'. Supported commands are: scrape_upcoming, scrape_historic."
    ):
        validator.validate_args(mock_args)


@pytest.mark.parametrize("invalid_sport", ["invalid_sport", "handball", 123, None])
def test_validate_sport_invalid(invalid_sport):
    """Test validation of invalid sports."""
    validator = CLIArgumentValidator()

    with pytest.raises(ValueError) as exc_info:
        validator._validate_sport(sport=invalid_sport)

    expected_sports = ", ".join(s.value for s in Sport)
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
    mock_args.league = None

    with pytest.raises(
        ValueError, match="Invalid date format: '25-02-2025'. Expected format is YYYYMMDD \\(e.g., 20250227\\)."
    ):
        validator.validate_args(mock_args)


def test_validate_date_past_date(validator, mock_args):
    mock_args.date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    mock_args.match_links = None
    mock_args.league = None

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


# Tests pour _validate_season
@pytest.mark.parametrize(
    ("command", "season", "expected_errors"),
    [
        ("scrape_historic", "2023-2024", []),  # Valid format YYYY-YYYY
        ("scrape_historic", "2023", []),  # Valid format YYYY
        (
            "scrape_historic",
            "2022-2024",
            ["Invalid season range: '2022-2024'. The second year must be exactly one year after the first year."],
        ),  # Invalid range
        (
            "scrape_historic",
            "202X",
            ["Invalid season format: '202X'. Expected format: YYYY or YYYY-YYYY (e.g., 2024 or 2024-2025)."],
        ),  # Invalid format
        (
            "scrape_historic",
            None,
            ["The season argument is required for the 'scrape_historic' command."],
        ),  # Missing season
        ("scrape_upcoming", "2023-2024", []),  # Different command, no validation
    ],
)
def test_validate_season(validator, command, season, expected_errors):
    """Test validation of the season parameter."""
    errors = validator._validate_season(command=command, season=season)
    assert errors == expected_errors


# Test pour _validate_date avec match_links fourni
def test_validate_date_with_match_links(validator):
    """Test that date is not required when match_links is provided."""
    errors = validator._validate_date(
        command="scrape_upcoming", date=None, match_links=["https://www.oddsportal.com/match/123456"]
    )
    assert not errors, "Validation should succeed when match_links is provided, even without date"


def test_validate_date_with_league(validator):
    """Test that date is not required when league is provided."""
    errors = validator._validate_date(
        command="scrape_upcoming", date=None, match_links=None, league="england-premier-league"
    )
    assert not errors, "Validation should succeed when league is provided, even without date"


# Test pour _validate_date pour une commande autre que scrape_upcoming
def test_validate_date_wrong_command(validator):
    """Test date validation for a command other than scrape_upcoming."""
    errors = validator._validate_date(command="scrape_historic", date="20250101", match_links=None)
    assert len(errors) == 1
    assert "Date should not be provided for the 'scrape_historic' command." in errors[0]


# Tests pour _validate_proxies
@pytest.mark.parametrize(
    ("proxies", "expected_errors"),
    [
        (None, []),  # Pas de proxy spécifié
        ([], []),  # Liste vide
        (["http://proxy.com:8080 user pass"], []),  # Format valide avec auth
        (["socks5://proxy.com:1080"], []),  # Format valide sans auth
        (
            ["invalid_proxy_format"],
            [
                "Invalid proxy format: 'invalid_proxy_format'. Expected format: 'http[s]://host:port [user pass]' or 'socks5://host:port [user pass]'."
            ],
        ),  # Format invalide
        (
            ["http://proxy.com:8080", "invalid_proxy"],
            [
                "Invalid proxy format: 'invalid_proxy'. Expected format: 'http[s]://host:port [user pass]' or 'socks5://host:port [user pass]'."
            ],
        ),  # Un valide, un invalide
    ],
)
def test_validate_proxies(validator, proxies, expected_errors):
    """Test validation of proxy settings."""
    errors = validator._validate_proxies(proxies=proxies)
    assert errors == expected_errors


# Tests pour _validate_browser_settings
@pytest.mark.parametrize(
    ("user_agent", "locale_timezone", "timezone_id", "expected_errors"),
    [
        ("Mozilla/5.0", "fr-FR", "Europe/Paris", []),  # Tous valides
        (None, None, None, []),  # Tous None
        (123, "fr-FR", "Europe/Paris", ["Invalid browser user agent format."]),  # user_agent invalide
        ("Mozilla/5.0", 123, "Europe/Paris", ["Invalid browser locale timezone format."]),  # locale_timezone invalide
        ("Mozilla/5.0", "fr-FR", 123, ["Invalid browser timezone ID format."]),  # timezone_id invalide
        (
            123,
            456,
            789,
            [
                "Invalid browser user agent format.",
                "Invalid browser locale timezone format.",
                "Invalid browser timezone ID format.",
            ],
        ),  # Tous invalides
    ],
)
def test_validate_browser_settings(validator, user_agent, locale_timezone, timezone_id, expected_errors):
    """Test validation of browser settings."""
    errors = validator._validate_browser_settings(
        user_agent=user_agent, locale_timezone=locale_timezone, timezone_id=timezone_id
    )
    assert errors == expected_errors


# Tests pour _validate_match_links
@pytest.mark.parametrize(
    ("match_links", "sport", "expected_errors"),
    [
        (None, "football", []),  # Pas de match_links
        ([], "football", []),  # Liste vide
        (["https://www.oddsportal.com/football/match/123456"], "football", []),  # Format valide
        (
            ["https://www.oddsportal.com/football/match/123456"],
            None,
            ["The '--sport' argument is required when using '--match_links'."],
        ),  # Sport manquant
        (["invalid_url_format"], "football", ["Invalid match link format: invalid_url_format"]),  # Format URL invalide
    ],
)
def test_validate_match_links(validator, match_links, sport, expected_errors):
    """Test validation of match links."""
    errors = validator._validate_match_links(match_links=match_links, sport=sport)
    assert errors == expected_errors


# Tests pour _validate_max_pages
@pytest.mark.parametrize(
    ("command", "max_pages", "expected_errors"),
    [
        ("scrape_historic", 5, []),  # Valide
        ("scrape_historic", 1, []),  # Valide (minimum)
        ("scrape_historic", None, []),  # Valide (non spécifié)
        ("scrape_historic", 0, ["Invalid max-pages value: '0'. It must be a positive integer."]),  # Invalide (zéro)
        (
            "scrape_historic",
            -1,
            ["Invalid max-pages value: '-1'. It must be a positive integer."],
        ),  # Invalide (négatif)
        (
            "scrape_historic",
            "5",
            ["Invalid max-pages value: '5'. It must be a positive integer."],
        ),  # Invalide (pas un entier)
        ("scrape_upcoming", 5, []),  # Autre commande, pas de validation
    ],
)
def test_validate_max_pages(validator, command, max_pages, expected_errors):
    """Test validation of max_pages parameter."""
    errors = validator._validate_max_pages(command=command, max_pages=max_pages)
    assert errors == expected_errors


# Test pour _validate_file_args avec chemin de fichier sans extension
def test_validate_file_args_no_extension(validator):
    """Test validation with file path having no extension."""
    args = MagicMock(file_path="data_file", format=None)
    errors = validator._validate_file_args(args=args)
    assert len(errors) == 1
    assert "File path 'data_file' must include a valid file extension" in errors[0]


# Test pour _validate_file_args avec format valide mais sans chemin de fichier
def test_validate_file_args_format_only(validator):
    """Test validation with format specified but no file path."""
    args = MagicMock(file_path=None, format="json")
    errors = validator._validate_file_args(args=args)
    assert not errors, "La validation devrait réussir avec format spécifié mais sans chemin de fichier"


# Test pour vérifier que les arguments match_links sont validés correctement
def test_validate_args_with_match_links(validator, mock_args):
    """Test validation d'arguments avec match_links."""
    # Configurer un scénario avec match_links
    mock_args.match_links = ["https://www.oddsportal.com/football/match/123456"]
    mock_args.sport = "football"
    mock_args.date = None  # La date n'est pas requise quand match_links est fourni

    # Cette validation devrait réussir
    try:
        validator.validate_args(mock_args)
    except ValueError as e:
        pytest.fail(f"Unexpected ValueError: {e}")


# Test pour le target_bookmaker
def test_validate_target_bookmaker(validator, mock_args):
    """Test validation du target_bookmaker."""
    # Valide
    mock_args.target_bookmaker = "Bookmaker1"
    validator.validate_args(mock_args)

    # Invalide
    mock_args.target_bookmaker = 123  # Non-string
    with pytest.raises(ValueError, match="Target bookmaker must be a string if specified."):
        validator.validate_args(mock_args)


# Test pour scrape_odds_history
def test_validate_scrape_odds_history(validator, mock_args):
    """Test validation du flag scrape_odds_history."""
    # Valide
    mock_args.scrape_odds_history = True
    validator.validate_args(mock_args)

    # Invalide
    mock_args.scrape_odds_history = "yes"  # Non-boolean
    with pytest.raises(ValueError, match="'--scrape-odds-history' must be a boolean flag."):
        validator.validate_args(mock_args)
