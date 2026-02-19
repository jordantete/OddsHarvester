ODDSPORTAL_BASE_URL = "https://www.oddsportal.com"

# =============================================================================
# TIMEOUT CONSTANTS (milliseconds unless noted)
# =============================================================================

# Navigation & page load timeouts (ms)
NAVIGATION_TIMEOUT_MS = 15000
GOTO_TIMEOUT_MS = 10000
GOTO_TIMEOUT_LONG_MS = 20000
SELECTOR_TIMEOUT_MS = 10000
COOKIE_BANNER_TIMEOUT_MS = 10000
MARKET_TAB_TIMEOUT_MS = 10000
BOOKIES_FILTER_TIMEOUT_MS = 5000
PERIOD_SELECTOR_TIMEOUT_MS = 5000
ODDS_FORMAT_SELECTOR_TIMEOUT_MS = 8000

# Market extraction timeouts (ms)
DEFAULT_MARKET_TIMEOUT_MS = 5000
SCROLL_PAUSE_TIME_MS = 2000
MARKET_SWITCH_WAIT_TIME_MS = 3000

# Dynamic content wait (ms)
DYNAMIC_CONTENT_WAIT_MS = 2000
ODDS_FORMAT_WAIT_MS = 10000
DROPDOWN_WAIT_MS = 1000
TAB_SWITCH_WAIT_MS = 500
FALLBACK_VERIFY_WAIT_MS = 1000

# Odds history extraction timeouts (ms)
ODDS_HISTORY_PRE_WAIT_MS = 2000
ODDS_HISTORY_HOVER_WAIT_MS = 2000
ODDS_MOVEMENT_SELECTOR_TIMEOUT_MS = 3000

# Scrolling defaults (seconds)
SCROLL_TIMEOUT_S = 30
SCROLL_PAUSE_S = 3
MAX_SCROLL_ATTEMPTS = 5
SCROLL_UNTIL_CLICK_TIMEOUT_S = 20
SCROLL_UNTIL_CLICK_PAUSE_S = 3

# Page collection delays (ms)
PAGE_COLLECTION_DELAY_MIN_MS = 6000
PAGE_COLLECTION_DELAY_MAX_MS = 8000

# =============================================================================
# PAGINATION CONSTANTS
# =============================================================================

MAX_PAGINATION_PAGES = 50

# =============================================================================
# RETRY CONSTANTS
# =============================================================================

# Operation-level retries (for scrape_historic, scrape_upcoming, scrape_matches)
OPERATION_RETRY_MAX_ATTEMPTS = 3
OPERATION_RETRY_BASE_DELAY = 20.0
OPERATION_RETRY_MAX_DELAY = 60.0

# Match-level retries (for individual match scraping within extract_match_odds)
MATCH_RETRY_MAX_ATTEMPTS = 2
MATCH_RETRY_BASE_DELAY = 2.0
MATCH_RETRY_MAX_DELAY = 30.0

# =============================================================================
# RATE LIMITING CONSTANTS
# =============================================================================

DEFAULT_REQUEST_DELAY_S = 1.0
REQUEST_DELAY_JITTER_FACTOR = 0.5

PLAYWRIGHT_BROWSER_ARGS = [
    "--disable-background-networking",
    "--disable-extensions",
    "--mute-audio",
    "--window-size=1280,720",
    "--disable-popup-blocking",
    "--disable-translate",
    "--no-first-run",
    "--disable-infobars",
    "--disable-features=IsolateOrigins,site-per-process",
    "--enable-gpu-rasterization",
    "--disable-blink-features=AutomationControlled",
]

PLAYWRIGHT_BROWSER_ARGS_DOCKER = [
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--headless",
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-popup-blocking",
    "--disable-extensions",
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--mute-audio",
    "--window-size=1280,720",
]
