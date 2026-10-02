"""Integration tests for football scraping."""

import copy
import json
from pathlib import Path
import re

import pytest

from tests.integration.helpers.cli_runner import run_historic
from tests.integration.helpers.comparison import compare_golden
from tests.integration.helpers.replay import is_live, load_golden, replay_and_compare, run_replay

# Match configurations
LEICESTER_BRENTFORD = {
    "sport": "football",
    "league": "premier-league",
    "match_id": "leicester-brentford-xQ77QTN0",
    "url": "https://www.oddsportal.com/football/h2h/brentford-xYe7DwID/leicester-KrrdAMyI/#xQ77QTN0",
}

REAL_MADRID_BARCELONA = {
    "sport": "football",
    "league": "super-cup-2025",
    "match_id": "real-madrid-barcelona-bZrHkILa",
    "url": "https://www.oddsportal.com/football/h2h/barcelona-SKbpVP5K/real-madrid-W8mj7MDD/#bZrHkILa",
}


@pytest.mark.integration
class TestFootballBasicMarkets:
    """Tests for basic football markets."""

    def test_fb_001_1x2_full_time(self, har_for_match, tmp_path):
        """FB-001: Test 1x2 market, full time, all bookies."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_full_time_all.json",
            markets=["1x2"],
            period="full_time",
            bookies_filter="all",
        )

    def test_fb_002_multiple_markets(self, har_for_match, tmp_path):
        """FB-002: Test 1x2 + btts + double_chance markets."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_btts_double_chance_full_time_all.json",
            markets=["1x2", "btts", "double_chance"],
        )

    def test_fb_003_over_under(self, har_for_match, tmp_path):
        """FB-003: Test over/under markets."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "over_under_1_5_over_under_2_5_full_time_all.json",
            markets=["over_under_2_5", "over_under_1_5"],
        )

    def test_fb_004_over_under_umbrella(self, har_for_match, tmp_path):
        """FB-004: Test the over_under umbrella token expands into per-line markets.

        Reuses the FB-003 fixture (captured for the explicit over_under_1_5 /
        over_under_2_5 lines) but requests the umbrella token `over_under` instead.
        The umbrella enumerates every O/U line rendered on the page and produces one
        `{token}_market` key per line rather than a single `over_under_market` key.
        Only the two lines this fixture was captured for are asserted here, since
        those are the ones guaranteed to carry real odds data under HAR replay.
        """
        fixture_name = "over_under_1_5_over_under_2_5_full_time_all.json"
        actual = run_replay(har_for_match, tmp_path, LEICESTER_BRENTFORD, fixture_name, markets=["over_under"])
        expected = load_golden(LEICESTER_BRENTFORD, fixture_name)

        # The umbrella also yields lines this fixture was not captured for; compare only the captured ones.
        captured = {k: v for k, v in actual[0].items() if not k.endswith("_market") or k in expected[0]}
        live = is_live(har_for_match, LEICESTER_BRENTFORD, fixture_name)
        result = compare_golden(captured, expected[0], live=live)
        assert result.passed, str(result)

        record = actual[0]

        # Umbrella must expand into per-line keys, not collapse to a single market key.
        assert "over_under_market" not in record

        for line_key in ("over_under_1_5_market", "over_under_2_5_market"):
            assert line_key in record, f"Expected umbrella to produce '{line_key}'"
            assert record[line_key], f"'{line_key}' should be non-empty"
            if not live:
                assert record[line_key] == expected[0][line_key]

    def test_fb_008_local_kickoff(self, har_for_match, tmp_path):
        """FB-008: Test --local-kickoff adds venue_timezone and match_date_venue_local, UTC untouched."""
        actual = run_replay(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_full_time_all.json",
            markets=["1x2"],
            period="full_time",
            bookies_filter="all",
            local_kickoff=True,
        )

        record = actual[0]
        assert record["venue_timezone"] == "Europe/London"
        assert record["match_date_venue_local"] is not None
        assert record["match_date"].endswith("UTC")

    def test_fb_007_real_madrid_barcelona(self, har_for_match, tmp_path):
        """FB-007: Test Real Madrid vs Barcelona."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            REAL_MADRID_BARCELONA,
            "1x2_btts_full_time_all.json",
            markets=["1x2", "btts"],
        )


@pytest.mark.integration
class TestFootballPeriods:
    """Tests for football period options."""

    def test_fb_005_1st_half(self, har_for_match, tmp_path):
        """FB-005: Test 1x2 market, 1st half period."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_1st_half_all.json",
            markets=["1x2"],
            period="1st_half",
        )


@pytest.mark.integration
class TestFootballBookiesFilter:
    """Tests for football bookies filter option."""

    def test_fb_006_classic_bookies(self, har_for_match, tmp_path):
        """FB-006: Test 1x2 market with classic bookies only."""
        replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_full_time_classic.json",
            markets=["1x2"],
            bookies_filter="classic",
        )


@pytest.mark.integration
class TestFootballPreview:
    """Tests for --preview-only, which reads each line's collapsed row instead of every bookmaker."""

    def test_fb_009_preview_only(self, har_for_match, tmp_path):
        """FB-009: Over/Under is scraped once for both lines, and each line token holds every visible line.

        Its capture command is the SPECIAL_FIXTURES entry in scripts/capture_all_hars.py.
        """
        record = replay_and_compare(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_over_under_1_5_over_under_2_5_full_time_all_preview.json",
            markets=["1x2", "over_under_1_5", "over_under_2_5"],
            period="full_time",
            extra_args=["--preview-only"],
        )[0]

        assert record["over_under_1_5_market"], "preview mode returned no Over/Under line"
        assert record["over_under_1_5_market"] == record["over_under_2_5_market"]
        assert {entry.get("extraction_mode") for entry in record["over_under_1_5_market"]} == {"passive"}


