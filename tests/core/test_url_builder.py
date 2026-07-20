from datetime import UTC, datetime

import pytest

from oddsharvester.core.url_builder import URLBuilder, normalize_inplay_match_url, rebase_url
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL
from oddsharvester.utils.sport_league_constants import SPORTS_LEAGUES_URLS_MAPPING
from oddsharvester.utils.sport_market_constants import Sport

# Create test mapping for sports and leagues
SPORTS_LEAGUES_URLS_MAPPING[Sport.FOOTBALL] = {
    "england-premier-league": f"{ODDSPORTAL_BASE_URL}/football/england/premier-league",
    "la-liga": f"{ODDSPORTAL_BASE_URL}/football/spain/la-liga",
    "czech-republic-chance-liga": f"{ODDSPORTAL_BASE_URL}/football/czech-republic/chance-liga",
    "slovakia-nike-liga": f"{ODDSPORTAL_BASE_URL}/football/slovakia/nike-liga",
    "hungary-nb-i": f"{ODDSPORTAL_BASE_URL}/football/hungary/nb-i",
    "brazil-serie-a": f"{ODDSPORTAL_BASE_URL}/football/brazil/serie-a-betano",
    "south-africa-premiership": f"{ODDSPORTAL_BASE_URL}/football/south-africa/betway-premiership",
    "bulgaria-parva-liga": f"{ODDSPORTAL_BASE_URL}/football/bulgaria/efbet-league",
}
SPORTS_LEAGUES_URLS_MAPPING[Sport.TENNIS] = {
    "atp-tour": f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour",
}
SPORTS_LEAGUES_URLS_MAPPING[Sport.BASEBALL] = {
    "mlb": f"{ODDSPORTAL_BASE_URL}/baseball/usa/mlb",
    "japan-npb": f"{ODDSPORTAL_BASE_URL}/baseball/japan/npb",
}
SPORTS_LEAGUES_URLS_MAPPING[Sport.AMERICAN_FOOTBALL] = {
    "nfl": f"{ODDSPORTAL_BASE_URL}/american-football/usa/nfl",
    "ncaa": f"{ODDSPORTAL_BASE_URL}/american-football/usa/ncaa",
}
SPORTS_LEAGUES_URLS_MAPPING[Sport.HANDBALL] = {
    "ehf-champions-league": f"{ODDSPORTAL_BASE_URL}/handball/europe/champions-league",
}
SPORTS_LEAGUES_URLS_MAPPING[Sport.VOLLEYBALL] = {
    "italy-superlega": f"{ODDSPORTAL_BASE_URL}/volleyball/italy/superlega",
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
        # American Football cases
        (
            "american-football",
            "nfl",
            "2024-2025",
            f"{ODDSPORTAL_BASE_URL}/american-football/usa/nfl-2024-2025/results/",
        ),
        (
            "american-football",
            "ncaa",
            "2023-2024",
            f"{ODDSPORTAL_BASE_URL}/american-football/usa/ncaa-2023-2024/results/",
        ),
    ],
)
def test_get_historic_matches_url(sport, league, season, expected_url):
    """Test building URLs for historical matches with various inputs."""
    assert URLBuilder.get_historic_matches_url(sport, league, season) == expected_url


