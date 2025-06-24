from unittest.mock import patch

import pytest

from src.utils.proxy_manager import ProxyManager


@pytest.fixture
def proxy_list():
    return ["http://proxy1.com:8080 user1 pass1", "http://proxy2.com:8080 user2 pass2"]


@pytest.fixture
def proxy_manager(proxy_list):
    return ProxyManager(cli_proxies=proxy_list)


def test_parse_proxies_valid(proxy_manager):
    expected_proxies = [
        {"server": "http://proxy1.com:8080", "username": "user1", "password": "pass1"},  # pragma: allowlist secret
        {"server": "http://proxy2.com:8080", "username": "user2", "password": "pass2"},  # pragma: allowlist secret
    ]
    assert proxy_manager.proxies == expected_proxies


def test_parse_proxies_invalid_format():
    invalid_proxies = ["invalid_proxy_format", "http://proxy3.com:8080 user_only"]

    with patch("src.utils.proxy_manager.logging.getLogger") as mock_logger:
        proxy_manager = ProxyManager(cli_proxies=invalid_proxies)
        assert proxy_manager.proxies == []
        assert mock_logger.return_value.error.called


def test_no_proxies_logs_warning():
    with patch("src.utils.proxy_manager.logging.getLogger") as mock_logger:
        proxy_manager = ProxyManager(cli_proxies=None)
        assert proxy_manager.proxies == []
        mock_logger.return_value.info.assert_called_with("No proxies provided, running without proxy.")


def test_get_current_proxy(proxy_manager):
    assert proxy_manager.get_current_proxy() == {
        "server": "http://proxy1.com:8080",
        "username": "user1",
        "password": "pass1",  # pragma: allowlist secret
    }


def test_get_current_proxy_no_proxies():
    proxy_manager = ProxyManager(cli_proxies=None)
    assert proxy_manager.get_current_proxy() is None


def test_rotate_proxy(proxy_manager):
    # First proxy
    assert proxy_manager.get_current_proxy() == {
        "server": "http://proxy1.com:8080",
        "username": "user1",
        "password": "pass1",  # pragma: allowlist secret
    }

    # Rotate once
    proxy_manager.rotate_proxy()
    assert proxy_manager.get_current_proxy() == {
        "server": "http://proxy2.com:8080",
        "username": "user2",
        "password": "pass2",  # pragma: allowlist secret
    }

    # Rotate again (should wrap around)
    proxy_manager.rotate_proxy()
    assert proxy_manager.get_current_proxy() == {
        "server": "http://proxy1.com:8080",
        "username": "user1",
        "password": "pass1",  # pragma: allowlist secret
    }


def test_rotate_proxy_no_proxies():
    with patch("src.utils.proxy_manager.logging.getLogger") as mock_logger:
        proxy_manager = ProxyManager(cli_proxies=None)
        proxy_manager.rotate_proxy()
        assert proxy_manager.get_current_proxy() is None
        mock_logger.return_value.warning.assert_called_with("No proxies available to rotate. Running without proxy.")


def test_logging_on_rotation(proxy_manager):
    with patch.object(proxy_manager.logger, "info") as mock_info:
        proxy_manager.rotate_proxy()
        expected_log_message = f"Rotated to new proxy: {proxy_manager.get_current_proxy()}"
        mock_info.assert_called_with(expected_log_message)
