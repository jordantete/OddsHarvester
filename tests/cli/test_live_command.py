"""Tests for the live CLI command."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
import pytest

from oddsharvester.cli.cli import cli
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats
from oddsharvester.utils.command_enum import CommandEnum


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_live_run():
    """Mock the run so no browser is launched."""
    with patch(
        "oddsharvester.cli.commands._scrape.run_scrape",
        new_callable=AsyncMock,
        return_value=ScrapeResult(
            success=[{"home_team": "A", "away_team": "B", "live_period": "65'"}],
            stats=ScrapeStats(total_urls=1, successful=1, failed=0),
        ),
    ) as mock:
        yield mock


def test_live_is_registered(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "live" in result.output


def test_live_requires_sport(runner):
    result = runner.invoke(cli, ["live"])
    assert result.exit_code != 0
    assert "sport" in result.output.lower()


def test_live_rejects_odds_history(runner):
    result = runner.invoke(cli, ["live", "--sport", "football", "--odds-history"])
    assert result.exit_code != 0
    assert "not supported" in result.output


@pytest.mark.parametrize(("sport", "period"), [("football", "full_time"), ("basketball", "full_including_ot")])
@patch("oddsharvester.cli.commands._output.store_data")
def test_live_accepts_the_full_match_period_as_a_no_op(store_mock, runner, mock_live_run, sport, period):
    result = runner.invoke(cli, ["live", "--sport", sport, "--period", period])

    assert result.exit_code == 0, result.output
    assert mock_live_run.called


@pytest.mark.parametrize(
    ("sport", "period", "accepted"),
    [("football", "1st_half", "full_time"), ("basketball", "1st_quarter", "full_including_ot")],
)
def test_live_rejects_any_other_period(runner, sport, period, accepted):
    result = runner.invoke(cli, ["live", "--sport", sport, "--period", period])

    assert result.exit_code == 2
    assert f"--period accepts only {accepted} for live scraping" in result.output


def test_live_rejects_links_only_with_local_kickoff(runner):
    result = runner.invoke(cli, ["live", "--sport", "football", "--links-only", "--local-kickoff"])

    assert result.exit_code == 2
    assert "--links-only cannot be combined with --local-kickoff" in result.output


def test_live_rejects_multiple_leagues(runner):
    # Both slugs must be valid so this exercises the live command's own one-league
    # rule rather than --league's slug validation.
    result = runner.invoke(cli, ["live", "--sport", "football", "--league", "england-premier-league,brazil-serie-a"])
    assert result.exit_code != 0
    assert "at most one --league" in result.output


def test_live_rejects_links_only_with_match_link(runner):
    result = runner.invoke(
        cli,
        [
            "live",
            "--sport",
            "football",
            "--links-only",
            "--match-link",
            "https://www.oddsportal.com/football/spain/laliga/real-betis-abc/",
        ],
    )
    assert result.exit_code != 0


@patch("oddsharvester.cli.commands._output.store_data")
def test_live_invokes_run_scraper_with_live_command(store_mock, runner, mock_live_run):
    result = runner.invoke(cli, ["live", "--sport", "football", "--market", "1x2"])

    assert result.exit_code == 0
    [options] = mock_live_run.call_args.args
    assert options.command is CommandEnum.LIVE
    assert options.sport == "football"
    assert store_mock.called


@patch("oddsharvester.cli.commands._output.store_data")
def test_live_no_matches_exits_zero_without_storing(store_mock, runner):
    """Zero live matches is a normal outcome, not a failure."""
    with patch(
        "oddsharvester.cli.commands._scrape.run_scrape",
        new_callable=AsyncMock,
        return_value=ScrapeResult(),
    ):
        result = runner.invoke(cli, ["live", "--sport", "football", "--market", "1x2"])

    assert result.exit_code == 0
    assert "No live matches" in result.output
    assert not store_mock.called


@patch("oddsharvester.cli.commands._output.store_data")
def test_live_exits_nonzero_when_scraper_returns_none(store_mock, runner):
    """A fatal scraper error must not be reported as a clean run."""
    with patch(
        "oddsharvester.cli.commands._scrape.run_scrape",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = runner.invoke(cli, ["live", "--sport", "football", "--market", "1x2"])

    assert result.exit_code == 1
    assert not store_mock.called


@patch("oddsharvester.cli.commands._output.store_data")
def test_live_exits_nonzero_when_every_match_fails(store_mock, runner):
    """All matches failing is a scraping failure, not an empty-but-healthy snapshot.

    An external cron sampler must be able to tell "OddsPortal has nothing in play"
    apart from "every request was blocked".
    """
    failures = [
        FailedUrl(
            url="https://www.oddsportal.com/football/x/inplay-odds/#a",
            error_type=ErrorType.NAVIGATION,
            error_message="timeout",
        )
    ]
    with patch(
        "oddsharvester.cli.commands._scrape.run_scrape",
        new_callable=AsyncMock,
        return_value=ScrapeResult(
            success=[],
            failed=failures,
            stats=ScrapeStats(total_urls=1, successful=0, failed=1),
        ),
    ):
        result = runner.invoke(cli, ["live", "--sport", "football", "--market", "1x2"])

    assert result.exit_code == 1
    assert not store_mock.called
    assert "No live matches" not in result.output


@patch("oddsharvester.cli.commands._output.store_data")
def test_live_forwards_preview_and_local_kickoff(store_mock, runner, mock_live_run):
    """Options accepted by the CLI must reach the scraper, not be silently dropped."""
    result = runner.invoke(cli, ["live", "--sport", "football", "--market", "1x2", "--preview-only", "--local-kickoff"])

    assert result.exit_code == 0
    [options] = mock_live_run.call_args.args
    assert options.preview_submarkets_only is True
    assert options.local_kickoff is True
