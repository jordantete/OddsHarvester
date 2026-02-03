"""Tests for custom exceptions module."""

from oddsharvester.core.exceptions import (
    MarketExtractionError,
    NavigationError,
    PageNotFoundError,
    ParsingError,
    PartialDataError,
    RateLimitError,
    ScraperError,
)


class TestScraperError:
    """Tests for base ScraperError."""

    def test_create_scraper_error(self):
        """Test creating a ScraperError."""
        error = ScraperError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.url is None
        assert error.is_retryable is True

    def test_scraper_error_with_url(self):
        """Test ScraperError with URL."""
        error = ScraperError("Error occurred", url="https://example.com/match")
        assert str(error) == "Error occurred (url: https://example.com/match)"
        assert error.url == "https://example.com/match"

    def test_scraper_error_not_retryable(self):
        """Test non-retryable ScraperError."""
        error = ScraperError("Permanent error", is_retryable=False)
        assert error.is_retryable is False


class TestNavigationError:
    """Tests for NavigationError."""

    def test_create_navigation_error(self):
        """Test creating a NavigationError."""
        error = NavigationError("Connection timeout", url="https://example.com")
        assert error.message == "Connection timeout"
        assert error.url == "https://example.com"
        assert error.is_retryable is True  # Navigation errors are retryable

    def test_navigation_error_is_scraper_error(self):
        """Test that NavigationError is a ScraperError."""
        error = NavigationError("Timeout", url="https://example.com")
        assert isinstance(error, ScraperError)


class TestParsingError:
    """Tests for ParsingError."""

    def test_create_parsing_error(self):
        """Test creating a ParsingError."""
        error = ParsingError("Invalid HTML structure", url="https://example.com")
        assert error.message == "Invalid HTML structure"
        assert error.is_retryable is False  # Parsing errors are not retryable

    def test_parsing_error_is_scraper_error(self):
        """Test that ParsingError is a ScraperError."""
        error = ParsingError("Parse failed", url="https://example.com")
        assert isinstance(error, ScraperError)


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_create_rate_limit_error(self):
        """Test creating a RateLimitError."""
        error = RateLimitError("Too many requests", url="https://example.com", retry_after=120)
        assert error.message == "Too many requests"
        assert error.retry_after == 120
        assert error.is_retryable is True

    def test_rate_limit_error_default_retry_after(self):
        """Test default retry_after value."""
        error = RateLimitError("429", url="https://example.com")
        assert error.retry_after == 60


class TestPageNotFoundError:
    """Tests for PageNotFoundError."""

    def test_create_page_not_found_error(self):
        """Test creating a PageNotFoundError."""
        error = PageNotFoundError("Page does not exist", url="https://example.com/missing")
        assert error.message == "Page does not exist"
        assert error.is_retryable is False  # 404 errors are not retryable


class TestPartialDataError:
    """Tests for PartialDataError."""

    def test_create_partial_data_error(self):
        """Test creating a PartialDataError."""
        partial_data = {"home_team": "Team A", "away_team": "Team B"}
        error = PartialDataError(
            "Missing market data",
            url="https://example.com/match",
            partial_data=partial_data,
        )
        assert error.message == "Missing market data"
        assert error.partial_data == partial_data
        assert error.is_retryable is False


class TestMarketExtractionError:
    """Tests for MarketExtractionError."""

    def test_create_market_extraction_error(self):
        """Test creating a MarketExtractionError."""
        error = MarketExtractionError("Failed to extract odds", url="https://example.com")
        assert error.message == "Failed to extract odds"
        assert error.is_retryable is True  # Default is retryable

    def test_market_extraction_error_not_retryable(self):
        """Test non-retryable MarketExtractionError."""
        error = MarketExtractionError(
            "Market not supported",
            url="https://example.com",
            is_retryable=False,
        )
        assert error.is_retryable is False


class TestExceptionHierarchy:
    """Tests for exception hierarchy and catching."""

    def test_all_exceptions_are_scraper_errors(self):
        """Test that all custom exceptions inherit from ScraperError."""
        errors = [
            NavigationError("nav", url="url"),
            ParsingError("parse", url="url"),
            RateLimitError("rate", url="url"),
            PageNotFoundError("404", url="url"),
            PartialDataError("partial", url="url", partial_data={}),
            MarketExtractionError("market", url="url"),
        ]

        for error in errors:
            assert isinstance(error, ScraperError)

    def test_exception_attributes_preserved(self):
        """Test that exception attributes are preserved when caught."""
        error = RateLimitError("Rate limited", url="https://example.com", retry_after=30)
        assert error.url == "https://example.com"
        assert hasattr(error, "retry_after")
        assert error.retry_after == 30
