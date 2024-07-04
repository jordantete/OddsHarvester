import time, requests
from datetime import datetime
from logger import LOGGER

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

TENNIS_LEAGUES_ULRS_MAPPING = {
    "test": "test"
}

FRENCH_ODDS_SCRAPPER_LEAGUE_URLS_MAPPING = {
    "premier-league": 'http://www.comparateur-de-cotes.fr/comparateur/football/Angleterre-Premier-League-ed2',
    "ligue-1": 'http://www.comparateur-de-cotes.fr/comparateur/football/France-Ligue-1-ed3',
    "bundesliga": 'http://www.comparateur-de-cotes.fr/comparateur/football/Allemagne-Bundesliga-ed4',
    "championship": 'http://www.comparateur-de-cotes.fr/comparateur/football/Angleterre-Championship-ed13',
    "liga": 'http://www.comparateur-de-cotes.fr/comparateur/football/Espagne-LaLiga-ed6',
    "champions-league": 'http://www.comparateur-de-cotes.fr/comparateur/football/Ligue-des-Champions-ed7'
}

def get_current_date_time_string():
    now = datetime.now()
    date_time_string = now.strftime('%Y-%m-%d %H:%M:%S')
    return date_time_string

def measure_network_performance():
    try:
        start_time = time.time()
        response = requests.get("https://www.google.com", timeout=5)
        latency = time.time() - start_time
        
        if response.status_code != 200:
            raise Exception(f"Unexpected status code: {response.status_code}")

        LOGGER.info(f"Latency to www.google.com: {latency:.4f} seconds")
        start_time = time.time()
        response = requests.get("https://speed.hetzner.de/100MB.bin", stream=True, timeout=5)
        total_length = response.headers.get('content-length')

        if total_length is None:
            raise Exception("Could not get content length for throughput test")

        download_size = 0
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:
                download_size += len(chunk)

        throughput = download_size / (time.time() - start_time)
        LOGGER.info(f"Download throughput: {throughput / 1_000_000:.2f} MB/s")
        return {'latency': latency, 'throughput': throughput / 1_000_000}
    except Exception as e:
        LOGGER.error(f"An error occurred while measuring network performance: {e}")
        return None