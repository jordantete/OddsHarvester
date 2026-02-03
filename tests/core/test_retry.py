"""Tests for retry module."""

import pytest

from oddsharvester.core.retry import (
    RetryConfig,
    classify_error,
    is_retryable_error,
    retry_with_backoff,
)
from oddsharvester.core.scrape_result import ErrorType


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 2.0
        assert config.max_delay == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter_factor == 0.1

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(max_attempts=5, base_delay=1.0, max_delay=60.0)
        assert config.max_attempts == 5
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    @pytest.mark.parametrize(
        "error_message",
        [
            "ERR_CONNECTION_RESET",
            "ERR_CONNECTION_TIMED_OUT",
            "ERR_NAME_NOT_RESOLVED",
            "ERR_PROXY_CONNECTION_FAILED",
            "Timeout waiting for element",
            "Navigation timeout of 30000ms exceeded",
            "TimeoutError: Waiting failed",
            "net::ERR_FAILED",
            "Target closed",
        ],
    )
    def test_retryable_errors(self, error_message):
        """Test that transient errors are marked as retryable."""
        assert is_retryable_error(error_message) is True

    @pytest.mark.parametrize(
        "error_message",
        [
            "Element not found",
            "Invalid selector",
            "JSON parse error",
            "Unexpected token",
            "",
        ],
    )
    def test_non_retryable_errors(self, error_message):
        """Test that non-transient errors are not retryable."""
        assert is_retryable_error(error_message) is False


class TestClassifyError:
    """Tests for classify_error function."""

    def test_navigation_errors(self):
        """Test classification of navigation errors."""
        assert classify_error("Connection timeout") == ErrorType.NAVIGATION
        assert classify_error("Navigation failed") == ErrorType.NAVIGATION
        assert classify_error("Network error occurred") == ErrorType.NAVIGATION
        assert classify_error("Proxy connection failed") == ErrorType.NAVIGATION

    def test_header_not_found_errors(self):
        """Test classification of header not found errors."""
        assert classify_error("react-event-header not found") == ErrorType.HEADER_NOT_FOUND
        assert classify_error("Header element missing") == ErrorType.HEADER_NOT_FOUND
        assert classify_error("Selector not found on page") == ErrorType.HEADER_NOT_FOUND

    def test_parsing_errors(self):
        """Test classification of parsing errors."""
        assert classify_error("JSON decode error") == ErrorType.PARSING
        assert classify_error("Failed to parse HTML") == ErrorType.PARSING
        assert classify_error("lxml parsing failed") == ErrorType.PARSING

    def test_market_extraction_errors(self):
        """Test classification of market extraction errors."""
        assert classify_error("Market extraction failed") == ErrorType.MARKET_EXTRACTION
        assert classify_error("Failed to extract odds from market") == ErrorType.MARKET_EXTRACTION

    def test_rate_limit_errors(self):
        """Test classification of rate limit errors."""
        assert classify_error("429 Too Many Requests") == ErrorType.RATE_LIMITED
        assert classify_error("Rate limit exceeded") == ErrorType.RATE_LIMITED

    def test_page_not_found_errors(self):
        """Test classification of page not found errors."""
        assert classify_error("404 Not Found") == ErrorType.PAGE_NOT_FOUND
        assert classify_error("Page unavailable") == ErrorType.PAGE_NOT_FOUND

    def test_unknown_errors(self):
        """Test classification of unknown errors."""
        assert classify_error("Some random error") == ErrorType.UNKNOWN
        assert classify_error(None) == ErrorType.UNKNOWN
        assert classify_error("") == ErrorType.UNKNOWN


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test successful execution on first attempt."""

        async def successful_func():
            return "success"

        result = await retry_with_backoff(successful_func)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1
        assert result.last_error is None
        assert result.error_type is None

    @pytest.mark.asyncio
    async def test_retry_on_transient_error(self):
        """Test retry behavior on transient errors."""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("ERR_CONNECTION_RESET")
            return "success after retry"

        config = RetryConfig(max_attempts=3, base_delay=0.01)  # Fast delay for tests
        result = await retry_with_backoff(flaky_func, config=config)

        assert result.success is True
        assert result.result == "success after retry"
        assert result.attempts == 2
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_permanent_error(self):
        """Test that permanent errors are not retried."""
        call_count = 0

        async def permanent_error_func():
            nonlocal call_count
            call_count += 1
            raise Exception("Element not found - not retryable")

        config = RetryConfig(max_attempts=3, base_delay=0.01)
        result = await retry_with_backoff(permanent_error_func, config=config)

        assert result.success is False
        assert result.attempts == 1
        assert call_count == 1
        assert "not retryable" in result.last_error

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded."""
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("ERR_CONNECTION_TIMED_OUT")

        config = RetryConfig(max_attempts=3, base_delay=0.01)
        result = await retry_with_backoff(always_fails, config=config)

        assert result.success is False
        assert result.attempts == 3
        assert call_count == 3
        assert "TIMED_OUT" in result.last_error

    @pytest.mark.asyncio
    async def test_function_with_arguments(self):
        """Test retry with function that takes arguments."""

        async def add_numbers(a, b, multiplier=1):
            return (a + b) * multiplier

        result = await retry_with_backoff(add_numbers, 2, 3, multiplier=2)

        assert result.success is True
        assert result.result == 10

    @pytest.mark.asyncio
    async def test_error_type_classification(self):
        """Test that error type is correctly classified."""

        async def nav_error():
            raise Exception("Navigation timeout")

        config = RetryConfig(max_attempts=1)
        result = await retry_with_backoff(nav_error, config=config)

        assert result.success is False
        assert result.error_type == ErrorType.NAVIGATION
