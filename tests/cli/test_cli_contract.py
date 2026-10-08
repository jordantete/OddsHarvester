"""The CLI contract its consumers rely on.

The odds collector reads only whether the output file exists. tipster_watch reads the exit code (0 or 1) and
greps the output for "rate limited by OddsPortal" and "does not exist on OddsPortal". upcoming and historic
exit 1 on an empty result; live exits 0 on an empty snapshot, and search writes [] and exits 0 when it finds
nothing. Each test runs the real command, and the real run_scraper against FakeScraper for the odds commands,
so none depends on how the CLI reaches the core.
"""

import json
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
import pytest

from oddsharvester.cli.cli import cli
from oddsharvester.core.exceptions import PageNotFoundError, RateLimitError
from oddsharvester.core.odds_portal_scraper import ListingResult
from oddsharvester.core.scrape_result import ErrorType, FailedUrl, ScrapeResult, ScrapeStats
from oddsharvester.utils.bookies_filter_enum import BookiesFilter
from oddsharvester.utils.period_constants import FootballPeriod

FUTURE_DATE = "20991231"
EPL = "england-premier-league"
M1 = "https://www.oddsportal.com/football/h2h/arsenal-hA1Zm19f/leeds-tUxUbLR2/#xtmHKGT0"
M2 = "https://www.oddsportal.com/football/h2h/chelsea-4fGZN2oK/manchester-city-Wtn9Stg0/#lMp9YMye"
LISTING_URL = "https://www.oddsportal.com/football/england/premier-league/results/"

# Each command line, with the scraper method whose answer is the run's odds result.
SHAPES = {
    "upcoming listing": (["upcoming", "-s", "football", "-l", EPL, "-d", FUTURE_DATE], "extract_match_odds"),
    "upcoming match links": (["upcoming", "-s", "football", "--match-link", f"{M1},{M2}"], "scrape_matches"),
    "historic listing": (["historic", "-s", "football", "-l", EPL, "--season", "2025-2026"], "extract_match_odds"),
    "historic match links": (
        ["historic", "-s", "football", "--season", "2025-2026", "--match-link", f"{M1},{M2}"],
        "scrape_matches",
    ),
    "live listing": (["live", "-s", "football"], "scrape_live"),
    "live match links": (["live", "-s", "football", "--match-link", M1], "scrape_live"),
}


def _odds(ok: list[str], failed: list[str] = ()) -> ScrapeResult:
    return ScrapeResult(
        success=[{"match_link": link, "home_team": "Home", "season": None} for link in ok],
        failed=[FailedUrl(url=link, error_type=ErrorType.NAVIGATION, error_message="Timeout") for link in failed],
        stats=ScrapeStats(total_urls=len(ok) + len(failed), successful=len(ok), failed=len(failed)),
    )


def _listing(*links: str, failed_page_urls: list[str] | None = None) -> ListingResult:
    return ListingResult(rows=[{"match_link": link} for link in links], failed_page_urls=failed_page_urls or [])


def _invoke(args: list[str], out) -> object:
    return CliRunner().invoke(cli, [*args, "--headless", "-o", str(out)])


def _run_shape(scraper, shape: str, odds: ScrapeResult, tmp_path, listed: tuple[str, ...] = (M1, M2)):
    args, method = SHAPES[shape]
    scraper.answers["collect_upcoming_links"] = _listing(*listed)
    scraper.answers["collect_historic_links"] = _listing(*listed)
    scraper.answers[method] = odds
    out = tmp_path / "out.json"
    return _invoke(args, out), out


def _links(out) -> list[str]:
    return [record["match_link"] for record in json.loads(out.read_text(encoding="utf-8"))]


@pytest.mark.parametrize("shape", list(SHAPES))
def test_a_complete_run_exits_0_and_writes_every_record(fake_scraper, tmp_path, shape):
    result, out = _run_shape(fake_scraper, shape, _odds([M1, M2]), tmp_path)

    assert result.exit_code == 0, result.output
    assert _links(out) == [M1, M2]
    unit = "live matches" if shape.startswith("live") else "matches"
    assert f"Successfully scraped 2 {unit} (0 failed, 100.0% success rate)." in result.stdout


