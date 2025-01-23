import pytest
from argparse import Namespace
from unittest.mock import patch
from utils.cli_argument_handler import CLIArgumentHandler

class TestCLIArgumentHandler:
    @pytest.fixture
    def cli_handler(self):
        return CLIArgumentHandler()

    @pytest.mark.parametrize(
        "args, expected",
        [
            (
                [
                    "scrape_upcoming",
                    "--sport", "football",
                    "--date", "2025-01-01",
                    "--markets", "1x2,btts",
                    "--storage", "local",
                    "--file_path", "data.json",
                    "--format", "json",
                    "--headless"
                ],
                Namespace(
                    command="scrape_upcoming",
                    sport="football",
                    date="2025-01-01",
                    league=None,
                    markets=["1x2", "btts"],
                    storage="local",
                    file_path="data.json",
                    format="json",
                    headless=True,
                    save_logs=False,
                ),
            ),
            (
                [
                    "scrape_historic",
                    "--league", "england-premier-league",
                    "--season", "2022-2023",
                    "--markets", "1x2",
                    "--storage", "remote",
                    "--file_path", "data.json",
                    "--format", "json",
                ],
                Namespace(
                    command="scrape_historic",
                    league="england-premier-league",
                    season="2022-2023",
                    markets=["1x2"],
                    storage="remote",
                    file_path="data.json",
                    format="json",
                    headless=False,
                    save_logs=False,
                ),
            ),
        ],
    )
    def test_parse_and_validate_args_valid(self, cli_handler, args, expected):
        with patch("sys.argv", ["main.py"] + args):
            parsed_args = cli_handler.parser.parse_args()
            cli_handler.parse_and_validate_args()  # Ensure validation does not raise
            for key, value in vars(expected).items():
                assert getattr(parsed_args, key) == value

    def test_missing_command(self, cli_handler):
        with pytest.raises(SystemExit):
            cli_handler.parser.parse_args([])
            cli_handler.parse_and_validate_args()

    def test_help_message(self, cli_handler, capsys):
        with pytest.raises(SystemExit):
            cli_handler.parser.parse_args(["--help"])

        captured = capsys.readouterr()
        assert "OddsHarvester CLI for scraping betting odds data." in captured.out

    def test_default_values(self, cli_handler):
        args = [
            "scrape_upcoming",
            "--sport", "football",
            "--date", "2025-01-01",
        ]
        parsed_args = cli_handler.parser.parse_args(args)
        assert parsed_args.markets == ["1x2"]
        assert parsed_args.storage == "local"
        assert parsed_args.headless is False
        assert parsed_args.save_logs is False
        assert parsed_args.file_path is None
        assert parsed_args.format is None