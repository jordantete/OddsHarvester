"""Integration tests for the team command.

Re-capture the fixture with:
    ODDSHARVESTER_HAR_RECORD=tests/integration/fixtures/team/teams.har \\
        uv run oddsharvester team --team lId4TMwf,zzzzzzzz,WGt8En5I --headless \\
        -o tests/integration/fixtures/team/teams.json

The wrong id in the middle is deliberate: it keeps the failure path in the
replay, and it is what a typo in a spreadsheet column looks like.
"""

import json
import os
from pathlib import Path
import subprocess

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "team"
TEAMS_HAR = FIXTURES / "teams.har"
TEAMS_SNAPSHOT = FIXTURES / "teams.json"

LIVERPOOL = "lId4TMwf"
BARCELONA_FC = "WGt8En5I"
WRONG_ID = "zzzzzzzz"


def _run(args: list[str], output: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        ["uv", "run", "oddsharvester", "team", *args, "--headless", "-o", str(output)],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=300,
        env=env or os.environ.copy(),
    )


def _without_timestamp(record: dict) -> dict:
    return {key: value for key, value in record.items() if key != "scraped_at"}


@pytest.mark.integration
def test_team_command_har_replay(temp_output_dir):
    """Liverpool carries every field; Barcelona FC carries none of the venue ones."""
    output = temp_output_dir / "out.json"
    env = os.environ.copy()
    env["ODDSHARVESTER_HAR_REPLAY"] = str(TEAMS_HAR)

    result = _run(["--team", f"{LIVERPOOL},{WRONG_ID},{BARCELONA_FC}"], output, env)

    assert result.returncode == 0, f"stderr: {result.stderr[-2000:]}"

    records = json.loads(output.read_text())
    expected = json.loads(TEAMS_SNAPSHOT.read_text())
    assert [_without_timestamp(r) for r in records] == [_without_timestamp(r) for r in expected]

    liverpool, barcelona = records
    assert liverpool["list_name"] == "Liverpool"
    assert liverpool["venue"] == "Anfield"
    assert barcelona["list_name"] == "Barcelona", "resolved although the page shows no odds rows"
    assert barcelona["venue"] is None


@pytest.mark.integration
def test_a_wrong_team_id_is_reported_without_costing_the_other_teams(temp_output_dir):
    """A wrong id returns a page that looks valid, so it must fail loudly and alone."""
    output = temp_output_dir / "out.json"
    env = os.environ.copy()
    env["ODDSHARVESTER_HAR_REPLAY"] = str(TEAMS_HAR)

    result = _run(["--team", f"{LIVERPOOL},{WRONG_ID},{BARCELONA_FC}"], output, env)

    assert result.returncode == 0, "one bad id must not fail a run that produced records"
    assert WRONG_ID in result.stderr
    assert [record["team_id"] for record in json.loads(output.read_text())] == [LIVERPOOL, BARCELONA_FC]


@pytest.mark.integration
@pytest.mark.live_only
def test_team_command_against_the_live_site(temp_output_dir):
    """The HAR is a frozen snapshot, so only this catches OddsPortal moving the payload.

    Values change over time (coach, form, league), so only the shape is asserted.
    """
    output = temp_output_dir / "out.json"

    result = _run(["--team", f"{LIVERPOOL},{BARCELONA_FC}"], output)

    assert result.returncode == 0, f"stderr: {result.stderr[-2000:]}"

    liverpool, barcelona = json.loads(output.read_text())

    assert liverpool["name"], "the breadcrumb no longer yields a name"
    assert liverpool["full_name"], "the header logo alt no longer yields a full name"
    assert liverpool["list_name"], "the form block no longer yields a list name"
    assert liverpool["venue"], "basicInfo lost its venue"
    assert liverpool["town"], "basicInfo lost its venue town"
    assert liverpool["country"], "basicInfo lost its venue country"
    assert liverpool["coach"], "basicInfo lost its coach"
    assert liverpool["logo_url"].startswith("https://www.oddsportal.com/proxy/serve/images/team-logo/")
    assert liverpool["team_url"].endswith(f"/{LIVERPOOL}/"), "the canonical slug is no longer recoverable"
    assert liverpool["form"], "lastPerformance lost its form"
    assert liverpool["avg_goals_scored"] is not None, "lastPerformance lost its averages"

    # A team the selected bookmakers price nothing for: identity must still resolve.
    assert barcelona["list_name"], "list_name no longer survives a page with no odds rows"
    assert barcelona["coach"]
