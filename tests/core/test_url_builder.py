import pytest

from src.core.url_builder import URLBuilder
from src.utils.constants import ODDSPORTAL_BASE_URL
from src.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from src.utils.sport_market_constants import Sport

# Create test mapping for sports and leagues
SPORTS_LEAGUES_URLS_MAPPING[Sport.FOOTBALL] = {
    "england-premier-league": f"{ODDSPORTAL_BASE_URL}/football/england/premier-league",
    "la-liga": f"{ODDSPORTAL_BASE_URL}/football/spain/la-liga",
}
SPORTS_LEAGUES_URLS_MAPPING[Sport.TENNIS] = {
    "atp-tour": f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour",
}
SPORTS_LEAGUES_URLS_MAPPING[Sport.BASEBALL] = {
    "mlb": f"{ODDSPORTAL_BASE_URL}/baseball/usa/mlb",
    "japan-npb": f"{ODDSPORTAL_BASE_URL}/baseball/japan/npb",
}


@pytest.mark.parametrize(
    ("sport", "league", "season", "expected_url"),
    [
        # Valid cases with specific seasons
        (
            "football",
            "england-premier-league",
            "2023-2024",
            f"{ODDSPORTAL_BASE_URL}/football/england/premier-league-2023-2024/results/",
        ),
        ("tennis", "atp-tour", "2024-2025", f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour-2024-2025/results/"),
        # Empty season cases (representing current season)
        ("football", "england-premier-league", "", f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/results/"),
        ("football", "england-premier-league", None, f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/results/"),
        # Single year format
        ("tennis", "atp-tour", "2024", f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour-2024/results/"),
        # Baseball special cases (should only use first year)
        ("baseball", "mlb", "2023-2024", f"{ODDSPORTAL_BASE_URL}/baseball/usa/mlb-2023/results/"),
        ("baseball", "japan-npb", "2024-2025", f"{ODDSPORTAL_BASE_URL}/baseball/japan/npb-2024/results/"),
    ],
)
def test_get_historic_matches_url(sport, league, season, expected_url):
    """Test building URLs for historical matches with various inputs."""
    assert URLBuilder.get_historic_matches_url(sport, league, season) == expected_url


@pytest.mark.parametrize(
    ("sport", "league", "season", "error_msg"),
    [
        # Invalid season format
        (
            "football",
            "england-premier-league",
            "20-2024",
            "Invalid season format: 20-2024. Expected format: 'YYYY' or 'YYYY-YYYY'",
        ),
        (
            "football",
            "england-premier-league",
            "202A-2024",
            "Invalid season format: 202A-2024. Expected format: 'YYYY' or 'YYYY-YYYY'",
        ),
        (
            "football",
            "england-premier-league",
            "2023/2024",
            "Invalid season format: 2023/2024. Expected format: 'YYYY' or 'YYYY-YYYY'",
        ),
        # Special cases that are invalid according to implementation
        (
            "football",
            "england-premier-league",
            "current",
            "Invalid season format: current. Expected format: 'YYYY' or 'YYYY-YYYY'",
        ),
        (
            "football",
            "england-premier-league",
            " 2023-2024 ",
            "Invalid season format:  2023-2024 . Expected format: 'YYYY' or 'YYYY-YYYY'",
        ),
        (
            "football",
            "england-premier-league",
            "Season_2023-2024",
            "Invalid season format: Season_2023-2024. Expected format: 'YYYY' or 'YYYY-YYYY'",
        ),
    ],
)
def test_get_historic_matches_url_invalid_season_format(sport, league, season, error_msg):
    """Test invalid season formats."""
    with pytest.raises(ValueError, match=error_msg):
        URLBuilder.get_historic_matches_url(sport, league, season)


@pytest.mark.parametrize(
    ("sport", "league", "season", "error_msg"),
    [
        # According to the implementation, end year must be exactly start_year + 1
        (
            "football",
            "england-premier-league",
            "2023-2025",
            "Invalid season range: 2023-2025. The second year must be exactly one year after the first.",
        ),
        (
            "football",
            "england-premier-league",
            "2024-2023",
            "Invalid season range: 2024-2023. The second year must be exactly one year after the first.",
        ),
    ],
)
def test_get_historic_matches_url_invalid_season_range(sport, league, season, error_msg):
    """Test invalid season ranges."""
    with pytest.raises(ValueError, match=error_msg):
        URLBuilder.get_historic_matches_url(sport, league, season)


def test_get_historic_matches_url_invalid_sport():
    """Test error handling for invalid sports."""
    with pytest.raises(ValueError, match="'handball' is not a valid Sport"):
        URLBuilder.get_historic_matches_url("handball", "champions-league", "2023-2024")


def test_get_historic_matches_url_invalid_league():
    """Test error handling for invalid leagues."""
    with pytest.raises(
        ValueError,
        match="Invalid league 'random-league' for sport 'football'. Available: england-premier-league, la-liga",
    ):
        URLBuilder.get_historic_matches_url("football", "random-league", "2023-2024")


@pytest.mark.parametrize(
    ("sport", "date", "league", "expected_url"),
    [
        # With league
        ("football", "2025-02-10", "england-premier-league", f"{ODDSPORTAL_BASE_URL}/football/england/premier-league"),
        # Without league
        ("football", "2025-02-10", None, f"{ODDSPORTAL_BASE_URL}/matches/football/2025-02-10/"),
        # Different date format (assuming implemented format handling)
        ("tennis", "2025-02-10", "atp-tour", f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour"),
        # Empty or None date should use today's date (not testing exact value to avoid test instability)
        ("football", None, None, None),  # Special case handled in test function
        ("football", "", None, None),  # Special case handled in test function
    ],
)
def test_get_upcoming_matches_url(sport, date, league, expected_url):
    """Test building URLs for upcoming matches with various inputs."""
    if date is None or date == "":
        # Don't test the exact URL since it depends on today's date
        result = URLBuilder.get_upcoming_matches_url(sport, date, league)
        assert result.startswith(f"{ODDSPORTAL_BASE_URL}/matches/")
    else:
        assert URLBuilder.get_upcoming_matches_url(sport, date, league) == expected_url


@pytest.mark.parametrize(
    ("sport", "league", "expected_url"),
    [
        ("football", "england-premier-league", f"{ODDSPORTAL_BASE_URL}/football/england/premier-league"),
        ("tennis", "atp-tour", f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour"),
        ("baseball", "mlb", f"{ODDSPORTAL_BASE_URL}/baseball/usa/mlb"),
    ],
)
def test_get_league_url(sport, league, expected_url):
    """Test retrieving league URLs."""
    assert URLBuilder.get_league_url(sport, league) == expected_url


def test_get_league_url_invalid_sport():
    """Test get_league_url raises ValueError for unsupported sport."""
    with pytest.raises(ValueError, match="'handball' is not a valid Sport"):
        URLBuilder.get_league_url("handball", "champions-league")


def test_get_league_url_invalid_league():
    """Test get_league_url raises ValueError for unsupported league."""
    with pytest.raises(
        ValueError,
        match="Invalid league 'random-league' for sport 'football'. Available: england-premier-league, la-liga",
    ):
        URLBuilder.get_league_url("football", "random-league")
