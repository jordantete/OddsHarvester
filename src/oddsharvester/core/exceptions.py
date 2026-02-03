"""
Custom exception hierarchy for the scraper.

This module provides a hierarchy of exceptions to distinguish between
different types of scraping failures and enable targeted error handling.
"""


class ScraperError(Exception):
    """Base class for all scraper exceptions."""

    def __init__(self, message: str, url: str | None = None, is_retryable: bool = True):
        super().__init__(message)
        self.url = url
        self.is_retryable = is_retryable
        self.message = message

    def __str__(self) -> str:
        if self.url:
            return f"{self.message} (url: {self.url})"
        return self.message


class NavigationError(ScraperError):
    """
    Error during page navigation.

    Includes timeouts, connection errors, and other network-related failures.
    These errors are typically retryable.
    """

    def __init__(self, message: str, url: str):
        super().__init__(message, url, is_retryable=True)


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

    def __init__(self, message: str, url: str, retry_after: int = 60):
        super().__init__(message, url, is_retryable=True)
        self.retry_after = retry_after


class PageNotFoundError(ScraperError):
    """
    Page not found (404) or unavailable.

    The requested page does not exist or has been removed.
    These errors are not retryable.
    """

    def __init__(self, message: str, url: str):
        super().__init__(message, url, is_retryable=False)


class PartialDataError(ScraperError):
    """
    Partial data was retrieved.

    Some data was successfully extracted but not all requested information
    is available (e.g., missing markets). The partial data is attached.
    """

    def __init__(self, message: str, url: str, partial_data: dict):
        super().__init__(message, url, is_retryable=False)
        self.partial_data = partial_data


class MarketExtractionError(ScraperError):
    """
    Error extracting market data.

    The match details were retrieved but market extraction failed.
    May be retryable depending on the cause.
    """

    def __init__(self, message: str, url: str, is_retryable: bool = True):
        super().__init__(message, url, is_retryable=is_retryable)
