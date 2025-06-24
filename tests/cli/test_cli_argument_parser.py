import pytest

from src.cli.cli_argument_parser import CLIArgumentParser


@pytest.fixture
def parser():
    return CLIArgumentParser().get_parser()


def test_parser_has_subparsers(parser):
    assert parser._subparsers is not None
    assert "scrape_upcoming" in parser._subparsers._group_actions[0].choices
    assert "scrape_historic" in parser._subparsers._group_actions[0].choices


def test_parse_scrape_upcoming(parser):
    args = parser.parse_args(
        [
            "scrape_upcoming",
            "--sport",
            "football",
            "--date",
            "20250225",
            "--league",
            "premier-league",
            "--markets",
            "1x2,btts",
            "--storage",
            "local",
            "--format",
            "json",
            "--file_path",
            "output.json",
            "--headless",
            "--save_logs",
        ]
    )
    assert args.command == "scrape_upcoming"
    assert args.sport == "football"
    assert args.date == "20250225"
    assert args.league == "premier-league"
    assert args.markets == ["1x2", "btts"]
    assert args.storage == "local"
    assert args.format == "json"
    assert args.file_path == "output.json"
    assert args.headless is True
    assert args.save_logs is True


def test_parse_scrape_historic(parser):
    args = parser.parse_args(
        [
            "scrape_historic",
            "--sport",
            "tennis",
            "--season",
            "2023-2024",
            "--league",
            "atp-tour",
            "--markets",
            "match_winner,over_under",
            "--storage",
            "local",
            "--format",
            "csv",
            "--file_path",
            "historical.csv",
            "--headless",
        ]
    )
    assert args.command == "scrape_historic"
    assert args.sport == "tennis"
    assert args.season == "2023-2024"
    assert args.league == "atp-tour"
    assert args.markets == ["match_winner", "over_under"]
    assert args.storage == "local"
    assert args.format == "csv"
    assert args.file_path == "historical.csv"
    assert args.headless is True


def test_parser_defaults():
    """Test that the parser sets correct default values."""
    parser = CLIArgumentParser()
    args = parser.parse_args(["scrape_upcoming"])

    assert args.command == "scrape_upcoming"
    assert args.sport is None  # Changed from 'football' to None since we want explicit sport selection
    assert args.league is None
    assert args.markets is None
    assert args.storage == "local"
    assert args.file_path is None
    assert args.format is None
    assert args.proxies is None
    assert args.browser_user_agent is None
    assert args.browser_locale_timezone is None
    assert args.browser_timezone_id is None
    assert args.headless is False
    assert args.save_logs is False
    assert args.target_bookmaker is None
    assert args.scrape_odds_history is False
    assert args.date is None


def test_invalid_sport(parser):
    with pytest.raises(SystemExit):  # argparse raises SystemExit on invalid args
        parser.parse_args(["scrape_upcoming", "--sport", "invalid_sport", "--date", "20250225"])


def test_missing_season(parser):
    with pytest.raises(SystemExit):
        parser.parse_args(["scrape_historic"])


def test_invalid_storage(parser):
    with pytest.raises(SystemExit):
        parser.parse_args(["scrape_upcoming", "--date", "20250225", "--storage", "invalid_storage"])


def test_invalid_format(parser):
    with pytest.raises(SystemExit):
        parser.parse_args(["scrape_upcoming", "--date", "20250225", "--format", "invalid_format"])
