import pytest
from src.core.url_builder import URLBuilder
from src.utils.constants import ODDSPORTAL_BASE_URL
from src.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from src.utils.sport_market_constants import Sport

SPORTS_LEAGUES_URLS_MAPPING[Sport.FOOTBALL] = {
    "england-premier-league": f"{ODDSPORTAL_BASE_URL}/football/england/premier-league",
    "la-liga": f"{ODDSPORTAL_BASE_URL}/football/spain/la-liga",
}
SPORTS_LEAGUES_URLS_MAPPING[Sport.TENNIS] = {
    "atp-tour": f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour",
}

@pytest.mark.parametrize(
    "sport, league, season, expected_url",
    [
        # Valid cases
        ("football", "england-premier-league", "2023-2024", f"{ODDSPORTAL_BASE_URL}/football/england/premier-league-2023-2024/results/"),
        ("tennis", "atp-tour", "2024-2025", f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour-2024-2025/results/"),
        # Without season, should return base league URL
        ("football", "england-premier-league", None, f"{ODDSPORTAL_BASE_URL}/football/england/premier-league"),
    ]
)
def test_get_historic_matches_url(sport, league, season, expected_url):
    assert URLBuilder.get_historic_matches_url(sport, league, season) == expected_url

def test_get_historic_matches_url_invalid_season():
    with pytest.raises(ValueError, match="Invalid season format: 20-2024. Expected format: 'YYYY' or 'YYYY-YYYY'."):
        URLBuilder.get_historic_matches_url("football", "england-premier-league", "20-2024")

@pytest.mark.parametrize(
    "sport, date, league, expected_url",
    [
        # With league
        ("football", "2025-02-10", "england-premier-league", f"{ODDSPORTAL_BASE_URL}/football/england/premier-league"),
        # Without league
        ("football", "2025-02-10", None, f"{ODDSPORTAL_BASE_URL}/matches/football/2025-02-10/"),
    ]
)
def test_get_upcoming_matches_url(sport, date, league, expected_url):
    assert URLBuilder.get_upcoming_matches_url(sport, date, league) == expected_url

@pytest.mark.parametrize(
    "sport, league, expected_url",
    [
        ("football", "england-premier-league", f"{ODDSPORTAL_BASE_URL}/football/england/premier-league"),
        ("tennis", "atp-tour", f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour"),
    ]
)
def test_get_league_url(sport, league, expected_url):
    assert URLBuilder.get_league_url(sport, league) == expected_url

def test_get_league_url_invalid_sport():
    """Test get_league_url raises ValueError for unsupported sport."""
    with pytest.raises(ValueError, match="'handball' is not a valid Sport"):
        URLBuilder.get_league_url("handball", "champions-league")

def test_get_league_url_invalid_league():
    with pytest.raises(ValueError, match="Invalid league 'random-league' for sport 'football'. Available: england-premier-league, la-liga"):
        URLBuilder.get_league_url("football", "random-league")