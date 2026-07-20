"""An incomplete listing collection must not be reported as a successful run.

A failed listing page loses a whole page of matches that were never discovered.
Downstream consumers (cron jobs, backtests) cannot detect that from the data, so
the exit code has to carry the signal.
"""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
import pytest

from oddsharvester.cli.cli import cli
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats


@pytest.fixture
def runner():
    return CliRunner()


def _listing_failure(page: int) -> FailedUrl:
    return FailedUrl(
        url=f"https://www.oddsportal.com/football/england/premier-league-2022-2023/results/#/page/{page}",
        error_type=ErrorType.LISTING_PAGE,
        error_message="Failed to collect links from listing page",
    )


def _run(runner, result):
    with patch(
        "oddsharvester.cli.commands.historic.run_scraper",
        new_callable=AsyncMock,
        return_value=result,
    ):
        return runner.invoke(
            cli,
            ["historic", "--sport", "football", "--league", "england-premier-league", "--season", "2022-2023"],
        )


@patch("oddsharvester.cli.commands.historic.store_data")
def test_partial_collection_exits_nonzero_but_still_stores(store_mock, runner):
    result = _run(
        runner,
        ScrapeResult(
            success=[{"home_team": "A"}, {"home_team": "B"}],
            failed=[_listing_failure(3), _listing_failure(4)],
            stats=ScrapeStats(total_urls=4, successful=2, failed=2),
        ),
    )

    assert result.exit_code == 1, "an incomplete collection must not look like a clean run"
    assert "listing page" in result.output.lower()
    assert store_mock.called, "the partial data is still worth keeping for inspection or retry"


@patch("oddsharvester.cli.commands.historic.store_data")
def test_complete_collection_exits_zero(store_mock, runner):
    result = _run(
        runner,
        ScrapeResult(
            success=[{"home_team": "A"}],
            stats=ScrapeStats(total_urls=1, successful=1),
        ),
    )

    assert result.exit_code == 0
    assert store_mock.called


@patch("oddsharvester.cli.commands.historic.store_data")
def test_per_match_failures_alone_do_not_fail_the_run(store_mock, runner):
    """Individual match failures are enumerable and retryable, so they stay non-fatal."""
    result = _run(
        runner,
        ScrapeResult(
            success=[{"home_team": "A"}],
            failed=[
                FailedUrl(
                    url="https://www.oddsportal.com/football/h2h/a/b/",
                    error_type=ErrorType.NAVIGATION,
                    error_message="timeout",
                )
            ],
            stats=ScrapeStats(total_urls=2, successful=1, failed=1),
        ),
    )

    assert result.exit_code == 0
    assert store_mock.called
