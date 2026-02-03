"""Tests for scrape_result module."""

from datetime import datetime

from oddsharvester.core.scrape_result import (
    ErrorType,
    FailedUrl,
    PartialResult,
    ScrapeResult,
    ScrapeStats,
)


class TestErrorType:
    """Tests for ErrorType enum."""

    def test_all_error_types_have_values(self):
        """Verify all error types have string values."""
        assert ErrorType.NAVIGATION.value == "navigation"
        assert ErrorType.PARSING.value == "parsing"
        assert ErrorType.MARKET_EXTRACTION.value == "market_extraction"
        assert ErrorType.HEADER_NOT_FOUND.value == "header_not_found"
        assert ErrorType.RATE_LIMITED.value == "rate_limited"
        assert ErrorType.PAGE_NOT_FOUND.value == "page_not_found"
        assert ErrorType.UNKNOWN.value == "unknown"


class TestFailedUrl:
    """Tests for FailedUrl dataclass."""

    def test_create_failed_url(self):
        """Test creating a FailedUrl instance."""
        failed = FailedUrl(
            url="https://example.com/match1",
            error_type=ErrorType.NAVIGATION,
            error_message="Connection timeout",
            attempts=2,
            is_retryable=True,
        )
        assert failed.url == "https://example.com/match1"
        assert failed.error_type == ErrorType.NAVIGATION
        assert failed.error_message == "Connection timeout"
        assert failed.attempts == 2
        assert failed.is_retryable is True
        assert isinstance(failed.last_attempt, datetime)

    def test_failed_url_to_dict(self):
        """Test converting FailedUrl to dictionary."""
        failed = FailedUrl(
            url="https://example.com/match1",
            error_type=ErrorType.PARSING,
            error_message="Invalid HTML",
            attempts=1,
            is_retryable=False,
        )
        result = failed.to_dict()
        assert result["url"] == "https://example.com/match1"
        assert result["error_type"] == "parsing"
        assert result["error_message"] == "Invalid HTML"
        assert result["attempts"] == 1
        assert result["is_retryable"] is False
        assert "last_attempt" in result


class TestPartialResult:
    """Tests for PartialResult dataclass."""

    def test_create_partial_result(self):
        """Test creating a PartialResult instance."""
        partial = PartialResult(
            url="https://example.com/match1",
            data={"home_team": "Team A", "away_team": "Team B"},
            missing_markets=["over_under"],
            warnings=["Market data incomplete"],
        )
        assert partial.url == "https://example.com/match1"
        assert partial.data["home_team"] == "Team A"
        assert partial.missing_markets == ["over_under"]
        assert partial.warnings == ["Market data incomplete"]

    def test_partial_result_to_dict(self):
        """Test converting PartialResult to dictionary."""
        partial = PartialResult(
            url="https://example.com/match1",
            data={"home_team": "Team A"},
            missing_markets=["1x2"],
        )
        result = partial.to_dict()
        assert result["url"] == "https://example.com/match1"
        assert result["data"]["home_team"] == "Team A"
        assert result["missing_markets"] == ["1x2"]
        assert result["warnings"] == []


class TestScrapeStats:
    """Tests for ScrapeStats dataclass."""

    def test_create_scrape_stats(self):
        """Test creating a ScrapeStats instance."""
        stats = ScrapeStats(total_urls=100, successful=80, failed=15, partial=5)
        assert stats.total_urls == 100
        assert stats.successful == 80
        assert stats.failed == 15
        assert stats.partial == 5

    def test_success_rate_calculation(self):
        """Test success rate property."""
        stats = ScrapeStats(total_urls=100, successful=75)
        assert stats.success_rate == 75.0

    def test_success_rate_zero_total(self):
        """Test success rate when total is zero."""
        stats = ScrapeStats()
        assert stats.success_rate == 0.0

    def test_scrape_stats_to_dict(self):
        """Test converting ScrapeStats to dictionary."""
        stats = ScrapeStats(total_urls=50, successful=45, failed=3, partial=2)
        result = stats.to_dict()
        assert result["total_urls"] == 50
        assert result["successful"] == 45
        assert result["failed"] == 3
        assert result["partial"] == 2
        assert result["success_rate"] == "90.0%"