@pytest.mark.parametrize("shape", list(SHAPES))
def test_a_run_with_failed_matches_exits_0_and_writes_the_others(fake_scraper, tmp_path, shape):
    result, out = _run_shape(fake_scraper, shape, _odds([M1], failed=[M2]), tmp_path)

    assert result.exit_code == 0, result.output
    assert _links(out) == [M1]
    assert f"Failed URLs: ['{M2}']" in result.stderr
    assert "(1 failed, 50.0% success rate)." in result.stdout


@pytest.mark.parametrize("shape", list(SHAPES))
def test_a_run_where_every_match_failed_exits_1_and_writes_nothing(fake_scraper, tmp_path, shape):
    result, out = _run_shape(fake_scraper, shape, _odds([], failed=[M1, M2]), tmp_path)

    assert result.exit_code == 1, result.output
    assert not out.exists()


@pytest.mark.parametrize("shape", list(SHAPES))
def test_an_empty_run_exits_1_but_an_empty_live_snapshot_exits_0(fake_scraper, tmp_path, caplog, shape):
    result, out = _run_shape(fake_scraper, shape, ScrapeResult(), tmp_path, listed=())

    assert not out.exists()
    if shape.startswith("live"):
        assert result.exit_code == 0, result.output
        assert "No live matches found right now." in result.stdout
    else:
        assert result.exit_code == 1, result.output
        assert "Scraper did not return valid data." in caplog.text


@pytest.mark.parametrize("shape", list(SHAPES))
def test_a_run_that_crashes_exits_1_and_writes_nothing(fake_scraper, tmp_path, caplog, shape):
    fake_scraper.answers["start_playwright"] = RuntimeError("browser crashed")

    result, out = _run_shape(fake_scraper, shape, _odds([M1, M2]), tmp_path)

    assert result.exit_code == 1, result.output
    assert not out.exists()
    assert "browser crashed" in caplog.text


def test_a_listing_page_that_failed_exits_1_and_keeps_the_records(fake_scraper, tmp_path):
    fake_scraper.answers["collect_historic_links"] = _listing(M1, failed_page_urls=[f"{LISTING_URL}#/page/2/"])
    fake_scraper.answers["extract_match_odds"] = _odds([M1])
    out = tmp_path / "out.json"

    result = _invoke(["historic", "-s", "football", "-l", EPL, "--season", "2025-2026"], out)

    assert result.exit_code == 1, result.output
    assert _links(out) == [M1]
    assert "Incomplete collection: 1 listing page(s) failed" in result.stderr


def test_a_league_whose_listing_failed_exits_1_and_keeps_the_other_league(fake_scraper, tmp_path):
    def listing(league, **_):
        if league == "spain-laliga":
            raise ValueError("listing broke")
        return _listing(M1)

    fake_scraper.answers["collect_upcoming_links"] = listing
    fake_scraper.answers["extract_match_odds"] = _odds([M1])
    out = tmp_path / "out.json"

    result = _invoke(
        ["upcoming", "-s", "football", "-l", f"{EPL},spain-laliga", "-d", FUTURE_DATE, "--request-delay", "0"], out
    )

    assert result.exit_code == 1, result.output
    assert _links(out) == [M1]
    assert "1 combo(s) errored." in result.stdout
    assert "Incomplete collection: 1 listing page(s) failed" in result.stderr


@pytest.mark.parametrize(
    ("args", "method"),
    [
        (["historic", "-s", "football", "-l", EPL, "--season", "current", "--links-only"], "collect_historic_links"),
        (["live", "-s", "football", "--links-only"], "scrape_live"),
    ],
    ids=["historic listing", "live listing"],
)
def test_a_rate_limited_run_exits_1_and_says_so(fake_scraper, tmp_path, caplog, args, method):
    fake_scraper.answers[method] = RateLimitError(
        f"rate limited by OddsPortal: HTTP 429 on listing {LISTING_URL}", url=LISTING_URL, retry_after=0
    )
    out = tmp_path / "out.json"

    with patch("oddsharvester.core.retry.asyncio.sleep", new_callable=AsyncMock):
        result = _invoke(args, out)

    assert result.exit_code == 1, result.output
    assert not out.exists()
    assert "rate limited by OddsPortal" in caplog.text


def test_a_league_oddsportal_does_not_know_exits_1_and_says_so(fake_scraper, tmp_path, caplog):
    league = "football/bhutan/premier-league"
    fake_scraper.answers["collect_upcoming_links"] = PageNotFoundError(
        "League page https://www.oddsportal.com/football/bhutan/premier-league/ does not exist on OddsPortal "
        "(no link to its country page).",
        url="https://www.oddsportal.com/football/bhutan/premier-league/",
    )
    out = tmp_path / "out.json"

    result = _invoke(["upcoming", "-s", "football", "--league", league, "--include-started", "--links-only"], out)

    assert result.exit_code == 1, result.output
    assert not out.exists()
    assert "does not exist on OddsPortal" in caplog.text


