"""upcoming must flag a league whose listing failed, like historic does."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from oddsharvester.cli.cli import cli
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats

ARGS = ["upcoming", "-s", "football", "--league", "england-premier-league,england-championship"]


def _combo(league, successful, errored=False):
    return {"league": league, "season": None, "successful": successful, "failed": 0, "errored": errored}


def _run(result):
    with (
        patch("oddsharvester.cli.commands.upcoming.run_scraper", new_callable=AsyncMock, return_value=result),
        patch("oddsharvester.cli.commands._output.store_data") as store_mock,
    ):
        return CliRunner().invoke(cli, ARGS), store_mock


def test_errored_league_exits_1_and_keeps_the_other_leagues_data():
    result, store_mock = _run(
        ScrapeResult(
            success=[{"match_link": "https://x/epl/m1"}],
            failed=[
                FailedUrl(
                    url="england-championship",
                    error_type=ErrorType.LISTING_PAGE,
                    error_message="Listing failed for england-championship: ValueError: boom",
                )
            ],
            stats=ScrapeStats(total_urls=2, successful=1, failed=1),
            combo_stats=[_combo("england-premier-league", 1), _combo("england-championship", 0, errored=True)],
        )
    )

    assert result.exit_code == 1, result.output
    assert store_mock.called
    assert "Collected matches across 2 combos" in result.output
    assert "1 combo(s) errored." in result.output
    assert "listing page" in result.output.lower()


def test_complete_multi_league_run_exits_0_with_its_summary():
    result, store_mock = _run(
        ScrapeResult(
            success=[{"match_link": "https://x/epl/m1"}, {"match_link": "https://x/efl/m1"}],
            stats=ScrapeStats(total_urls=2, successful=2),
            combo_stats=[_combo("england-premier-league", 1), _combo("england-championship", 1)],
        )
    )

    assert result.exit_code == 0, result.output
    assert store_mock.called
    assert "Collected matches across 2 combos" in result.output
