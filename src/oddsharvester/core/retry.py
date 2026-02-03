"""
Retry utilities with exponential backoff.

This module provides retry functionality for scraping operations,
with configurable backoff and error classification.
"""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
import random
from typing import Any

from oddsharvester.core.scrape_result import ErrorType

logger = logging.getLogger(__name__)

# Error keywords that indicate transient/retryable errors
TRANSIENT_ERROR_KEYWORDS = (
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_TIMED_OUT",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_SOCKS_CONNECTION_FAILED",
    "ERR_CERT_AUTHORITY_INVALID",
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_NETWORK_CHANGED",
    "Timeout",
    "net::ERR_FAILED",
    "net::ERR_CONNECTION_ABORTED",
    "net::ERR_INTERNET_DISCONNECTED",
    "Navigation timeout",
    "TimeoutError",
    "Target closed",
)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 2.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter_factor: float = 0.1


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    result: Any | None
    attempts: int
    last_error: str | None
    error_type: ErrorType | None


def is_retryable_error(error_message: str) -> bool:
    """
    Determine if an error is retryable based on its message.

    Args:
        error_message: The error message to check.

    Returns:
        True if the error is retryable, False otherwise.
    """
    if not error_message:
        return False
    return any(keyword in error_message for keyword in TRANSIENT_ERROR_KEYWORDS)


def classify_error(error_message: str | None) -> ErrorType:
    """
    Classify an error based on its message.

    Args:
        error_message: The error message to classify.

    Returns:
        The appropriate ErrorType.
    """
    if not error_message:
        return ErrorType.UNKNOWN

    error_lower = error_message.lower()

    if any(kw in error_lower for kw in ["timeout", "navigation", "connection", "network", "proxy"]):
        return ErrorType.NAVIGATION
    elif any(kw in error_lower for kw in ["react-event-header", "header", "selector not found"]):
        return ErrorType.HEADER_NOT_FOUND
    elif any(kw in error_lower for kw in ["parse", "json", "decode", "lxml", "beautifulsoup"]):
        return ErrorType.PARSING
    elif any(kw in error_lower for kw in ["market", "odds extraction"]):
        return ErrorType.MARKET_EXTRACTION
    elif any(kw in error_lower for kw in ["rate", "limit", "429", "too many"]):
        return ErrorType.RATE_LIMITED
    elif any(kw in error_lower for kw in ["404", "not found", "page unavailable"]):
        return ErrorType.PAGE_NOT_FOUND

    return ErrorType.UNKNOWN


async def retry_with_backoff[T](
    func: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    config: RetryConfig | None = None,
    **kwargs: Any,
) -> RetryResult:
    """
    Execute an async function with retry and exponential backoff.

    Args:
        func: The async function to execute.
        *args: Positional arguments to pass to the function.
        config: Retry configuration. Uses defaults if not provided.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        RetryResult containing the outcome and metadata.
    """
    if config is None:
        config = RetryConfig()

    last_error: str | None = None
    error_type: ErrorType | None = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            result = await func(*args, **kwargs)
            return RetryResult(
                success=True,
                result=result,
                attempts=attempt,
                last_error=None,
                error_type=None,
            )

        except Exception as e:
            last_error = str(e)
            error_type = classify_error(last_error)
            is_retryable = is_retryable_error(last_error)

            if not is_retryable or attempt == config.max_attempts:
                logger.debug(f"Attempt {attempt}/{config.max_attempts} failed (not retrying): {last_error[:100]}")
                return RetryResult(
                    success=False,
                    result=None,
                    attempts=attempt,
                    last_error=last_error,
                    error_type=error_type,
                )

            # Calculate delay with exponential backoff and jitter
            delay = min(
                config.base_delay * (config.exponential_base ** (attempt - 1)),
                config.max_delay,
            )
            jitter = delay * config.jitter_factor * random.random()  # noqa: S311
            total_delay = delay + jitter

            logger.debug(
                f"Attempt {attempt}/{config.max_attempts} failed: {last_error[:100]}. Retrying in {total_delay:.1f}s..."
            )
            await asyncio.sleep(total_delay)

    # Should not reach here, but handle it anyway
    return RetryResult(
        success=False,
        result=None,
        attempts=config.max_attempts,
        last_error=last_error,
        error_type=error_type,
    )
