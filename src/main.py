import os, asyncio, uuid, pytz
from logger import LOGGER
from utils import get_current_date_time_string, measure_network_performance
from odds_portal_scrapper import OddsPortalScrapper
from comparateur_de_cotes_scraper import FrenchOddsScrapper
from local_data_storage import LocalDataStorage
from remote_data_storage import RemoteDataStorage
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

is_lambda = os.environ.get("AWS_EXECUTION_ENV") is not None

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

async def get_all_upcoming_event_odds(sport: str, date: str):
    odds_portal_scrapper = OddsPortalScrapper(headless_mode=is_lambda)
    await odds_portal_scrapper.initialize_webdriver()
    odds = await odds_portal_scrapper.get_upcoming_matchs_odds(sport=sport, date=date)
    return odds

def scrape_concurently():
    ## TODO: testing purposes
    leagues_seasons = [('liga', '2021-2022')]
    with ThreadPoolExecutor(max_workers=6) as executor:
        executor.map(lambda x: get_odds_portal_historic_odds(*x), leagues_seasons)

async def scan_and_store_odds_portal_data_async(event=0, context=0):
    LOGGER.info(f"scan_and_store_odds_portal_matches - event: {event} - context: {context}")

    paris_tz = pytz.timezone('Europe/Paris')
    today_date = datetime.now(paris_tz)
    next_days_date = today_date + timedelta(days=2)
    formatted_next_days_date = next_days_date.strftime('%Y%m%d')

    next_days_football_matches_data = await get_all_upcoming_event_odds(sport="football", date=formatted_next_days_date)
    LOGGER.info(f"tomorrow_football_matches_data: {next_days_football_matches_data}")

    if next_days_football_matches_data:
        random_string_id = uuid.uuid4().hex
        csv_filename = f'/tmp/odds_data_{formatted_next_days_date}_{random_string_id}.csv'
        data_storage = RemoteDataStorage()
        executor = ThreadPoolExecutor()
        await asyncio.get_event_loop().run_in_executor(
            executor, 
            data_storage.process_and_upload, 
            next_days_football_matches_data, 
            today_date.strftime("%m/%d/%Y, %H:%M:%S"), 
            csv_filename
        )
        return {'statusCode': 200, "body": "File uploaded successfully"}
    else:
        LOGGER.warn("No data to upload.")
        return {'statusCode': 400, "body": "No data to upload"}

def scan_and_store_odds_portal_data(event=0, context=0):
    network_results = measure_network_performance()
    if network_results:
        LOGGER.info(f"Network performance: {network_results}")

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(scan_and_store_odds_portal_data_async(event, context))

if not is_lambda:
    scan_and_store_odds_portal_data()