MANCHESTER_CITY_CHELSEA = {
    "sport": "football",
    "league": "premier-league",
    "match_id": "manchester-city-chelsea-lMp9YMye",
    "url": "https://www.oddsportal.com/football/h2h/chelsea-4fGZN2oK/manchester-city-Wtn9Stg0/#lMp9YMye",
}


def _drop(entries, i, _one):
    del entries[i]


def _refuse(entries, i, _one):
    entries[i]["response"]["status"] = 503


def _empty(entries, i, _one):
    entries[i]["response"]["content"]["text"] = ""


def _serve_1x2(entries, i, one):
    entries[i]["response"] = copy.deepcopy(one["response"])


def _add_1x2(entries, market_id, one):
    """A request the HAR never held, for market `market_id`, answered with the 1X2 data."""
    added = copy.deepcopy(one)
    added["request"]["url"] = re.sub(r"-1-(\d+)-([^-/]+\.dat)", rf"-{market_id}-\1-\2", one["request"]["url"])
    entries.append(added)


@pytest.mark.integration
class TestAMarketWhoseDataDidNotCome:
    """Each way OddsPortal can fail the data request of a market switch fails the match (gotchas §27).

    The HAR is edited: replays abort a request it does not hold. Without the guard each run exits 0, with the
    market empty or holding the 1X2 odds (seen live on 2026-10-02 for btts, double chance and over/under).
    """

    @staticmethod
    def _run(har_for_match, tmp_path, match, fixture_name, market_id, edit, markets, bookies_filter="all"):
        if is_live(har_for_match, match, fixture_name):
            pytest.skip("edits a recorded request; the live site has none to edit")
        har = json.loads(
            Path(har_for_match(match["sport"], match["league"], match["match_id"], fixture_name)).read_text()
        )
        entries = har["log"]["entries"]
        event = match["url"].rsplit("#", 1)[1]

        def data_of(market):
            pattern = re.compile(rf"/proxy/match-event/[^/?]*-{event}-{market}-2-")
            return [i for i, entry in enumerate(entries) if pattern.search(entry["request"]["url"])]

        one = entries[data_of(1)[0]]
        if edit is _add_1x2:
            _add_1x2(entries, market_id, one)
        else:
            for i in reversed(data_of(market_id)):
                edit(entries, i, one)
        edited = tmp_path / "edited.har"
        edited.write_text(json.dumps(har))
        output_path = tmp_path / "output"

        exit_code, _stdout, stderr = run_historic(
            sport=match["sport"],
            match_link=match["url"],
            markets=markets,
            output_path=output_path,
            bookies_filter=bookies_filter,
            har_path=edited,
        )

        assert exit_code == 1, stderr[-2000:]
        assert not Path(f"{output_path}.json").exists()
        return stderr

    @pytest.mark.parametrize(
        ("edit", "reason"),
        [
            (_drop, "OddsPortal refused the data of the view 'bts;2': no response"),
            (_refuse, "OddsPortal refused the data of the view 'bts;2': HTTP 503"),
            (_empty, "The view 'bts;2' did not render within 5500 ms"),
            (_serve_1x2, "OddsPortal sent the data of market 1 for the view 'bts;2'"),
        ],
        ids=["dropped", "refused", "empty", "1X2 data"],
    )
    @pytest.mark.parametrize("bookies_filter", ["all", "crypto"])
    def test_btts_without_its_data_fails_the_match(self, har_for_match, tmp_path, edit, reason, bookies_filter):
        stderr = self._run(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_btts_double_chance_full_time_all.json",
            13,
            edit,
            ["1x2", "btts", "double_chance"],
            bookies_filter,
        )

        assert reason in stderr

    def test_a_handicap_line_given_the_1x2_data_fails_the_match(self, har_for_match, tmp_path):
        """Rendered from the 1X2 data the view shows a line "Asian Handicap 0", a real token: its odds were 1X2's."""
        stderr = self._run(
            har_for_match,
            tmp_path,
            LEICESTER_BRENTFORD,
            "1x2_btts_double_chance_full_time_all.json",
            5,
            _add_1x2,
            ["1x2", "asian_handicap_0"],
        )

        assert "OddsPortal sent the data of market 1 for the view 'ah;2'" in stderr

    def test_over_under_given_the_1x2_data_fails_the_match(self, har_for_match, tmp_path):
        stderr = self._run(
            har_for_match,
            tmp_path,
            MANCHESTER_CITY_CHELSEA,
            "1x2_over_under_2_5_full_time_all_odds_history.json",
            2,
            _serve_1x2,
            ["1x2", "over_under_2_5"],
        )

        assert "OddsPortal sent the data of market 1 for the view 'over-under;2'" in stderr
