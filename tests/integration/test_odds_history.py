"""
Integration test for --odds-history, run with the odds_evolution_collector's flags.

The collector pairs odds_history_data with the outcome keys of each bookmaker entry by
position, so the contract tests pin that shape on top of the golden comparison.

Recapture (live):
    uv run python -m tests.integration.helpers.capture --sport football --league premier-league \\
        --match-url "https://www.oddsportal.com/football/h2h/chelsea-4fGZN2oK/manchester-city-Wtn9Stg0/#lMp9YMye" \\
        --match-dir manchester-city-chelsea-lMp9YMye --markets "1x2,over_under_2_5" --period full_time \\
        --bookies-filter all --season 2025-2026 --odds-history --timezone Europe/London \\
        --locale en-GB --request-delay 2 --concurrency 3 --capture-har
scripts/capture_all_hars.py skips this fixture: it does not know the odds-history flags.
"""

from datetime import datetime
import json
import re

import pytest

from tests.integration.helpers.cli_runner import run_historic
from tests.integration.helpers.comparison import compare_match_data
from tests.integration.helpers.fixture_files import FIXTURES_DIR, har_path_for, require_file

pytestmark = pytest.mark.integration

MATCH_URL = "https://www.oddsportal.com/football/h2h/chelsea-4fGZN2oK/manchester-city-Wtn9Stg0/#lMp9YMye"
FIXTURE = (
    FIXTURES_DIR
    / "football"
    / "premier-league"
    / "manchester-city-chelsea-lMp9YMye"
    / "1x2_over_under_2_5_full_time_all_odds_history.json"
)
MARKETS = ["1x2", "over_under_2_5"]
COLLECTOR_ARGS = [
    "--odds-history",
    "--timezone",
    "Europe/London",
    "--locale",
    "en-GB",
    "--request-delay",
    "2",
    "--concurrency",
    "3",
]
META_KEYS = ("bookmaker_name", "period", "odds_history_data", "submarket_name", "blocked_outcomes")
NAIVE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
MATCH_DATE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC$")


@pytest.fixture(scope="module")
def run(request, tmp_path_factory):
    expected = json.loads(require_file(FIXTURE).read_text())
    output_path = tmp_path_factory.mktemp("odds_history") / "output"
    exit_code, _stdout, stderr = run_historic(
        sport="football",
        match_link=MATCH_URL,
        markets=MARKETS,
        output_path=output_path,
        period="full_time",
        season="2025-2026",
        timeout=900,
        har_path=har_path_for(FIXTURE, request.config.getoption("--live")),
        extra_args=COLLECTOR_ARGS,
    )
    output_file = output_path.with_suffix(".json")
    actual = json.loads(output_file.read_text()) if output_file.exists() else None
    return {"exit_code": exit_code, "stderr": stderr, "actual": actual, "expected": expected}


def _match(run):
    if not run["actual"]:
        pytest.fail(f"No output (exit {run['exit_code']}): {run['stderr'][-2000:]}")
    return run["actual"][0]


def _entries(match):
    for key, entries in match.items():
        if key.endswith("_market"):
            for entry in entries:
                yield key, entry


def _labels(entry):
    return [key for key in entry if key not in META_KEYS]


def _blocks(entry):
    return entry.get("odds_history_data") or []


def test_run_succeeds(run):
    assert run["exit_code"] == 0, run["stderr"][-2000:]
    _match(run)


def test_matches_golden(run):
    result = compare_match_data(_match(run), run["expected"][0])
    assert result.passed, str(result)


@pytest.mark.xfail(
    strict=True,
    reason="odds_history_extractor also matches the non-leaf row of an expanded submarket, "
    "so a bookmaker collects extra history blocks",
)
def test_one_history_block_per_outcome(run):
    mismatches = [
        (key, entry.get("bookmaker_name"), entry.get("submarket_name"), len(_labels(entry)), len(_blocks(entry)))
        for key, entry in _entries(_match(run))
        if len(_labels(entry)) != len(_blocks(entry))
    ]
    assert not mismatches, mismatches


def test_history_blocks_have_the_collector_shape(run):
    for key, entry in _entries(_match(run)):
        for block in _blocks(entry):
            assert isinstance(block, dict), (key, entry.get("bookmaker_name"), block)
            assert "odds_history" in block, (key, entry.get("bookmaker_name"), block)
            assert "opening_odds" in block, (key, entry.get("bookmaker_name"), block)


def test_history_timestamps_are_naive_iso(run):
    for key, entry in _entries(_match(run)):
        for block in _blocks(entry):
            points = list(block.get("odds_history") or [])
            if block.get("opening_odds"):
                points.append(block["opening_odds"])
            for point in points:
                assert NAIVE_ISO.match(point["timestamp"]), (key, entry.get("bookmaker_name"), point)
                assert datetime.fromisoformat(point["timestamp"]).tzinfo is None


def test_match_date_format(run):
    assert MATCH_DATE.match(_match(run)["match_date"])


def test_outcome_keys_come_before_meta_keys(run):
    for key, entry in _entries(_match(run)):
        labels = _labels(entry)
        assert list(entry)[: len(labels)] == labels, (key, list(entry))
