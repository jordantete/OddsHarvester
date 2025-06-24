from datetime import UTC, datetime
import json

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import pytest

TEST_MATCH_URL = "https://www.oddsportal.com/football/england/premier-league/leicester-brentford-xQ77QTN0"
MARKET_TABS_SELECTOR = "ul.visible-links.bg-black-main.odds-tabs > li"


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    page.close()


@pytest.mark.skip(reason="Requires Playwright browser installation")
def test_match_page_navigation(page):
    page.goto(TEST_MATCH_URL)

    market_tabs = page.locator(MARKET_TABS_SELECTOR)
    assert market_tabs.count() > 0, "No market tabs found! Website layout may have changed."

    print("✅ Website layout is intact. Scraper should work correctly.")


@pytest.mark.skip(reason="Requires Playwright browser installation")
def test_match_header_extraction(page):
    page.goto(TEST_MATCH_URL, timeout=5000, wait_until="domcontentloaded")

    html_content = page.content()
    soup = BeautifulSoup(html_content, "html.parser")
    script_tag = soup.find("div", id="react-event-header")

    assert script_tag, "React event header not found! Website layout may have changed."

    try:
        json_data = json.loads(script_tag.get("data"))
    except (TypeError, json.JSONDecodeError):
        pytest.fail("Error: Failed to parse JSON data from event header.")

    event_body = json_data.get("eventBody", {})
    event_data = json_data.get("eventData", {})
    unix_timestamp = event_body.get("startDate")

    match_date = (
        datetime.fromtimestamp(unix_timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M:%S %Z") if unix_timestamp else None
    )

    assert match_date, "Match date is missing!"
    assert event_data.get("home") == "Leicester", f"Expected home team 'Leicester', but got '{event_data.get('home')}'"
    assert event_data.get("away") == "Brentford", f"Expected away team 'Brentford', but got '{event_data.get('away')}'"
    assert (
        event_data.get("tournamentName") == "Premier League"
    ), f"Expected league 'Premier League', but got '{event_data.get('tournamentName')}'"

    assert (
        event_body.get("homeResult") == "0"
    ), f"Expected Leicester's final score to be 0, but got {event_body.get('homeResult')}"
    assert (
        event_body.get("awayResult") == "4"
    ), f"Expected Brentford's final score to be 4, but got {event_body.get('awayResult')}"

    assert (
        event_body.get("venue") == "King Power Stadium"
    ), f"Expected venue 'King Power Stadium', but got '{event_body.get('venue')}'"
    assert (
        event_body.get("venueTown") == "Leicester"
    ), f"Expected venue town 'Leicester', but got '{event_body.get('venueTown')}'"
    assert (
        event_body.get("venueCountry") == "England"
    ), f"Expected venue country 'England', but got '{event_body.get('venueCountry')}'"

    print("✅ Match header extraction is working correctly. Scraper should function properly.")
