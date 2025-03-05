class CLIHelpMessageGenerator:
    def generate(self):
        return (
            "Commands and arguments:\n\n"
            "  scrape_upcoming:\n"
            "    --sport         The sport to scrape (default: football).\n"
            "    --date          Date for upcoming matches (YYYYMMDD).\n"
            "    --league        Specific league to target for upcoming matches (e.g., england-premier-league).\n"
            "    --markets       Comma-separated list of betting markets to scrape (e.g., 1x2, btts, ...).\n"
            "    --storage       Storage type for scraped data (local or remote; default: local).\n"
            "    --file_path     File path to save data locally (default: scraped_data.csv).\n"
            "    --format        Format for saving local data (json).\n"
            "    --headless      Run the scraper in headless mode (default: False).\n"
            "    --save_logs     Save logs to a local file for debugging (default: False).\n\n"
            "  scrape_historic:\n"
            "    --sport         The sport to scrape (default: football).\n"
            "    --league        The league to scrape (e.g., england-premier-league).\n"
            "    --season        Season to scrape (format: YYYY-YYYY).\n"
            "    --markets       Comma-separated list of betting markets to scrape (e.g., 1x2, btts, ...).\n"
            "    --storage       Storage type for scraped data (local or remote; default: local).\n"
            "    --file_path     File path to save data locally (default: scraped_data.csv).\n"
            "    --format        Format for saving local data (json).\n"
            "    --max_pages     Maximum number of pages to scrape (optional).\n"
            "    --headless      Run the scraper in headless mode (default: False).\n"
            "    --save_logs     Save logs to a local file for debugging (default: False).\n\n"
            "Examples:\n"
            "  Scrape upcoming matches:\n"
            "    python main.py scrape_upcoming --sport football --date 20250101 --markets 1x2,btts,dnb --storage local --file_path output.json\n\n"
            "  Scrape historical odds:\n"
            "    python main.py scrape_historic --sport football --league england-premier-league --season 2022-2023 --markets 1x2 --storage remote --headless\n"
        )