@pytest.mark.parametrize(
    ("sport", "league", "expected_url"),
    [
        ("football", "england-premier-league", f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/results/"),
        ("tennis", "atp-tour", f"{ODDSPORTAL_BASE_URL}/tennis/atp-tour/results/"),
        ("basketball", "nba", "https://www.oddsportal.com/basketball/usa/nba/results/"),
        ("baseball", "mlb", f"{ODDSPORTAL_BASE_URL}/baseball/usa/mlb/results/"),
        ("american-football", "nfl", f"{ODDSPORTAL_BASE_URL}/american-football/usa/nfl/results/"),
        ("ice-hockey", "nhl", "https://www.oddsportal.com/hockey/usa/nhl/results/"),
        (
            "rugby-league",
            "england-super-league",
            "https://www.oddsportal.com/rugby-league/england/super-league/results/",
        ),
        ("rugby-union", "six-nations", "https://www.oddsportal.com/rugby-union/europe/six-nations/results/"),
    ],
)
def test_get_historic_matches_url_with_current_season(sport, league, expected_url):
    """'current' must resolve to the base /results/ URL for every supported sport (issue #59)."""
    assert URLBuilder.get_historic_matches_url(sport, league, "current") == expected_url


@pytest.mark.parametrize("season_value", ["current", "CURRENT", "Current", "cUrReNt"])
def test_get_historic_matches_url_current_is_case_insensitive(season_value):
    """'current' must be matched case-insensitively (issue #59)."""
    expected = f"{ODDSPORTAL_BASE_URL}/football/england/premier-league/results/"
    assert URLBuilder.get_historic_matches_url("football", "england-premier-league", season_value) == expected


def test_get_historic_matches_url_explicit_current_year_range_is_suffixed():
    """Regression (season rollover, issue #71): an explicit YYYY-YYYY range whose end
    year equals the current calendar year must resolve to the suffixed URL, not the base
    URL. Trusting the calendar year sent finished-season requests to the base URL, which
    OddsPortal rolls over to the next season → wrong season scraped. Only 'current'/None
    may use the base URL."""
    end_year = datetime.now(UTC).year
    season = f"{end_year - 1}-{end_year}"
    url = URLBuilder.get_historic_matches_url("football", "england-premier-league", season)
    assert url == f"{ODDSPORTAL_BASE_URL}/football/england/premier-league-{season}/results/"


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
    with pytest.raises(ValueError, match="'curling' is not a valid Sport"):
        URLBuilder.get_historic_matches_url("curling", "champions-league", "2023-2024")


def test_get_historic_matches_url_invalid_league():
    """Test error handling for invalid leagues."""
    with pytest.raises(
        ValueError,
        match=r"Invalid league 'random-league' for sport 'football'\. Available: england-premier-league, la-liga",
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
        ("american-football", "nfl", f"{ODDSPORTAL_BASE_URL}/american-football/usa/nfl"),
        ("handball", "ehf-champions-league", f"{ODDSPORTAL_BASE_URL}/handball/europe/champions-league"),
        ("volleyball", "italy-superlega", f"{ODDSPORTAL_BASE_URL}/volleyball/italy/superlega"),
    ],
)
def test_get_league_url(sport, league, expected_url):
    """Test retrieving league URLs."""
    assert URLBuilder.get_league_url(sport, league) == expected_url


def test_get_league_url_cricket():
    """Cricket league URL resolves from the seeded mapping."""
    assert (
        URLBuilder.get_league_url("cricket", "big-bash-league")
        == "https://www.oddsportal.com/cricket/australia/big-bash-league/"
    )


