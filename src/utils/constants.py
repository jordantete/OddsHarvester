ODDSPORTAL_BASE_URL = "https://www.oddsportal.com"
ODDS_FORMAT = "Decimal Odds"

SCRAPE_CONCURRENCY_TASKS = 3

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
    "--headless",  # Ensure headless mode
    "--disable-gpu",
    "--disable-background-networking",
    "--disable-popup-blocking",
    "--disable-extensions",
]
