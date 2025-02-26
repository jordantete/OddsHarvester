import pytest
from unittest.mock import patch
from src.utils.setup_proxy import setup_proxy_config

@pytest.fixture
def mock_logger():
    with patch("src.utils.setup_proxy.logger") as mock_logger:
        yield mock_logger

def test_setup_proxy_no_proxy_provided(mock_logger):
    result = setup_proxy_config(None)
    assert result is None
    mock_logger.info.assert_called_once_with("No proxy configuration provided. Proceeding without proxy.")

def test_setup_proxy_missing_server_key(mock_logger):
    result = setup_proxy_config({"username": "user", "password": "pass"})
    assert result is None
    mock_logger.info.assert_called_once_with("No proxy configuration provided. Proceeding without proxy.")

def test_setup_proxy_with_server_only(mock_logger):
    proxy = {"server": "http://proxy-server:8080"}
    result = setup_proxy_config(proxy)
    
    assert result == {"server": "http://proxy-server:8080"}
    mock_logger.info.assert_called_once_with("Using proxy server: http://proxy-server:8080")

def test_setup_proxy_with_full_credentials(mock_logger):
    proxy = {
        "server": "http://proxy-server:8080",
        "username": "user123",
        "password": "securePass!"
    }
    result = setup_proxy_config(proxy)

    expected = {
        "server": "http://proxy-server:8080",
        "username": "user123",
        "password": "securePass!"
    }
    assert result == expected
    mock_logger.info.assert_called_once_with("Using proxy server: http://proxy-server:8080")