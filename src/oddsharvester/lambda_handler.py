import asyncio
from datetime import datetime, timedelta
from typing import Any

import pytz

from oddsharvester.core.scraper_app import run_scraper


def lambda_handler(event: dict[str, Any], context: Any):
    """AWS Lambda handler for triggering the scraper."""
    paris_tz = pytz.timezone("Europe/Paris")
    next_day = datetime.now(paris_tz) + timedelta(days=1)
    formatted_date = next_day.strftime("%Y%m%d")

    ## TODO: Parse event to retrieve scraping taks' params - handle exceptions
    result = asyncio.run(
        run_scraper(
            command="scrape_upcoming",
            sport="football",
            date=formatted_date,
            leagues=["premier-league"],
            storage_type="remote",
            headless=True,
            markets=["1x2"],
        )
    )

    if result is None:
        return {"statusCode": 500, "body": "Scraper failed to return data"}

    return {
        "statusCode": 200,
        "body": {
            "successful": result.stats.successful,
            "failed": result.stats.failed,
            "success_rate": f"{result.stats.success_rate:.1f}%",
            "data": result.success,
        },
    }
