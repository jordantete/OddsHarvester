"""Tests for custom exceptions module."""

from oddsharvester.core.exceptions import (
    AllProxiesExhaustedError,
    MatchContentError,
    PageNotFoundError,
    ParsingError,
    RateLimitError,
    ScraperError,
)
from oddsharvester.core.scrape_result import ErrorType
from oddsharvester.utils.constants import RATE_LIMIT_RETRY_DELAY_S


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

    def test_rate_limit_error_waits_the_rate_limit_delay_by_default(self):
        """A caller that gives no retry_after gets the delay every raise in the scraper passes."""
        error = RateLimitError("429", url="https://example.com")
        assert error.retry_after == RATE_LIMIT_RETRY_DELAY_S


class TestPageNotFoundError:
    """Tests for PageNotFoundError."""

    def test_create_page_not_found_error(self):
        """Test creating a PageNotFoundError."""
        error = PageNotFoundError("Page does not exist", url="https://example.com/missing")
        assert error.message == "Page does not exist"
        assert error.is_retryable is False  # 404 errors are not retryable


class TestExceptionHierarchy:
    """Tests for exception hierarchy and catching."""

    def test_all_exceptions_are_scraper_errors(self):
        """Test that all custom exceptions inherit from ScraperError."""
        errors = [
            ParsingError("parse", url="url"),
            RateLimitError("rate", url="url"),
            PageNotFoundError("404", url="url"),
        ]

        for error in errors:
            assert isinstance(error, ScraperError)

    def test_exception_attributes_preserved(self):
        """Test that exception attributes are preserved when caught."""
        error = RateLimitError("Rate limited", url="https://example.com", retry_after=30)
        assert error.url == "https://example.com"
        assert hasattr(error, "retry_after")
        assert error.retry_after == 30


class TestAllProxiesExhaustedError:
    def test_is_scraper_error(self):
        assert issubclass(AllProxiesExhaustedError, ScraperError)

    def test_message_preserved(self):
        err = AllProxiesExhaustedError("all proxies blacklisted")
        assert str(err) == "all proxies blacklisted"


class TestH2HFragmentResolutionError:
    def test_is_retryable_and_typed_as_header_not_found(self):
        from oddsharvester.core.exceptions import H2HFragmentResolutionError
        from oddsharvester.core.scrape_result import ErrorType

        error = H2HFragmentResolutionError(
            "H2H fragment resolution failed after retry: requested=WbDmMwm1",
            url="https://www.oddsportal.com/football/h2h/a/b/#WbDmMwm1",
        )

        assert error.is_retryable is True
        assert error.error_type is ErrorType.HEADER_NOT_FOUND

    def test_is_not_proxy_attributable(self):
        """A client-side render race must never blacklist the proxy that served the page."""
        from oddsharvester.core.exceptions import H2HFragmentResolutionError
        from oddsharvester.core.retry import is_proxy_attributable_error

        error = H2HFragmentResolutionError("boom")

        assert is_proxy_attributable_error(error.error_type) is False

    def test_base_scraper_error_defaults_error_type_to_none(self):
        from oddsharvester.core.exceptions import ScraperError

        assert ScraperError("boom").error_type is None


def test_match_content_error_is_retryable_and_typed_by_the_caller():
    error = MatchContentError("boom", url="https://x/")
    typed = MatchContentError("no header", url="https://x/", error_type=ErrorType.HEADER_NOT_FOUND)

    assert error.is_retryable is True
    assert error.error_type is ErrorType.PARSING
    assert typed.error_type is ErrorType.HEADER_NOT_FOUND
