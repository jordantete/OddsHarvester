"""Tests for scrape_result module."""

from datetime import datetime

from oddsharvester.core.scrape_result import (
    ErrorType,
    FailedUrl,
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


class TestScrapeStats:
    """Tests for ScrapeStats dataclass."""

    def test_create_scrape_stats(self):
        """Test creating a ScrapeStats instance."""
        stats = ScrapeStats(total_urls=100, successful=80, failed=15)
        assert stats.total_urls == 100
        assert stats.successful == 80
        assert stats.failed == 15

    def test_success_rate_calculation(self):
        """Test success rate property."""
        stats = ScrapeStats(total_urls=100, successful=75)
        assert stats.success_rate == 75.0

    def test_success_rate_zero_total(self):
        """Test success rate when total is zero."""
        stats = ScrapeStats()
        assert stats.success_rate == 0.0


class TestScrapeResult:
    """Tests for ScrapeResult dataclass."""

    def test_create_empty_scrape_result(self):
        """Test creating an empty ScrapeResult."""
        result = ScrapeResult()
        assert result.success == []
        assert result.failed == []
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


def test_combo_stats_defaults_to_empty_list():
    result = ScrapeResult()
    assert result.combo_stats == []


def test_merge_does_not_propagate_combo_stats():
    """Only the combo helper writes combo_stats; merging per-combo results must not duplicate entries."""
    target = ScrapeResult()
    other = ScrapeResult()
    other.combo_stats.append(
        {"league": "spain-laliga", "season": "2020", "successful": 1, "failed": 0, "errored": False}
    )
    target.merge(other)
    assert target.combo_stats == []


class TestLinksOnlyResult:
    def test_from_links_puts_link_first_context_next_and_extras_last(self):
        result = ScrapeResult.from_links(
            rows=[{"match_link": "https://x/m1", "kickoff_utc": "2026-09-20 18:00:00 UTC"}],
            context={"sport": "football", "league": "epl", "date": "20260920", "season": None},
        )

        assert list(result.success[0].keys()) == ["match_link", "sport", "league", "date", "season", "kickoff_utc"]
        assert result.success[0]["match_link"] == "https://x/m1"
        assert result.failed == []
        assert (result.stats.successful, result.stats.failed, result.stats.total_urls) == (1, 0, 1)

    def test_from_links_counts_failed_listing_pages(self):
        result = ScrapeResult.from_links(
            rows=[{"match_link": "https://x/m1"}],
            context={"sport": "football"},
            failed_page_urls=["https://x/results/#page/3"],
        )

        assert [f.url for f in result.failed] == ["https://x/results/#page/3"]
        assert result.failed[0].error_type is ErrorType.LISTING_PAGE
        assert (result.stats.successful, result.stats.failed, result.stats.total_urls) == (1, 1, 2)

    def test_add_listing_failures_extends_failed_and_stats(self):
        result = ScrapeResult(success=[{"home_team": "A"}], stats=ScrapeStats(total_urls=1, successful=1))

        result.add_listing_failures(["https://x/results/#page/2", "https://x/results/#page/3"])

        assert [f.error_type for f in result.failed] == [ErrorType.LISTING_PAGE, ErrorType.LISTING_PAGE]
        assert (result.stats.failed, result.stats.total_urls) == (2, 3)

    def test_add_listing_failures_with_nothing_is_a_no_op(self):
        result = ScrapeResult(stats=ScrapeStats(total_urls=1, successful=1))

        result.add_listing_failures([])

        assert result.failed == []
        assert (result.stats.failed, result.stats.total_urls) == (0, 1)
