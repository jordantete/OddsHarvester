import json, requests
from logger import LOGGER
from datetime import datetime
from utils import get_current_date_time_string
from concurrent.futures import ThreadPoolExecutor
from odds_portal_scrapper import OddsPortalScrapper
from comparateur_de_cotes_scraper import FrenchOddsScrapper
from data_storage import DataStorage

def lambda_handler(event, context):
    LOGGER.info(f"Lambda handler called: {event} and context: {context}")

def get_odds_portal_historic_odds(league_name: str, season: str):
    file_path = f"/data/{league_name}_{season}_{get_current_date_time_string()}.json"
    odds_portal_scrapper = OddsPortalScrapper(league=league_name)
    scrapped_historic_odds = odds_portal_scrapper.get_historic_odds(season=season)
    flattened_historic_odds = [item for sublist in scrapped_historic_odds for item in sublist]
    storage = DataStorage(file_path)
    storage.append_data(flattened_historic_odds)
    LOGGER.info(f"Historic odds for {league_name} season {season} have been scrapped and stored.")

def get_odds_portal_next_matchs_odds(league_name: str):
    odds_portal_scrapper = OddsPortalScrapper(league=league_name)
    odds_portal_scrapper.get_next_matchs_odds()

def get_french_bookamker_odds(league_name: str):
    french_odds_scrapper = FrenchOddsScrapper(league=league_name)
    french_odds_scrapper.scrape_and_store_matches()

if __name__ == "__main__":
    get_odds_portal_next_matchs_odds(league_name="ligue-1")
    get_french_bookamker_odds(league_name="ligue-1")

    # leagues_seasons = [('liga', '2021-2022')]
    # with ThreadPoolExecutor(max_workers=6) as executor:
    #     executor.map(lambda x: get_odds_portal_historic_odds(*x), leagues_seasons)