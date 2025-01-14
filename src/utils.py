from datetime import datetime

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

def get_current_date_time_string():
    now = datetime.now()
    date_time_string = now.strftime('%Y-%m-%d %H:%M:%S')
    return date_time_string