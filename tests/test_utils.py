import os, pytest
from unittest.mock import patch, mock_open
from utils.utils import build_response, get_football_league_url, is_running_in_docker, ensure_directory_exists, parse_over_under_market, setup_proxy_config
from utils.constants import FOOTBALL_LEAGUES_URLS_MAPPING
from src.core.over_under_market import OverUnderMarket

@pytest.fixture
def mock_footbal_leagues():
    """Mock football leagues mapping."""
    return {
        "premier-league": "https://example.com/premier-league",
        "la-liga": "https://example.com/la-liga"
    }

def test_build_response():
    """Test building a consistent response."""
    result = build_response(200, "Success")
    assert result == {"statusCode": 200, "body": "Success"}

def test_get_football_league_url_success(mock_footbal_leagues):
    """Test retrieving a valid football league URL."""
    with patch("utils.constants.FOOTBALL_LEAGUES_URLS_MAPPING", mock_footbal_leagues):
        url = get_football_league_url("england-premier-league")
        assert url == "https://www.oddsportal.com/football/england/premier-league"

def test_get_football_league_url_invalid(mock_footbal_leagues):
    """Test retrieving an invalid football league URL."""
    with patch("utils.constants.FOOTBALL_LEAGUES_URLS_MAPPING", mock_footbal_leagues):
        with pytest.raises(ValueError, match="Invalid football league 'invalid-league'."):
            get_football_league_url("invalid-league")

def test_is_running_in_docker_when_true():
    """Test detection of running in a Docker container when /.dockerenv exists."""
    with patch("os.path.exists", return_value=True):
        assert is_running_in_docker() is True

def test_is_running_in_docker_when_false():
    """Test detection of running in a Docker container when /.dockerenv does not exist."""
    with patch("os.path.exists", return_value=False):
        assert is_running_in_docker() is False

def test_ensure_directory_exists():
    """Test ensuring a directory exists."""
    test_path = "/path/to/file.txt"
    with patch("os.makedirs") as mock_makedirs, patch("os.path.exists", return_value=False):
        ensure_directory_exists(test_path)
        mock_makedirs.assert_called_once_with("/path/to")

def test_ensure_directory_exists_already_exists():
    """Test ensuring a directory already exists."""
    test_path = "/path/to/file.txt"
    with patch("os.makedirs") as mock_makedirs, patch("os.path.exists", return_value=True):
        ensure_directory_exists(test_path)
        mock_makedirs.assert_not_called()

def test_parse_over_under_market_valid():
    """Test parsing a valid Over/Under market."""
    arg = "over_under_1_5"
    result = parse_over_under_market(arg)
    assert result == OverUnderMarket("1.5")

def test_parse_over_under_market_invalid():
    """Test parsing an invalid Over/Under market."""
    arg = "invalid_market"
    with pytest.raises(ValueError, match="Invalid Over/Under market argument: invalid_market."):
        parse_over_under_market(arg)

def test_setup_proxy_config_with_full_config():
    """Test setting up a proxy configuration with full details."""
    proxy = {
        "server": "http://proxy-server:8080",
        "username": "user",
        "password": "pass"
    }
    result = setup_proxy_config(proxy)
    assert result == {
        "server": "http://proxy-server:8080",
        "username": "user",
        "password": "pass"
    }

def test_setup_proxy_config_without_auth():
    """Test setting up a proxy configuration without authentication."""
    proxy = {"server": "http://proxy-server:8080"}
    result = setup_proxy_config(proxy)
    assert result == {"server": "http://proxy-server:8080"}

def test_setup_proxy_config_no_proxy():
    """Test setting up a proxy configuration when no proxy is provided."""
    result = setup_proxy_config(None)
    assert result is None