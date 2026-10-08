"""Integration tests for the search command.

Re-capture the fixtures with:
    uv run python scripts/capture_all_hars.py --only search

A wrong team id exits 1 and writes nothing, so it cannot be captured; the live test covers it.
"""

import base64
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "search"
CANDIDATES_HAR = FIXTURES / "candidates.har"
TEAM_MATCHES_HAR = FIXTURES / "team_matches.har"

ARSENAL = "hA1Zm19f"
NACIONAL_POTOSI = "hUyau0Vc"
_CANDIDATE_LINK = re.compile(r'href="/search/results/:([A-Za-z0-9]{8})/"')
_UTC = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC")


def _run(args: list[str], output: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        ["uv", "run", "oddsharvester", "search", *args, "--headless", "-o", str(output)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=300,
        env=env or os.environ.copy(),
    )


def _replay(har: Path) -> dict:
    env = os.environ.copy()
    env["ODDSHARVESTER_HAR_REPLAY"] = str(har)
    return env


def _document(har: Path, path: str) -> str:
    """The HTML the site served for `path`, as the HAR holds it."""
    for entry in json.loads(har.read_text())["log"]["entries"]:
        content = entry["response"]["content"]
        if entry["request"]["url"].endswith(path) and "text/html" in content.get("mimeType", ""):
            text = content.get("text", "")
            return base64.b64decode(text).decode() if content.get("encoding") == "base64" else text
    raise AssertionError(f"{har.name} holds no document for {path}")


@pytest.mark.integration
def test_candidates_har_replay(temp_output_dir):
    output = temp_output_dir / "out.json"

    result = _run(["--query", "Nacional", "--sport", "football"], output, _replay(CANDIDATES_HAR))

    assert result.returncode == 0, f"stderr: {result.stderr[-2000:]}"
    candidates = json.loads(output.read_text())
    assert candidates == json.loads(CANDIDATES_HAR.with_suffix(".json").read_text())
    assert {
        "team_id": NACIONAL_POTOSI,
        "name": "Nacional Potosi",
        "country": "Bolivia",
        "sport": "football",
        "team_url": f"https://www.oddsportal.com/football/team/nacional-potosi/{NACIONAL_POTOSI}/",
    } in candidates
    assert not [c["name"] for c in candidates if "<" in c["name"] or "&" in c["name"]]


@pytest.mark.integration
def test_candidates_come_in_the_order_the_page_shows_them(temp_output_dir):
    output = temp_output_dir / "out.json"

    result = _run(["--query", "Nacional", "--sport", "football"], output, _replay(CANDIDATES_HAR))

    assert result.returncode == 0, f"stderr: {result.stderr[-2000:]}"
    served = _document(CANDIDATES_HAR, "/search/results/Nacional/football/")
    shown = list(dict.fromkeys(_CANDIDATE_LINK.findall(served)))
    assert [c["team_id"] for c in json.loads(output.read_text())] == shown


@pytest.mark.integration
def test_team_matches_har_replay(temp_output_dir):
    output = temp_output_dir / "out.json"

    result = _run(["--team-id", ARSENAL], output, _replay(TEAM_MATCHES_HAR))

    assert result.returncode == 0, f"stderr: {result.stderr[-2000:]}"
    matches = json.loads(output.read_text())
    assert matches == json.loads(TEAM_MATCHES_HAR.with_suffix(".json").read_text())
    assert {m["tab"] for m in matches} == {"next", "results"}
    assert all(ARSENAL in (m["home_team_id"], m["away_team_id"]) for m in matches), "a row without the team is a trap"
    assert all(_UTC.fullmatch(m["kickoff_utc"]) for m in matches)
    assert len({m["match_link"] for m in matches}) == len(matches)


@pytest.mark.integration
@pytest.mark.live_only
def test_search_against_the_live_site(temp_output_dir):
    """The HARs are frozen; only this catches OddsPortal moving the searchData payload."""
    teams = temp_output_dir / "teams.json"
    result = _run(["--query", "Nacional Potosi", "--sport", "football"], teams)
    assert result.returncode == 0, f"stderr: {result.stderr[-2000:]}"
    assert any(c["team_id"] == NACIONAL_POTOSI and c["country"] == "Bolivia" for c in json.loads(teams.read_text()))

    matches_out = temp_output_dir / "matches.json"
    result = _run(["--team-id", NACIONAL_POTOSI], matches_out)
    assert result.returncode == 0, f"stderr: {result.stderr[-2000:]}"
    matches = json.loads(matches_out.read_text())
    assert matches, "the results tab lists the team's past matches"
    assert all(NACIONAL_POTOSI in (m["home_team_id"], m["away_team_id"]) for m in matches)
    assert all(m["kickoff_utc"] and m["league_url"] for m in matches)

    unknown = temp_output_dir / "unknown.json"
    result = _run(["--team-id", "zzzzzzzz"], unknown)
    assert result.returncode == 1
    assert "does not exist on OddsPortal" in result.stderr
    assert not unknown.exists()