class TestScrapeResult:
    """Tests for ScrapeResult dataclass."""

    def test_create_empty_scrape_result(self):
        """Test creating an empty ScrapeResult."""
        result = ScrapeResult()
        assert result.success == []
        assert result.failed == []
        assert result.partial == []
        assert result.stats.total_urls == 0

    def test_create_scrape_result_with_data(self):
        """Test creating a ScrapeResult with data."""
        failed_url = FailedUrl(
            url="https://example.com/failed",
            error_type=ErrorType.NAVIGATION,
            error_message="Timeout",
        )
        result = ScrapeResult(
            success=[{"match": "data1"}, {"match": "data2"}],
            failed=[failed_url],
            stats=ScrapeStats(total_urls=3, successful=2, failed=1),
        )
        assert len(result.success) == 2
        assert len(result.failed) == 1
        assert result.stats.total_urls == 3

    def test_scrape_result_merge(self):
        """Test merging two ScrapeResults."""
        result1 = ScrapeResult(
            success=[{"match": "data1"}],
            stats=ScrapeStats(total_urls=2, successful=1, failed=1),
        )
        result2 = ScrapeResult(
            success=[{"match": "data2"}, {"match": "data3"}],
            stats=ScrapeStats(total_urls=3, successful=2, failed=1),
        )
        result1.merge(result2)

        assert len(result1.success) == 3
        assert result1.stats.total_urls == 5
        assert result1.stats.successful == 3
        assert result1.stats.failed == 2

    def test_get_retryable_urls(self):
        """Test getting retryable URLs."""
        failed1 = FailedUrl(
            url="https://example.com/retry1",
            error_type=ErrorType.NAVIGATION,
            error_message="Timeout",
            is_retryable=True,
        )
        failed2 = FailedUrl(
            url="https://example.com/no_retry",
            error_type=ErrorType.PAGE_NOT_FOUND,
            error_message="404",
            is_retryable=False,
        )
        failed3 = FailedUrl(
            url="https://example.com/retry2",
            error_type=ErrorType.NAVIGATION,
            error_message="Connection reset",
            is_retryable=True,
        )
        result = ScrapeResult(failed=[failed1, failed2, failed3])

        retryable = result.get_retryable_urls()
        assert len(retryable) == 2
        assert "https://example.com/retry1" in retryable
        assert "https://example.com/retry2" in retryable
        assert "https://example.com/no_retry" not in retryable

    def test_get_error_breakdown(self):
        """Test getting error breakdown by type."""
        failed1 = FailedUrl(
            url="https://example.com/nav1",
            error_type=ErrorType.NAVIGATION,
            error_message="Timeout",
        )
        failed2 = FailedUrl(
            url="https://example.com/nav2",
            error_type=ErrorType.NAVIGATION,
            error_message="Connection reset",
        )
        failed3 = FailedUrl(
            url="https://example.com/parse1",
            error_type=ErrorType.PARSING,
            error_message="Invalid HTML",
        )
        result = ScrapeResult(failed=[failed1, failed2, failed3])

        breakdown = result.get_error_breakdown()
        assert len(breakdown["navigation"]) == 2
        assert len(breakdown["parsing"]) == 1
        assert "https://example.com/nav1" in breakdown["navigation"]
        assert "https://example.com/parse1" in breakdown["parsing"]

    def test_scrape_result_to_dict(self):
        """Test converting ScrapeResult to dictionary."""
        failed = FailedUrl(
            url="https://example.com/failed",
            error_type=ErrorType.NAVIGATION,
            error_message="Timeout",
        )
        result = ScrapeResult(
            success=[{"match": "data1"}],
            failed=[failed],
            stats=ScrapeStats(total_urls=2, successful=1, failed=1),
        )

        data = result.to_dict()
        assert len(data["success"]) == 1
        assert len(data["failed"]) == 1
        assert data["stats"]["total_urls"] == 2
        assert data["failed"][0]["error_type"] == "navigation"
