"""Tests for the ProxyManager class."""

from unittest.mock import patch

import pytest

from oddsharvester.utils.proxy_manager import PROXY_CONSECUTIVE_FAILURE_THRESHOLD, ProxyEntry, ProxyManager


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


class TestUrlSanitization:
    """Test that URLs with embedded credentials are sanitized for logging."""

    def test_sanitize_url_strips_credentials(self):
        """Test that embedded user:pass is stripped from URL."""
        sanitized = ProxyManager._sanitize_url_for_logging("http://user:secret@proxy.example.com:8080")
        assert "user" not in sanitized
        assert "secret" not in sanitized
        assert "proxy.example.com:8080" in sanitized

    def test_sanitize_url_preserves_clean_url(self):
        """Test that a URL without credentials is unchanged."""
        url = "http://proxy.example.com:8080"
        assert ProxyManager._sanitize_url_for_logging(url) == url

    def test_embedded_credentials_not_logged(self):
        """Test that embedded credentials in proxy URL are never logged."""
        with patch("oddsharvester.utils.proxy_manager.logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            ProxyManager(proxy_url="http://user:secret@proxy.example.com:8080")
            for call in mock_logger.info.call_args_list:
                assert "secret" not in str(call)

    def test_invalid_scheme_does_not_log_url(self):
        """Test that invalid scheme error does not leak the URL."""
        with patch("oddsharvester.utils.proxy_manager.logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            ProxyManager(proxy_url="ftp://user:secret@proxy.example.com:8080")
            mock_logger.error.assert_called_with("Invalid proxy scheme provided.")


class TestProxyLogging:
    """Test proxy logging behavior."""

    def test_no_proxy_logs_info(self):
        """Test that no proxy configuration logs info message."""
        with patch("oddsharvester.utils.proxy_manager.logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            ProxyManager()
            mock_logger.info.assert_called_with("No proxy provided, running without proxy.")

    def test_proxy_with_auth_logs_info(self):
        """Test that proxy with auth logs URL without credentials."""
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


class TestMultiProxyPool:
    def test_empty_pool_is_direct(self):
        pm = ProxyManager()
        assert pm.is_multi_proxy() is False
        assert pm.launch_proxy() is None
        entry = pm.next_proxy()
        assert entry.config is None

    def test_single_proxy_launches_with_that_proxy(self):
        pm = ProxyManager(proxy_urls=["http://proxy.example.com:8080"])
        assert pm.is_multi_proxy() is False
        assert pm.launch_proxy() == {"server": "http://proxy.example.com:8080"}

    def test_multiple_proxies_launch_per_context(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        assert pm.is_multi_proxy() is True
        assert pm.launch_proxy() == {"server": "per-context"}

    def test_embedded_credentials_split_into_username_password(self):
        pm = ProxyManager(proxy_urls=["http://user:pass@a.example.com:8080"])
        entry = pm.entries[0]
        assert entry.config == {
            "server": "http://a.example.com:8080",
            "username": "user",
            "password": "pass",
        }

    def test_round_robin_cycles_entries(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        keys = [pm.next_proxy().key for _ in range(4)]
        assert keys == [
            "http://a.example.com:1",
            "http://b.example.com:2",
            "http://a.example.com:1",
            "http://b.example.com:2",
        ]

    def test_blacklist_after_threshold_skips_proxy(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        key_a = "http://a.example.com:1"
        for _ in range(PROXY_CONSECUTIVE_FAILURE_THRESHOLD):
            pm.report_result(key_a, is_proxy_failure=True)
        keys = {pm.next_proxy().key for _ in range(4)}
        assert keys == {"http://b.example.com:2"}

    def test_success_resets_failure_counter(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        key_a = "http://a.example.com:1"
        pm.report_result(key_a, is_proxy_failure=True)
        pm.report_result(key_a, is_proxy_failure=True)
        pm.report_result(key_a, is_proxy_failure=False)  # reset
        pm.report_result(key_a, is_proxy_failure=True)
        # Only 1 consecutive failure since reset -> not blacklisted
        assert any(e.key == key_a and not e.blacklisted for e in pm.entries)

    def test_all_blacklisted_returns_none(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1", "http://b.example.com:2"])
        for key in ["http://a.example.com:1", "http://b.example.com:2"]:
            for _ in range(PROXY_CONSECUTIVE_FAILURE_THRESHOLD):
                pm.report_result(key, is_proxy_failure=True)
        assert pm.next_proxy() is None

    def test_single_proxy_never_blacklists(self):
        pm = ProxyManager(proxy_urls=["http://a.example.com:1"])
        for _ in range(PROXY_CONSECUTIVE_FAILURE_THRESHOLD * 3):
            pm.report_result("http://a.example.com:1", is_proxy_failure=True)
        assert pm.next_proxy().key == "http://a.example.com:1"

    def test_multi_proxy_user_pass_ignored_with_warning(self):
        from unittest.mock import patch

        with patch("oddsharvester.utils.proxy_manager.logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            ProxyManager(
                proxy_urls=["http://a.example.com:1", "http://b.example.com:2"],
                proxy_user="u",
                proxy_pass="p",
            )
            assert any("ignored with multiple proxies" in str(call) for call in mock_logger.warning.call_args_list)

    def test_entry_dataclass_defaults(self):
        entry = ProxyEntry(key="k", config=None)
        assert entry.consecutive_failures == 0
        assert entry.blacklisted is False
