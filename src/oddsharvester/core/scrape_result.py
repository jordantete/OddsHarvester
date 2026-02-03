"""
Scrape result data structures for tracking scraping outcomes.

This module provides dataclasses to encapsulate scraping results with
detailed error tracking, enabling callers to programmatically handle
failures and generate reports.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ErrorType(Enum):
    """Classification of scraping errors."""

    NAVIGATION = "navigation"  # Timeout, connection errors
    PARSING = "parsing"  # HTML structure parsing failures
    MARKET_EXTRACTION = "market_extraction"  # Market data extraction failed
    HEADER_NOT_FOUND = "header_not_found"  # React header missing
    RATE_LIMITED = "rate_limited"  # Too many requests
    PAGE_NOT_FOUND = "page_not_found"  # 404 or page unavailable
    UNKNOWN = "unknown"  # Unclassified errors


@dataclass
class FailedUrl:
    """Represents a URL that failed to scrape."""

    url: str
    error_type: ErrorType
    error_message: str
    attempts: int = 1
    last_attempt: datetime = field(default_factory=lambda: datetime.now(UTC))
    is_retryable: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "error_type": self.error_type.value,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "last_attempt": self.last_attempt.isoformat(),
            "is_retryable": self.is_retryable,
        }


@dataclass
class PartialResult:
    """Represents a match with partial data (e.g., missing markets)."""

    url: str
    data: dict[str, Any]
    missing_markets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "url": self.url,
            "data": self.data,
            "missing_markets": self.missing_markets,
            "warnings": self.warnings,
        }


@dataclass
class ScrapeStats:
    """Statistics for a scraping operation."""

    total_urls: int = 0
    successful: int = 0
    failed: int = 0
    partial: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_urls == 0:
            return 0.0
        return (self.successful / self.total_urls) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_urls": self.total_urls,
            "successful": self.successful,
            "failed": self.failed,
            "partial": self.partial,
            "success_rate": f"{self.success_rate:.1f}%",
        }


@dataclass
class ScrapeResult:
    """
    Complete result of a scraping operation.

    Contains successful results, failed URLs with error details,
    partial results, and overall statistics.
    """

    success: list[dict[str, Any]] = field(default_factory=list)
    failed: list[FailedUrl] = field(default_factory=list)
    partial: list[PartialResult] = field(default_factory=list)
    stats: ScrapeStats = field(default_factory=ScrapeStats)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "failed": [f.to_dict() for f in self.failed],
            "partial": [p.to_dict() for p in self.partial],
            "stats": self.stats.to_dict(),
        }

    def merge(self, other: "ScrapeResult") -> "ScrapeResult":
        """
        Merge another ScrapeResult into this one.

        Args:
            other: Another ScrapeResult to merge.

        Returns:
            Self for chaining.
        """
        self.success.extend(other.success)
        self.failed.extend(other.failed)
        self.partial.extend(other.partial)
        self.stats.total_urls += other.stats.total_urls
        self.stats.successful += other.stats.successful
        self.stats.failed += other.stats.failed
        self.stats.partial += other.stats.partial
        return self

    def get_retryable_urls(self) -> list[str]:
        """Get list of failed URLs that can be retried."""
        return [f.url for f in self.failed if f.is_retryable]

    def get_error_breakdown(self) -> dict[str, list[str]]:
        """Get breakdown of failures by error type."""
        breakdown: dict[str, list[str]] = {}
        for failed in self.failed:
            error_type = failed.error_type.value
            if error_type not in breakdown:
                breakdown[error_type] = []
            breakdown[error_type].append(failed.url)
        return breakdown
