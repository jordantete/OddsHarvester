"""
Configuration for OddsPortal layout tests.

This file contains all test cases and configurations needed
to verify the integrity of OddsPortal layout.
"""

# Parameterized test configuration
TEST_CASES = [
    {
        "sport": "football",
        "url": "https://www.oddsportal.com/football/england/premier-league/leicester-brentford-xQ77QTN0",
        "markets": ["1X2", "Draw No Bet", "Over/Under 2.5"],
        "expected_teams": ("Leicester", "Brentford"),
        "expected_league": "Premier League 2024/2025",
        "expected_venue": "King Power Stadium",
        "expected_score": ("0", "4"),
        "description": "Football Premier League match with multiple markets",
        "timeout": 10000,
    },
    {
        "sport": "football-2",
        "url": "https://www.oddsportal.com/football/england/premier-league/leicester-brentford-xQ77QTN0",
        "markets": ["1X2", "Both Teams to Score", "Double Chance"],
        "expected_teams": ("Leicester", "Brentford"),
        "expected_league": "Premier League 2024/2025",
        "expected_venue": "King Power Stadium",
        "expected_score": ("0", "4"),
        "description": "Football Premier League match with different markets",
        "timeout": 10000,
    },
    {
        "sport": "football-3",
        "url": "https://www.oddsportal.com/football/england/premier-league/leicester-brentford-xQ77QTN0",
        "markets": ["1X2", "European Handicap", "Half Time / Full Time"],
        "expected_teams": ("Leicester", "Brentford"),
        "expected_league": "Premier League 2024/2025",
        "expected_venue": "King Power Stadium",
        "expected_score": ("0", "4"),
        "description": "Football Premier League match with advanced markets",
        "timeout": 10000,
    },
]

# CSS selectors for interface elements
SELECTORS = {
    "market_tabs": "ul.visible-links.bg-black-main.odds-tabs > li",
    "odds_container": ".odds-container",
    "odds_button": ".odds-text",  # Changed from .odds-button to .odds-text
    "react_event_header": "div#react-event-header",
    "market_content": ".market-content",
    "loading_spinner": ".loading-spinner",
    "odds_value": ".odds-value",
    "bookmaker_name": ".bookmaker-name",
    "market_title": ".market-title",
}

# Mapping of market names to their specific selectors
MARKET_SELECTORS = {
    "1X2": {"tab_text": ["1", "X", "2"], "odds_selector": ".odds-text", "expected_options": 3},
    "Draw No Bet": {"tab_text": ["Home", "Away"], "odds_selector": ".odds-text", "expected_options": 2},
    "Over/Under": {"tab_text": ["Over", "Under"], "odds_selector": ".odds-text", "expected_options": 2},
    "Match Winner": {"tab_text": ["Home", "Away"], "odds_selector": ".odds-text", "expected_options": 2},
    "Asian Handicap": {"tab_text": ["Home", "Away"], "odds_selector": ".odds-text", "expected_options": 2},
    "BTTS": {"tab_text": ["Yes", "No"], "odds_selector": ".odds-text", "expected_options": 2},
    "Handicap": {"tab_text": ["Home", "Away"], "odds_selector": ".odds-text", "expected_options": 2},
}

# Default timeout configuration
DEFAULT_TIMEOUTS = {"navigation": 10000, "market_tabs": 5000, "odds_loading": 3000, "page_load": 10000}

# Validation thresholds configuration
VALIDATION_THRESHOLDS = {
    "min_success_rate": 0.3,  # 30% of markets must pass (more realistic)
    "min_odds_count": 1,  # At least 1 odds per market
    "min_tabs_count": 1,  # At least 1 market tab
}

# Custom error messages
ERROR_MESSAGES = {
    "navigation_failed": "Failed to navigate to match page",
    "no_market_tabs": "No market tabs found",
    "no_odds_found": "No odds found for market",
    "invalid_event_data": "Invalid event data",
    "team_mismatch": "Expected teams do not match",
    "league_mismatch": "Expected league does not match",
    "score_mismatch": "Expected score does not match",
    "venue_mismatch": "Expected venue does not match",
}

# Log configuration
LOG_CONFIG = {"enable_detailed_logs": True, "log_level": "INFO", "include_timestamps": True, "max_log_length": 1000}

# Sport-specific test configuration
SPORT_SPECIFIC_CONFIG = {
    "football": {
        "expected_markets": ["1X2", "Draw No Bet", "Over/Under"],
        "min_markets": 2,
        "special_validation": ["venue", "score"],
    },
    "tennis": {
        "expected_markets": ["Match Winner", "Over/Under", "Asian Handicap"],
        "min_markets": 2,
        "special_validation": ["score"],
    },
    "basketball": {
        "expected_markets": ["1X2", "Over/Under", "Asian Handicap"],
        "min_markets": 2,
        "special_validation": ["score"],
    },
    "rugby-union": {
        "expected_markets": ["1X2", "Over/Under", "Handicap"],
        "min_markets": 2,
        "special_validation": ["score"],
    },
    "ice-hockey": {
        "expected_markets": ["1X2", "Over/Under", "BTTS"],
        "min_markets": 2,
        "special_validation": ["score"],
    },
}


def get_test_case_by_sport(sport: str) -> dict | None:
    """Gets a test case by sport."""
    for case in TEST_CASES:
        if case["sport"] == sport:
            return case
    return None


def get_sport_config(sport: str) -> dict:
    """Gets sport-specific configuration."""
    return SPORT_SPECIFIC_CONFIG.get(sport, {})


def validate_test_case(test_case: dict) -> list[str]:
    """Validates a test case and returns errors."""
    errors = []

    required_fields = ["url", "markets", "expected_teams", "sport"]
    for field in required_fields:
        if field not in test_case:
            errors.append(f"Required field missing: {field}")

    if "expected_teams" in test_case and len(test_case["expected_teams"]) != 2:
        errors.append("expected_teams must contain exactly 2 teams")

    if "markets" in test_case and len(test_case["markets"]) == 0:
        errors.append("At least one market must be defined")

    return errors


def get_all_sports() -> list[str]:
    """Returns the list of all supported sports."""
    return list({case["sport"] for case in TEST_CASES})