@pytest.mark.parametrize(
    ("sport", "league", "season", "expected_url"),
    [
        # Czech Republic: fortuna-liga for old seasons, chance-liga for new
        (
            "football",
            "czech-republic-chance-liga",
            "2023-2024",
            f"{ODDSPORTAL_BASE_URL}/football/czech-republic/fortuna-liga-2023-2024/results/",
        ),
        (
            "football",
            "czech-republic-chance-liga",
            "2024-2025",
            f"{ODDSPORTAL_BASE_URL}/football/czech-republic/chance-liga-2024-2025/results/",
        ),
        # Slovakia: fortuna-liga for old seasons, nike-liga for new
        (
            "football",
            "slovakia-nike-liga",
            "2022-2023",
            f"{ODDSPORTAL_BASE_URL}/football/slovakia/fortuna-liga-2022-2023/results/",
        ),
        (
            "football",
            "slovakia-nike-liga",
            "2024-2025",
            f"{ODDSPORTAL_BASE_URL}/football/slovakia/nike-liga-2024-2025/results/",
        ),
        # Hungary: otp-bank-liga for old seasons, nb-i for new
        (
            "football",
            "hungary-nb-i",
            "2023-2024",
            f"{ODDSPORTAL_BASE_URL}/football/hungary/otp-bank-liga-2023-2024/results/",
        ),
        (
            "football",
            "hungary-nb-i",
            "2024-2025",
            f"{ODDSPORTAL_BASE_URL}/football/hungary/nb-i-2024-2025/results/",
        ),
        # Brazil: serie-a for old seasons, serie-a-betano for new (single year format)
        (
            "football",
            "brazil-serie-a",
            "2023",
            f"{ODDSPORTAL_BASE_URL}/football/brazil/serie-a-2023/results/",
        ),
        (
            "football",
            "brazil-serie-a",
            "2024",
            f"{ODDSPORTAL_BASE_URL}/football/brazil/serie-a-betano-2024/results/",
        ),
        (
            "football",
            "brazil-serie-a",
            "2025",
            f"{ODDSPORTAL_BASE_URL}/football/brazil/serie-a-betano-2025/results/",
        ),
        # South Africa: premier-league for old seasons, betway-premiership for new
        (
            "football",
            "south-africa-premiership",
            "2023-2024",
            f"{ODDSPORTAL_BASE_URL}/football/south-africa/premier-league-2023-2024/results/",
        ),
        (
            "football",
            "south-africa-premiership",
            "2024-2025",
            f"{ODDSPORTAL_BASE_URL}/football/south-africa/betway-premiership-2024-2025/results/",
        ),
        # Bulgaria: parva-liga for old seasons, efbet-league for new
        (
            "football",
            "bulgaria-parva-liga",
            "2024-2025",
            f"{ODDSPORTAL_BASE_URL}/football/bulgaria/parva-liga-2024-2025/results/",
        ),
        # Explicit range → always suffixed (new efbet-league slug for recent seasons)
        (
            "football",
            "bulgaria-parva-liga",
            "2025-2026",
            f"{ODDSPORTAL_BASE_URL}/football/bulgaria/efbet-league-2025-2026/results/",
        ),
        # No alias - current season uses canonical URL
        (
            "football",
            "czech-republic-chance-liga",
            None,
            f"{ODDSPORTAL_BASE_URL}/football/czech-republic/chance-liga/results/",
        ),
        # No alias - league without aliases is unaffected
        (
            "football",
            "england-premier-league",
            "2023-2024",
            f"{ODDSPORTAL_BASE_URL}/football/england/premier-league-2023-2024/results/",
        ),
        # Single year format with alias
        (
            "football",
            "czech-republic-chance-liga",
            "2023",
            f"{ODDSPORTAL_BASE_URL}/football/czech-republic/fortuna-liga-2023/results/",
        ),
        (
            "football",
            "czech-republic-chance-liga",
            "2024",
            f"{ODDSPORTAL_BASE_URL}/football/czech-republic/chance-liga-2024/results/",
        ),
    ],
)
def test_get_historic_matches_url_with_league_aliases(sport, league, season, expected_url):
    """Test that historic URLs correctly resolve league aliases for sponsor name changes."""
    assert URLBuilder.get_historic_matches_url(sport, league, season) == expected_url


def test_get_league_url_invalid_sport():
    """Test get_league_url raises ValueError for unsupported sport."""
    with pytest.raises(ValueError, match="'curling' is not a valid Sport"):
        URLBuilder.get_league_url("curling", "champions-league")


def test_get_league_url_invalid_league():
    """Test get_league_url raises ValueError for unsupported league."""
    with pytest.raises(
        ValueError,
        match=r"Invalid league 'random-league' for sport 'football'\. Available: england-premier-league, la-liga",
    ):
        URLBuilder.get_league_url("football", "random-league")


class TestRebaseUrl:
    def test_none_base_url_returns_unchanged(self):
        url = "https://www.oddsportal.com/football/england/premier-league/results/"
        assert rebase_url(url, None) == url

    def test_empty_base_url_returns_unchanged(self):
        url = "https://www.oddsportal.com/football/england/premier-league/results/"
        assert rebase_url(url, "") == url

    def test_swaps_scheme_and_host_preserving_path_query_fragment(self):
        url = "https://www.oddsportal.com/football/italy/serie-a/results/?foo=1#bar"
        assert rebase_url(url, "https://www.centroquote.it") == (
            "https://www.centroquote.it/football/italy/serie-a/results/?foo=1#bar"
        )

    def test_preserves_http_scheme_from_base_url(self):
        url = "https://www.oddsportal.com/tennis/atp-tour/"
        assert rebase_url(url, "http://mirror.example.com") == "http://mirror.example.com/tennis/atp-tour/"

    def test_trailing_slash_on_base_url_does_not_double(self):
        url = "https://www.oddsportal.com/football/spain/laliga"
        assert rebase_url(url, "https://www.centroquote.it/") == "https://www.centroquote.it/football/spain/laliga"

    def test_idempotent(self):
        url = "https://www.oddsportal.com/football/france/ligue-1/results/"
        once = rebase_url(url, "https://www.centroquote.it")
        assert rebase_url(once, "https://www.centroquote.it") == once


