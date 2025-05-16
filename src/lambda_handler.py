import asyncio, pytz
from typing import Any, Dict
from datetime import datetime, timedelta
from src.core.scraper_app import run_scraper

def lambda_handler(event: Dict[str, Any], context: Any):
    """AWS Lambda handler for triggering the scraper."""
    paris_tz = pytz.timezone('Europe/Paris')
    next_day = datetime.now(paris_tz) + timedelta(days=1)
    formatted_date = next_day.strftime('%Y%m%d')
    
    ## TODO: Parse event to retrieve scraping taks' params - handle exceptions
    return asyncio.run(
        run_scraper(
            command="scrape_upcoming",
            sport="football",
            date=formatted_date,
            league="premier-league",
            storage_type="remote",
            headless=True,
            markets=["1x2"]
        )
    )