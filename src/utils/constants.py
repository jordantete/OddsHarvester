ODDSPORTAL_BASE_URL = "https://www.oddsportal.com"
ODDS_FORMAT = "Decimal Odds"
DATE_FORMAT_REGEX = r"^\d{4}\d{2}\d{2}$"  # YYYYMMDD

SUPPORTED_SPORTS = [
    "football"
]

SUPPORTED_MARKETS = [
    "1x2",           # Full-time 1X2 odds
    "over_under_1_5", # Over/Under 1.5 goals
    "over_under_2_5", # Over/Under 2.5 goals
    "over_under_3_5", # Over/Under 3.5 goals
    "over_under_4_5", # Over/Under 4.5 goals
    "btts",           # Both Teams to Score
    "double_chance"   # Double chance odds
]

FOOTBALL_LEAGUES_URLS_MAPPING = {
    "france-ligue-1": 'https://www.oddsportal.com/football/france/ligue-1',
    "france-ligue-2": "https://www.oddsportal.com/football/france/ligue-2/",
    "germany-bundesliga": 'https://www.oddsportal.com/football/germany/bundesliga',
    "germany-bundesliga-2": "https://www.oddsportal.com/football/germany/2-bundesliga/",
    "england-premier-league": 'https://www.oddsportal.com/football/england/premier-league',
    "england-championship": 'https://www.oddsportal.com/football/england/championship',
    "spain-laliga": 'https://www.oddsportal.com/football/spain/laliga',
    "spain-laliga2": "https://www.oddsportal.com/football/spain/laliga2/",
    "italy-serie-a": 'https://www.oddsportal.com/football/italy/serie-a',
    "italy-serie-b": "https://www.oddsportal.com/football/italy/serie-b/",
    "usa-mls": "https://www.oddsportal.com/football/usa/mls",
    "brazil-serie-a": "https://www.oddsportal.com/football/brazil/serie-a",
    "mexico-liga-mx": "https://www.oddsportal.com/football/mexico/liga-de-expansion-mx",
    "liga-portugal": "https://www.oddsportal.com/football/portugal/liga-portugal",
    "liga-portugal-2": "https://www.oddsportal.com/football/portugal/liga-portugal-2/",
    "eredivisie": "https://www.oddsportal.com/football/netherlands/eredivisie",
    "champions-league": "https://www.oddsportal.com/football/europe/champions-league",
    "europa-league": "https://www.oddsportal.com/football/europe/europa-league",
    "jupiler-pro-league": "https://www.oddsportal.com/football/belgium/jupiler-pro-league/",
    "denmark-superliga": "https://www.oddsportal.com/football/denmark/superliga/",
    "colombia-primera-a": "https://www.oddsportal.com/football/colombia/primera-a/",
    "austria-bundesliga": "https://www.oddsportal.com/football/austria/bundesliga/",
    "bulgaria-parva-liga": "https://www.oddsportal.com/football/bulgaria/parva-liga/",
    "australia-a-league": "https://www.oddsportal.com/football/australia/a-league/",
    "greece-super-league": "https://www.oddsportal.com/football/greece/super-league/",
    "norway-eliteserien": "https://www.oddsportal.com/football/norway/eliteserien/",
    "romania-superliga": "https://www.oddsportal.com/football/romania/superliga/",
    "saudi-professional-league": "https://www.oddsportal.com/football/saudi-arabia/saudi-professional-league/",
    "scotland-premiership": "https://www.oddsportal.com/football/scotland/premiership/",
    "switzerland-super-league": "https://www.oddsportal.com/football/switzerland/super-league/",
    "turkey-super-lig": "https://www.oddsportal.com/football/turkey/super-lig/",
    "world-championship-2026": "https://www.oddsportal.com/football/world/world-championship-2026/"
}

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
    "--disable-dev-shm-usage", "--ipc=host", "--single-process", "--window-size=1920,1080", "--no-sandbox",
    "--no-zygote", "--allow-running-insecure-content", "--autoplay-policy=user-gesture-required"
    "--disable-component-update", "--no-default-browser-check", "--disable-domain-reliability",
    "--disable-features=AudioServiceOutOfProcess,IsolateOrigins,site-per-process", "--disable-print-preview", 
    "--disable-setuid-sandbox", "--disable-site-isolation-trials", "--disable-speech-api",
    "--disable-web-security", "--disk-cache-size=33554432", "--enable-features=SharedArrayBuffer",
    "--hide-scrollbars", "--ignore-gpu-blocklist", "--in-process-gpu", "--mute-audio", "--no-pings", "--disable-gpu"
]