"""Tests for the ProxyManager class."""

from unittest.mock import patch

import pytest

from oddsharvester.utils.proxy_manager import ProxyManager


class TestProxyManagerBasics:
    """Test basic proxy configuration."""

    def test_no_proxy_configured(self):
        """Test that no proxy returns None."""
        proxy_manager = ProxyManager()
        assert proxy_manager.get_proxy() is None

    def test_proxy_url_only(self):
        """Test proxy with URL only (no auth)."""
        proxy_manager = ProxyManager(proxy_url="http://proxy.example.com:8080")
        expected = {"server": "http://proxy.example.com:8080"}
        assert proxy_manager.get_proxy() == expected

    def test_proxy_with_authentication(self):
        """Test proxy with full authentication."""
        proxy_manager = ProxyManager(
            proxy_url="http://proxy.example.com:8080",
            proxy_user="testuser",
            proxy_pass="testpass",
        )
        expected = {
            "server": "http://proxy.example.com:8080",
            "username": "testuser",
            "password": "testpass",
        }
        assert proxy_manager.get_proxy() == expected

    def test_proxy_with_partial_auth_ignored(self):
        """Test that partial auth (only user or only pass) is ignored."""
        # Only user provided
        pm1 = ProxyManager(proxy_url="http://proxy.example.com:8080", proxy_user="testuser")
        assert pm1.get_proxy() == {"server": "http://proxy.example.com:8080"}

        # Only pass provided
        pm2 = ProxyManager(proxy_url="http://proxy.example.com:8080", proxy_pass="testpass")
        assert pm2.get_proxy() == {"server": "http://proxy.example.com:8080"}


class TestProxySchemes:
    """Test different proxy schemes."""

    @pytest.mark.parametrize(
        "scheme",
        ["http://", "https://", "socks4://", "socks5://"],
    )
    def test_valid_schemes(self, scheme):
        """Test all valid proxy schemes."""
        proxy_url = f"{scheme}proxy.example.com:8080"
        proxy_manager = ProxyManager(proxy_url=proxy_url)
        assert proxy_manager.get_proxy() == {"server": proxy_url}

    def test_invalid_scheme(self):
        """Test invalid proxy scheme returns None."""
        proxy_manager = ProxyManager(proxy_url="ftp://proxy.example.com:8080")
        assert proxy_manager.get_proxy() is None


class TestProxyLogging:
    """Test proxy logging behavior."""

    def test_no_proxy_logs_info(self):
        """Test that no proxy configuration logs info message."""
        with patch("oddsharvester.utils.proxy_manager.logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            ProxyManager()
            mock_logger.info.assert_called_with("No proxy provided, running without proxy.")

    def test_proxy_with_auth_logs_info(self):
        """Test that proxy with auth logs appropriate message."""
        with patch("oddsharvester.utils.proxy_manager.logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            ProxyManager(
                proxy_url="http://proxy.example.com:8080",
                proxy_user="user",
                proxy_pass="pass",
            )
            mock_logger.info.assert_called_with("Configured proxy with authentication: http://proxy.example.com:8080")

    def test_proxy_without_auth_logs_info(self):
        """Test that proxy without auth logs appropriate message."""
        with patch("oddsharvester.utils.proxy_manager.logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            ProxyManager(proxy_url="http://proxy.example.com:8080")
            mock_logger.info.assert_called_with(
                "Configured proxy without authentication: http://proxy.example.com:8080"
            )

    def test_partial_auth_logs_warning(self):
        """Test that partial auth logs a warning."""
        with patch("oddsharvester.utils.proxy_manager.logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            ProxyManager(proxy_url="http://proxy.example.com:8080", proxy_user="user")
            mock_logger.warning.assert_called_with(
                "Both proxy_user and proxy_pass must be provided for authentication. Ignoring auth."
            )


class TestLegacyMethods:
    """Test legacy methods for backwards compatibility."""

    def test_get_current_proxy_is_alias(self):
        """Test that get_current_proxy returns same as get_proxy."""
        proxy_manager = ProxyManager(proxy_url="http://proxy.example.com:8080")
        assert proxy_manager.get_current_proxy() == proxy_manager.get_proxy()

    def test_rotate_proxy_is_noop(self):
        """Test that rotate_proxy doesn't crash."""
        proxy_manager = ProxyManager(proxy_url="http://proxy.example.com:8080")
        proxy_manager.rotate_proxy()  # Should not raise
        # Proxy should remain the same
        assert proxy_manager.get_proxy() == {"server": "http://proxy.example.com:8080"}