def test_links_only_runs_report_the_links_they_collected(fake_scraper, tmp_path):
    fake_scraper.answers["collect_historic_links"] = _listing(M1, M2)
    fake_scraper.answers["scrape_live"] = ScrapeResult.from_links(
        rows=[{"match_link": M1}], context={"sport": "football", "league": None}
    )

    historic = _invoke(["historic", "-s", "football", "-l", EPL, "--season", "current", "--links-only"], tmp_path / "h")
    live = _invoke(["live", "-s", "football", "--links-only"], tmp_path / "l")

    assert historic.exit_code == 0, historic.output
    assert "Collected 2 match links (0 listing pages failed)." in historic.stdout
    assert live.exit_code == 0, live.output
    assert "Collected 1 live match links." in live.stdout


def test_match_link_options_reach_the_scraper(fake_scraper, tmp_path):
    fake_scraper.answers["scrape_matches"] = _odds([M1])
    args = [
        "historic", "-s", "football", "--season", "2025-2026", "--match-link", M1, "-m", "1x2,btts",
        "--odds-history", "--target-bookmaker", "bet365", "--bookies-filter", "classic", "--period", "1st_half",
        "--request-delay", "2.5", "-c", "2", "--preview-only", "--local-kickoff", "--user-agent", "UA/1",
        "--locale", "en-GB", "--timezone", "Europe/London", "--base-url", "https://www.centroquote.it",
        "--proxy-url", "http://proxy.example:8080", "--proxy-user", "u", "--proxy-pass", "p",
    ]  # fmt: skip

    result = _invoke(args, tmp_path / "out.json")

    assert result.exit_code == 0, result.output
    built = fake_scraper.built_with
    assert (built["preview_submarkets_only"], built["local_kickoff"], built["on_match"]) == (True, True, None)
    assert built["base_url"] == "https://www.centroquote.it"
    [start] = fake_scraper.called("start_playwright")
    proxy_manager = start.pop("proxy_manager")
    assert start == {
        "headless": True,
        "browser_user_agent": "UA/1",
        "browser_locale_timezone": "en-GB",
        "browser_timezone_id": "Europe/London",
    }
    assert [entry.config for entry in proxy_manager.entries] == [
        {"server": "http://proxy.example:8080", "username": "u", "password": "p"}
    ]
    assert fake_scraper.called("scrape_matches") == [
        {
            "match_links": [M1],
            "sport": "football",
            "markets": ["1x2", "btts"],
            "scrape_odds_history": True,
            "target_bookmaker": "bet365",
            "bookies_filter": BookiesFilter.CLASSIC,
            "period": FootballPeriod.FIRST_HALF,
            "request_delay": 2.5,
            "concurrent_scraping_task": 2,
        }
    ]
    assert len(fake_scraper.called("stop_playwright")) == 1


def test_upcoming_listing_options_reach_the_scraper(fake_scraper, tmp_path):
    fake_scraper.answers["collect_upcoming_links"] = _listing(M1)
    fake_scraper.answers["extract_match_odds"] = _odds([M1])
    args = [
        "upcoming", "-s", "football", "-l", EPL, "-d", FUTURE_DATE, "--include-started", "--kickoff-within-hours",
        "6", "-m", "1x2", "-c", "2", "--request-delay", "0", "--period", "full_time", "--bookies-filter", "crypto",
    ]  # fmt: skip

    result = _invoke(args, tmp_path / "out.json")

    assert result.exit_code == 0, result.output
    assert fake_scraper.called("collect_upcoming_links") == [
        {
            "sport": "football",
            "date": FUTURE_DATE,
            "league": EPL,
            "include_started": True,
            "kickoff_within_hours": 6.0,
            "collect_kickoff": False,
        }
    ]
    assert fake_scraper.called("extract_match_odds") == [
        {
            "match_links": [M1],
            "sport": "football",
            "markets": ["1x2"],
            "scrape_odds_history": False,
            "target_bookmaker": None,
            "concurrent_scraping_task": 2,
            "preview_submarkets_only": False,
            "bookies_filter": BookiesFilter.CRYPTO,
            "period": FootballPeriod.FULL_TIME,
            "request_delay": 0.0,
        }
    ]


