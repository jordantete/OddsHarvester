import importlib

import pytest

import oddsharvester.utils.sport_league_constants as _slc_module
from oddsharvester.utils.sport_market_constants import Sport


@pytest.fixture(autouse=True)
def fresh_mapping():
    """Reload the production module so mutations from other test files don't bleed in."""
    importlib.reload(_slc_module)
    return _slc_module.SPORTS_LEAGUES_URLS_MAPPING


class TestHandballLeagueConstants:
    """Guards the production handball league mapping (Reddit Bettet follow-up)."""

    def test_handball_sport_present(self, fresh_mapping):
        assert Sport.HANDBALL in fresh_mapping

    def test_handball_expected_leagues(self, fresh_mapping):
        leagues = fresh_mapping[Sport.HANDBALL]
        expected = {
            "ehf-champions-league",
            "ehf-european-league",
            "germany-bundesliga",
            "france-lnh",
            "spain-liga-asobal",
            "denmark-handboldligaen",
            "hungary-nb-i",
        }
        assert expected.issubset(set(leagues.keys()))

    def test_handball_urls_well_formed(self, fresh_mapping):
        leagues = fresh_mapping[Sport.HANDBALL]
        for slug, url in leagues.items():
            assert url.startswith("https://www.oddsportal.com/handball/"), f"{slug}: {url}"
            assert url.endswith("/"), f"{slug} URL must end with '/': {url}"

    def test_ehf_champions_league_url(self, fresh_mapping):
        assert (
            fresh_mapping[Sport.HANDBALL]["ehf-champions-league"]
            == "https://www.oddsportal.com/handball/europe/ehf-champions-league/"
        )
