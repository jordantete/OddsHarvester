import pytest

from oddsharvester.utils.league_aliases import LEAGUE_SEASON_ALIASES, get_league_slug_for_season
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
            # Slovakia: fortuna-liga until 2023-2024, then nike-liga
            (Sport.FOOTBALL, "slovakia-nike-liga", "2021-2022", "fortuna-liga"),
            (Sport.FOOTBALL, "slovakia-nike-liga", "2023-2024", "fortuna-liga"),
            (Sport.FOOTBALL, "slovakia-nike-liga", "2024-2025", None),
            # Hungary: otp-bank-liga until 2023-2024, then nb-i
            (Sport.FOOTBALL, "hungary-nb-i", "2023-2024", "otp-bank-liga"),
            (Sport.FOOTBALL, "hungary-nb-i", "2024-2025", None),
            # Cyprus: cyta-championship until 2023-2024, then 1st-division
            (Sport.FOOTBALL, "cyprus-first-division", "2023-2024", "cyta-championship"),
            (Sport.FOOTBALL, "cyprus-first-division", "2024-2025", None),
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

    def test_all_alias_slugs_are_non_empty_strings(self):
        for sport_aliases in LEAGUE_SEASON_ALIASES.values():
            for league_aliases in sport_aliases.values():
                for slug in league_aliases.values():
                    assert isinstance(slug, str)
                    assert len(slug) > 0
