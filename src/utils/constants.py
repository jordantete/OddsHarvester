ODDSPORTAL_BASE_URL = "https://www.oddsportal.com"
ODDS_FORMAT = "Decimal Odds"
DATE_FORMAT_REGEX = r"^\d{4}\d{2}\d{2}$"  # YYYYMMDD

SCRAPE_CONCURRENCY_TASKS = 2
BROWSER_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
BROWSER_LOCALE_TIMEZONE = "fr-BE"
BROWSER_TIMEZONE_ID = "Europe/Brussels"
DEFAULT_PROXY_CONFIG = {
    "server": "http://45.128.133.205:1080",
    "username": "",
    "password": ""
}

PLAYWRIGHT_BROWSER_ARGS = [
    "--disable-background-networking", "--disable-extensions", "--mute-audio",
    "--window-size=1280,720", "--disable-popup-blocking", "--disable-translate",
    "--no-first-run", "--disable-infobars", "--disable-features=IsolateOrigins,site-per-process",
    "--enable-gpu-rasterization", "--disable-blink-features=AutomationControlled"
]

PLAYWRIGHT_BROWSER_ARGS_DOCKER = [
    "--disable-dev-shm-usage", 
    "--no-sandbox", 
    "--headless",  # Ensure headless mode
    "--disable-gpu", 
    "--disable-background-networking", 
    "--disable-popup-blocking", 
    "--disable-extensions"
]