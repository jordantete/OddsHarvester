FOOTBALL_LEAGUES_URLS_MAPPING = {
    "premier-league": 'https://www.oddsportal.com/football/england/premier-league',
    "ligue-1": 'https://www.oddsportal.com/football/france/ligue-1',
    "bundesliga": 'https://www.oddsportal.com/football/germany/bundesliga',
    "championship": 'https://www.oddsportal.com/football/england/championship',
    "liga": 'https://www.oddsportal.com/football/spain/laliga',
    "serie-a": 'https://www.oddsportal.com/football/italy/serie-a',
    "mls": "https://www.oddsportal.com/football/usa/mls",
    "brazil-serie-a": "https://www.oddsportal.com/football/brazil/serie-a",
    "liga-mx": "https://www.oddsportal.com/football/mexico/liga-de-expansion-mx",
    "liga-portugal": "https://www.oddsportal.com/football/portugal/liga-portugal",
    "eredivisie": "https://www.oddsportal.com/football/netherlands/eredivisie",
    "champions-league": "https://www.oddsportal.com/football/europe/champions-league"
}

PLAYWRIGHT_BROWSER_ARGS = [
    "--disable-dev-shm-usage", "--ipc=host", "--single-process", "--window-size=1920,1080", "--no-sandbox",
    "--no-zygote", "--allow-running-insecure-content", "--autoplay-policy=user-gesture-required"
    "--disable-component-update", "--no-default-browser-check", "--disable-domain-reliability",
    "--disable-features=AudioServiceOutOfProcess,IsolateOrigins,site-per-process", "--disable-print-preview", 
    "--disable-setuid-sandbox", "--disable-site-isolation-trials", "--disable-speech-api",
    "--disable-web-security", "--disk-cache-size=33554432", "--enable-features=SharedArrayBuffer",
    "--hide-scrollbars", "--ignore-gpu-blocklist", "--in-process-gpu", "--mute-audio", "--no-pings", "--disable-gpu"
]