def test_historic_listing_options_reach_the_scraper(fake_scraper, tmp_path):
    fake_scraper.answers["collect_historic_links"] = _listing(M1)
    fake_scraper.answers["extract_match_odds"] = _odds([M1])
    out = tmp_path / "out.json"

    result = _invoke(["historic", "-s", "football", "-l", EPL, "--season", "2024-2025", "--max-pages", "3"], out)

    assert result.exit_code == 0, result.output
    assert fake_scraper.called("collect_historic_links") == [
        {"sport": "football", "league": EPL, "season": "2024-2025", "max_pages": 3}
    ]
    assert [record["season"] for record in json.loads(out.read_text(encoding="utf-8"))] == ["2024-2025"]


def test_live_options_reach_the_scraper(fake_scraper, tmp_path):
    fake_scraper.answers["scrape_live"] = _odds([M1])
    args = [
        "live", "-s", "football", "-l", EPL, "-m", "1x2", "--target-bookmaker", "bet365", "--bookies-filter",
        "classic", "-c", "2", "--request-delay", "1.5", "--preview-only",
    ]  # fmt: skip

    result = _invoke(args, tmp_path / "out.json")

    assert result.exit_code == 0, result.output
    assert fake_scraper.built_with["preview_submarkets_only"] is True
    assert fake_scraper.called("scrape_live") == [
        {
            "sport": "football",
            "league": EPL,
            "markets": ["1x2"],
            "match_links": None,
            "target_bookmaker": "bet365",
            "bookies_filter": BookiesFilter.CLASSIC,
            "request_delay": 1.5,
            "concurrent_scraping_task": 2,
            "links_only": False,
        }
    ]


COLLECTOR = ["--headless", "--timezone", "Europe/London", "--locale", "en-GB", "--request-delay", "2.0"]
FOUR_MARKETS = "1x2,over_under_2_5,btts,double_chance"
CONSUMER_COMMANDS = {
    "collector upcoming discovery": [
        "upcoming", "--sport", "football", "--league", EPL, "--date", FUTURE_DATE, "--market", "1x2", *COLLECTOR,
    ],
    "collector snapshot": ["upcoming", "--sport", "football", "--match-link", M1, "--market", FOUR_MARKETS, *COLLECTOR],
    "collector historic discovery": [
        "historic", "--sport", "football", "--league", EPL, "--season", "2024-2025", "--market", "1x2",
        "--max-pages", "1", *COLLECTOR,
    ],
    "collector history": [
        "historic", "--sport", "football", "--match-link", M2, "--season", "2025-2026", "--market", FOUR_MARKETS,
        "--odds-history", *COLLECTOR, "--concurrency", "3",
    ],
    "tipster live links": ["live", "-s", "football", "--links-only"],
    "tipster league links": ["upcoming", "-s", "football", "--league", EPL, "--include-started", "--links-only"],
    "tipster league results": [
        "historic", "-s", "football", "--league", EPL, "--season", "current", "--links-only", "--max-pages", "1",
    ],
    "tipster pre-match odds": [
        "upcoming", "-s", "football", "--match-link", M1, "-m", "1x2", "--period", "full_time",
        "--bookies-filter", "all",
    ],
    "tipster match result": ["historic", "-s", "football", "--season", "current", "--match-link", M2, "-m", "1x2"],
}  # fmt: skip


@pytest.mark.parametrize("name", list(CONSUMER_COMMANDS))
def test_every_consumer_command_line_runs_and_writes_its_file(fake_scraper, tmp_path, name):
    fake_scraper.answers["collect_upcoming_links"] = _listing(M1)
    fake_scraper.answers["collect_historic_links"] = _listing(M1)
    for method in ("extract_match_odds", "scrape_matches", "scrape_live"):
        fake_scraper.answers[method] = _odds([M1])
    out = tmp_path / "out.json"

    result = CliRunner().invoke(cli, [*CONSUMER_COMMANDS[name], "--headless", "-f", "json", "-o", str(out)])

    assert result.exit_code == 0, result.output
    assert _links(out) == [M1]