class TestUrlBuilderBaseUrl:
    BASE = "https://www.centroquote.it"

    def test_get_league_url_default_unchanged(self):
        url = URLBuilder.get_league_url("football", "england-premier-league")
        assert url.startswith("https://www.oddsportal.com/")

    def test_get_league_url_rebased(self):
        url = URLBuilder.get_league_url("football", "england-premier-league", base_url=self.BASE)
        assert url == f"{self.BASE}/football/england/premier-league"

    def test_get_historic_matches_url_rebased_with_season(self):
        url = URLBuilder.get_historic_matches_url(
            sport="football", league="england-premier-league", season="2021-2022", base_url=self.BASE
        )
        assert url == f"{self.BASE}/football/england/premier-league-2021-2022/results/"

    def test_get_historic_matches_url_rebased_current_season(self):
        url = URLBuilder.get_historic_matches_url(
            sport="football", league="england-premier-league", season="current", base_url=self.BASE
        )
        assert url == f"{self.BASE}/football/england/premier-league/results/"

    def test_get_historic_matches_url_baseball_special_case_rebased(self):
        url = URLBuilder.get_historic_matches_url(
            sport="baseball", league="mlb", season="2022-2023", base_url=self.BASE
        )
        assert url == f"{self.BASE}/baseball/usa/mlb-2022/results/"

    def test_get_upcoming_matches_url_no_league_rebased(self):
        url = URLBuilder.get_upcoming_matches_url(sport="football", date="2025-01-15", base_url=self.BASE)
        assert url == f"{self.BASE}/matches/football/2025-01-15/"

    def test_get_upcoming_matches_url_with_league_rebased(self):
        url = URLBuilder.get_upcoming_matches_url(
            sport="football", date="2025-01-15", league="england-premier-league", base_url=self.BASE
        )
        assert url == f"{self.BASE}/football/england/premier-league"

    def test_default_calls_have_no_regression(self):
        assert URLBuilder.get_upcoming_matches_url(sport="football", date="2025-01-15").startswith(
            "https://www.oddsportal.com/"
        )


class TestLiveUrls:
    def test_get_live_matches_url(self):
        url = URLBuilder.get_live_matches_url(sport="football")
        assert url == "https://www.oddsportal.com/inplay-odds/live-now/football/"

    def test_get_live_matches_url_rebases_on_base_url(self):
        url = URLBuilder.get_live_matches_url(sport="football", base_url="https://www.centroquote.it")
        assert url == "https://www.centroquote.it/inplay-odds/live-now/football/"

    def test_get_live_matches_url_rejects_unknown_sport(self):
        with pytest.raises(ValueError):
            URLBuilder.get_live_matches_url(sport="chess")

    def test_normalize_inplay_match_url_appends_segment(self):
        url = "https://www.oddsportal.com/football/spain/laliga/real-madrid-barcelona-abc123/"
        assert (
            normalize_inplay_match_url(url)
            == "https://www.oddsportal.com/football/spain/laliga/real-madrid-barcelona-abc123/inplay-odds/"
        )

    def test_normalize_inplay_match_url_preserves_fragment(self):
        url = "https://www.oddsportal.com/tennis/h2h/a-x1/b-y2/#t0bmQMVh"
        assert (
            normalize_inplay_match_url(url) == "https://www.oddsportal.com/tennis/h2h/a-x1/b-y2/inplay-odds/#t0bmQMVh"
        )

    def test_normalize_inplay_match_url_idempotent(self):
        url = "https://www.oddsportal.com/tennis/h2h/a-x1/b-y2/inplay-odds/#t0bmQMVh"
        assert normalize_inplay_match_url(url) == url
