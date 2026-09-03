import pytest

from oddsharvester.utils.league_aliases import LEAGUE_SEASON_ALIASES, get_league_slug_for_season
from oddsharvester.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from oddsharvester.utils.sport_market_constants import Sport


class TestGetLeagueSlugForSeason:
    """Tests for get_league_slug_for_season()."""

    @pytest.mark.parametrize(
        ("sport", "league", "season", "expected_slug"),
        [
            # Czech Republic: fortuna-liga until 2023-2024, then chance-liga
            (Sport.FOOTBALL, "czech-republic-chance-liga", "2022-2023", "fortuna-liga"),
            (Sport.FOOTBALL, "czech-republic-chance-liga", "2023-2024", "fortuna-liga"),
            (Sport.FOOTBALL, "czech-republic-chance-liga", "2024-2025", None),
            (Sport.FOOTBALL, "czech-republic-chance-liga", "2025-2026", None),
            # Slovakia: fortuna-liga until 2022-2023, then nike-liga
            (Sport.FOOTBALL, "slovakia-nike-liga", "2021-2022", "fortuna-liga"),
            (Sport.FOOTBALL, "slovakia-nike-liga", "2022-2023", "fortuna-liga"),
            (Sport.FOOTBALL, "slovakia-nike-liga", "2023-2024", None),
            # Hungary: otp-bank-liga until 2024-2025, then nb-i
            (Sport.FOOTBALL, "hungary-nb-i", "2023-2024", "otp-bank-liga"),
            (Sport.FOOTBALL, "hungary-nb-i", "2024-2025", "otp-bank-liga"),
            (Sport.FOOTBALL, "hungary-nb-i", "2025-2026", None),
            # Spain: primera-division until 2015-2016, then laliga
            (Sport.FOOTBALL, "spain-laliga", "2010-2011", "primera-division"),
            (Sport.FOOTBALL, "spain-laliga", "2015-2016", "primera-division"),
            (Sport.FOOTBALL, "spain-laliga", "2016-2017", None),
            # Mexico: primera-division until 2018-2019, then liga-mx
            (Sport.FOOTBALL, "mexico-liga-mx", "2012-2013", "primera-division"),
            (Sport.FOOTBALL, "mexico-liga-mx", "2018-2019", "primera-division"),
            (Sport.FOOTBALL, "mexico-liga-mx", "2019-2020", None),
            # Norway: tippeligaen until 2016, then eliteserien
            (Sport.FOOTBALL, "norway-eliteserien", "2016", "tippeligaen"),
            (Sport.FOOTBALL, "norway-eliteserien", "2017", None),
            # Portugal second tier: three successive slugs before liga-portugal-2
            (Sport.FOOTBALL, "liga-portugal-2", "2011-2012", "liga-de-honra"),
            (Sport.FOOTBALL, "liga-portugal-2", "2012-2013", "segunda-liga"),
            (Sport.FOOTBALL, "liga-portugal-2", "2016-2017", "ligapro"),
            (Sport.FOOTBALL, "liga-portugal-2", "2020-2021", None),
            # Brazil: serie-a until 2023, then serie-a-betano
            (Sport.FOOTBALL, "brazil-serie-a", "2022", "serie-a"),
            (Sport.FOOTBALL, "brazil-serie-a", "2023", "serie-a"),
            (Sport.FOOTBALL, "brazil-serie-a", "2024", None),
            (Sport.FOOTBALL, "brazil-serie-a", "2025", None),
            # South Africa: premier-league until 2023-2024, then betway-premiership
            (Sport.FOOTBALL, "south-africa-premiership", "2022-2023", "premier-league"),
            (Sport.FOOTBALL, "south-africa-premiership", "2023-2024", "premier-league"),
            (Sport.FOOTBALL, "south-africa-premiership", "2024-2025", None),
            # Bulgaria: parva-liga until 2024-2025, then efbet-league
            (Sport.FOOTBALL, "bulgaria-parva-liga", "2023-2024", "parva-liga"),
            (Sport.FOOTBALL, "bulgaria-parva-liga", "2024-2025", "parva-liga"),
            (Sport.FOOTBALL, "bulgaria-parva-liga", "2025-2026", None),
            # Single year format
            (Sport.FOOTBALL, "czech-republic-chance-liga", "2023", "fortuna-liga"),
            (Sport.FOOTBALL, "czech-republic-chance-liga", "2024", None),
        ],
    )
    def test_alias_resolution(self, sport, league, season, expected_slug):
        assert get_league_slug_for_season(sport, league, season) == expected_slug

    @pytest.mark.parametrize(
        ("sport", "league", "season"),
        [
            # No alias for this league
            (Sport.FOOTBALL, "england-premier-league", "2023-2024"),
            # No alias for this sport
            (Sport.TENNIS, "atp-tour", "2023-2024"),
            # No season provided
            (Sport.FOOTBALL, "czech-republic-chance-liga", None),
            (Sport.FOOTBALL, "czech-republic-chance-liga", ""),
            # Invalid season format
            (Sport.FOOTBALL, "czech-republic-chance-liga", "invalid"),
            (Sport.FOOTBALL, "czech-republic-chance-liga", "2023/2024"),
        ],
    )
    def test_returns_none_when_no_alias_applies(self, sport, league, season):
        assert get_league_slug_for_season(sport, league, season) is None


class TestLeagueSeasonAliasesStructure:
    """Tests for LEAGUE_SEASON_ALIASES data structure integrity."""

    def test_all_sport_keys_are_valid(self):
        for sport in LEAGUE_SEASON_ALIASES:
            assert isinstance(sport, Sport)

    def test_all_max_years_are_integers(self):
        for sport_aliases in LEAGUE_SEASON_ALIASES.values():
            for league_aliases in sport_aliases.values():
                for max_year in league_aliases:
                    assert isinstance(max_year, int)

    def test_all_league_keys_exist_in_url_mapping(self):
        for sport, sport_aliases in LEAGUE_SEASON_ALIASES.items():
            for league in sport_aliases:
                assert league in SPORTS_LEAGUES_URLS_MAPPING[sport]

    def test_all_alias_slugs_are_non_empty_strings(self):
        for sport_aliases in LEAGUE_SEASON_ALIASES.values():
            for league_aliases in sport_aliases.values():
                for slug in league_aliases.values():
                    assert isinstance(slug, str)
                    assert len(slug) > 0
