"""
Custom exception hierarchy for the scraper.

This module provides a hierarchy of exceptions to distinguish between
different types of scraping failures and enable targeted error handling.
"""

from oddsharvester.core.scrape_result import ErrorType
from oddsharvester.utils.constants import RATE_LIMIT_RETRY_DELAY_S


class ScraperError(Exception):
    """Base class for all scraper exceptions."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        is_retryable: bool = True,
        error_type: ErrorType | None = None,
    ):
        super().__init__(message)
        self.url = url
        self.is_retryable = is_retryable
        self.error_type = error_type
        self.message = message

    def __str__(self) -> str:
        if self.url:
            return f"{self.message} (url: {self.url})"
        return self.message


class ParsingError(ScraperError):
    """
    Error parsing page content.

    Includes HTML structure changes, missing elements, and JSON decode errors.
    These errors are typically not retryable as the page structure has changed.
    """

    def __init__(self, message: str, url: str):
        super().__init__(message, url, is_retryable=False)


class RateLimitError(ScraperError):
    """
    Rate limiting detected.

    The server has returned a rate limit response (e.g., 429 Too Many Requests).
    These errors are retryable after waiting.
    """

    def __init__(self, message: str, url: str, retry_after: float = RATE_LIMIT_RETRY_DELAY_S):
        super().__init__(message, url, is_retryable=True, error_type=ErrorType.RATE_LIMITED)
        self.retry_after = retry_after


class PageNotFoundError(ScraperError):
    """
    Page not found (404) or unavailable.

    The requested page does not exist or has been removed.
    These errors are not retryable.
    """

    def __init__(self, message: str, url: str):
        super().__init__(message, url, is_retryable=False)


class SeasonNotFoundError(PageNotFoundError):
    """The requested season does not exist under this league slug; OddsPortal redirected it."""


class AllProxiesExhaustedError(ScraperError):
    """Raised when every proxy in the rotation pool has been blacklisted.

    Signals that no healthy IP remains for further requests.
    """


class H2HFragmentResolutionError(ScraperError):
    """The match view never rendered: no market tab appeared within any hydration attempt.

    Raised by hydrate_match_view for any match URL, with or without a fragment. Retryable, and typed
    HEADER_NOT_FOUND so proxy failover does not count it against the IP.
    """

    def __init__(self, message: str, url: str | None = None):
        super().__init__(message, url, is_retryable=True, error_type=ErrorType.HEADER_NOT_FOUND)


class MatchContentError(ScraperError):
    """The match page loaded but its content could not be read.

    Retryable, and typed by the raiser: classifying the message would turn a DOM timeout into a
    proxy-attributable navigation failure.
    """

    def __init__(self, message: str, url: str | None = None, error_type: ErrorType = ErrorType.PARSING):
        super().__init__(message, url, is_retryable=True, error_type=error_type)


class MarketDataError(MatchContentError):
    """OddsPortal did not deliver the data of the market or period view switched to: the table would not show it.

    Raised through every market-level catch: a record read past it would carry another market's odds.
    """

    def __init__(self, message: str, url: str | None = None):
        super().__init__(message, url, error_type=ErrorType.MARKET_EXTRACTION)
