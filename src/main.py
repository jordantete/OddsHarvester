#!/usr/bin/env python3
import json, requests
from logger import LOGGER
from utils import get_current_date_time_string
from odds_portal_scrapper import OddsPortalScrapper
from comparateur_de_cotes_scraper import FrenchOddsScrapper
from local_data_storage import LocalDataStorage
from remote_data_storage import RemoteDataStorage
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import sync_playwright


def get_odds_portal_historic_odds(league_name: str, season: str):
    file_path = f"/data/{league_name}_{season}_{get_current_date_time_string()}.json"
    odds_portal_scrapper = OddsPortalScrapper()
    scrapped_historic_odds = odds_portal_scrapper.get_historic_odds(league=league_name, season=season)
    flattened_historic_odds = [item for sublist in scrapped_historic_odds for item in sublist]
    storage = LocalDataStorage(file_path)
    storage.append_data(flattened_historic_odds)
    LOGGER.info(f"Historic odds for {league_name} season {season} have been scrapped and stored.")

def get_odds_portal_next_matchs_odds(league_name: str):
    odds_portal_scrapper = OddsPortalScrapper()
    odds_portal_scrapper.get_next_matchs_odds(league=league_name)

def get_french_bookamker_odds(league_name: str):
    french_odds_scrapper = FrenchOddsScrapper(league=league_name)
    french_odds_scrapper.scrape_and_store_matches()

def get_all_upcoming_event_odds(sport: str, date: str):
    odds_portal_scrapper = OddsPortalScrapper()
    odds = odds_portal_scrapper.get_upcoming_matchs_odds(sport=sport, date=date)
    return odds

def scrape_concurently():
    ## TODO: testing purposes
    leagues_seasons = [('liga', '2021-2022')]
    with ThreadPoolExecutor(max_workers=6) as executor:
        executor.map(lambda x: get_odds_portal_historic_odds(*x), leagues_seasons)

def scan_and_store_odds_portal_data(event=0, context=0):
    LOGGER.info(f"scan_and_store_odds_portal_matches - event: {event} - context: {context}")
    today_date = datetime.now()
    tomorrow_date = today_date + timedelta(days=1)
    formatted_today_date = today_date.strftime('%Y%m%d')
    formatted_tomorrow_date = tomorrow_date.strftime('%Y%m%d')
    # tomorow_football_matches_data = get_all_upcoming_event_odds(sport="football", date=formatted_tomorrow_date)
    # LOGGER.info(f"tomorow_football_matches_data: {tomorow_football_matches_data}")
    # csv_writer = S3CSVWriter('your-bucket-name')
    # data = [
    #     {'name': 'Alice', 'age': 30},
    #     {'name': 'Bob', 'age': 25},
    #     {'name': 'Charlie', 'age': 35}
    # ]
    # csv_writer.write_csv_to_s3(data, 'path/to/yourfile.csv')

def test_playwright_python():
    print("WIll test playwright python")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--disable-gpu", "--single-process"])
        page = browser.new_page()
        page.goto("http://google.com")
        print(page.title())
        browser.close()

if __name__ == "__main__":
    test_playwright_python()