BROWSER_FLAGS = [
    "--headless", "--proxy-url", "http://proxy.example:8080", "--proxy-user", "u", "--proxy-pass", "p",
    "--user-agent", "UA/1", "--locale", "en-GB", "--timezone", "Europe/London",
    "--base-url", "https://www.centroquote.it",
]  # fmt: skip
BROWSER_ENV = {
    "OH_HEADLESS": "1",
    "OH_PROXY_URL": "http://proxy.example:8080",
    "OH_PROXY_USER": "u",
    "OH_PROXY_PASS": "p",
    "OH_USER_AGENT": "UA/1",
    "OH_LOCALE": "en-GB",
    "OH_TIMEZONE": "Europe/London",
    "OH_BASE_URL": "https://www.centroquote.it",
}
BROWSER_KWARGS = {
    "headless": True,
    "proxy_url": ("http://proxy.example:8080",),
    "proxy_user": "u",
    "proxy_pass": "p",
    "browser_user_agent": "UA/1",
    "browser_locale_timezone": "en-GB",
    "browser_timezone_id": "Europe/London",
    "base_url": "https://www.centroquote.it",
}
OWN_RUNNERS = [
    (["community", "--sport", "football"], "community.run_top_predictions", lambda: [{"match_url": M1}]),
    (
        ["team", "--team", "lId4TMwf"],
        "team.run_teams",
        lambda: ScrapeResult(success=[{"team_id": "lId4TMwf"}], stats=ScrapeStats(total_urls=1, successful=1)),
    ),
    (["search", "--team-id", "hUyau0Vc"], "search.run_search", lambda: [{"match_link": M1}]),
]


@pytest.mark.parametrize(("args", "target", "answer"), OWN_RUNNERS, ids=["community", "team", "search"])
@pytest.mark.parametrize("given_as", ["flags", "environment"])
def test_commands_with_their_own_runner_take_the_output_and_browser_options(tmp_path, args, target, answer, given_as):
    out = tmp_path / "out.csv"
    flags = BROWSER_FLAGS if given_as == "flags" else []
    env = BROWSER_ENV if given_as == "environment" else {}
    output = ["--storage", "local", "--format", "csv", "--output", str(out), "--append"]

    with patch(f"oddsharvester.cli.commands.{target}", new_callable=AsyncMock, side_effect=lambda **_: answer()) as run:
        first = CliRunner().invoke(cli, [*args, *flags, *output], env=env)
        second = CliRunner().invoke(cli, [*args, *flags, *output], env=env)

    assert (first.exit_code, second.exit_code) == (0, 0), first.output + second.output
    assert {key: run.await_args.kwargs[key] for key in BROWSER_KWARGS} == BROWSER_KWARGS
    assert len(out.read_text(encoding="utf-8").splitlines()) == 3


SEARCH_SHAPES = {
    "tipster search teams": ["search", "--query", "Nacional Potosi", "-s", "football"],
    "tipster search matches": ["search", "--team-id", "hUyau0Vc"],
}


@pytest.mark.parametrize("name", list(SEARCH_SHAPES))
def test_a_search_that_finds_nothing_exits_0_and_writes_an_empty_list(tmp_path, name):
    out = tmp_path / "out.json"
    with patch("oddsharvester.cli.commands.search.run_search", new_callable=AsyncMock, return_value=[]):
        result = _invoke(SEARCH_SHAPES[name], out)

    assert result.exit_code == 0, result.output
    assert json.loads(out.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("name", list(SEARCH_SHAPES))
def test_a_rate_limited_search_exits_1_and_says_so(tmp_path, caplog, name):
    error = RateLimitError("rate limited by OddsPortal: HTTP 429 on page x", url="x", retry_after=0)
    out = tmp_path / "out.json"
    with patch("oddsharvester.cli.commands.search.run_search", new_callable=AsyncMock, side_effect=error):
        result = _invoke(SEARCH_SHAPES[name], out)

    assert result.exit_code == 1, result.output
    assert not out.exists()
    assert "rate limited by OddsPortal" in caplog.text
    assert "Traceback" not in caplog.text, "tipster_watch reads a traceback as a crash"


def test_a_team_id_oddsportal_does_not_know_exits_1_and_says_so(tmp_path, caplog):
    error = PageNotFoundError("Team id zzzzzzzz does not exist on OddsPortal: its search page names no team.", "x")
    out = tmp_path / "out.json"
    with patch("oddsharvester.cli.commands.search.run_search", new_callable=AsyncMock, side_effect=error):
        result = _invoke(["search", "--team-id", "zzzzzzzz"], out)

    assert result.exit_code == 1, result.output
    assert not out.exists()
    assert "does not exist on OddsPortal" in caplog.text
