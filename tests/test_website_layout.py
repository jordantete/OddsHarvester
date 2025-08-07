import json

from bs4 import BeautifulSoup
from playwright.sync_api import Page, sync_playwright
import pytest

from tests.test_website_config import (
    SELECTORS,
    TEST_CASES,
    VALIDATION_THRESHOLDS,
    validate_test_case,
)


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


class WebsiteLayoutTester:
    """Class to test the integrity of OddsPortal layout."""

    def __init__(self, page: Page):
        self.page = page
        self.logs = []

    def log(self, message: str):
        """Adds a log message."""
        self.logs.append(message)
        print(f"🔍 {message}")

    def navigate_to_match(self, url: str) -> bool:
        """Navigates to the match page."""
        try:
            self.page.goto(url, timeout=10000, wait_until="domcontentloaded")
            self.log(f"✅ Navigation successful to {url}")
            return True
        except Exception as e:
            self.log(f"❌ Navigation failed: {e}")
            return False

    def wait_for_market_tabs(self, timeout: int = 10000) -> bool:
        """Waits for market tabs to load."""
        try:
            # Wait for page to be fully loaded
            self.page.wait_for_load_state("networkidle", timeout=timeout)

            # Wait for tabs selector
            self.page.wait_for_selector(SELECTORS["market_tabs"], timeout=timeout)

            # Additional wait to ensure tabs are fully loaded
            self.page.wait_for_timeout(2000)

            tabs_count = self.page.locator(SELECTORS["market_tabs"]).count()
            self.log(f"✅ {tabs_count} market tabs found")
            return tabs_count > 0
        except Exception as e:
            self.log(f"❌ Failed to load tabs: {e}")
            return False

    def get_market_tabs_text(self) -> list[str]:
        """Gets the text of market tabs."""
        try:
            tabs = self.page.locator(SELECTORS["market_tabs"])
            tab_texts = []
            for i in range(tabs.count()):
                tab_text = tabs.nth(i).text_content().strip()
                if tab_text:
                    tab_texts.append(tab_text)
            self.log(f"📋 Tabs found: {tab_texts}")
            return tab_texts
        except Exception as e:
            self.log(f"❌ Error retrieving tabs: {e}")
            return []

    def click_market_tab(self, tab_index: int) -> bool:
        """Clicks on a specific market tab."""
        try:
            tabs = self.page.locator(SELECTORS["market_tabs"])
            if tab_index < tabs.count():
                tabs.nth(tab_index).click()
                self.page.wait_for_timeout(1000)  # Wait for loading
                self.log(f"✅ Click on tab {tab_index}")
                return True
            else:
                self.log(f"❌ Tab {tab_index} not found")
                return False
        except Exception as e:
            self.log(f"❌ Error clicking on tab {tab_index}: {e}")
            return False

    def check_odds_presence(self, market_name: str) -> bool:
        """Checks for the presence of odds for a given market."""
        try:
            # Wait for odds to load
            self.page.wait_for_selector(SELECTORS["odds_button"], timeout=3000)

            odds_buttons = self.page.locator(SELECTORS["odds_button"])
            odds_count = odds_buttons.count()

            if odds_count > 0:
                self.log(f"✅ {odds_count} odds found for {market_name}")
                return True
            else:
                self.log(f"❌ No odds found for {market_name}")
                return False
        except Exception as e:
            self.log(f"❌ Error checking odds for {market_name}: {e}")
            return False

    def extract_event_header_data(self) -> dict | None:
        """Extracts data from the React event header."""
        try:
            html_content = self.page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            script_tag = soup.find("div", id="react-event-header")

            if not script_tag:
                self.log("❌ React event header not found")
                return None

            try:
                json_data = json.loads(script_tag.get("data", "{}"))
                self.log("✅ JSON data extracted from event header")
                return json_data
            except (TypeError, json.JSONDecodeError) as e:
                self.log(f"❌ JSON parsing error: {e}")
                return None
        except Exception as e:
            self.log(f"❌ Error extracting header: {e}")
            return None

    def validate_event_data(self, event_data: dict, test_case: dict) -> bool:
        """Validates event data against expectations."""
        try:
            event_body = event_data.get("eventBody", {})
            event_data_obj = event_data.get("eventData", {})

            # Team validation
            home_team = event_data_obj.get("home")
            away_team = event_data_obj.get("away")
            expected_home, expected_away = test_case["expected_teams"]

            if home_team != expected_home:
                self.log(f"❌ Expected home team: {expected_home}, found: {home_team}")
                return False

            if away_team != expected_away:
                self.log(f"❌ Expected away team: {expected_away}, found: {away_team}")
                return False

            # League validation
            if test_case.get("expected_league"):
                league = event_data_obj.get("tournamentName")
                if league != test_case["expected_league"]:
                    self.log(f"❌ Expected league: {test_case['expected_league']}, found: {league}")
                    return False

            # Score validation (if available)
            if test_case.get("expected_score"):
                home_score = event_body.get("homeResult")
                away_score = event_body.get("awayResult")
                expected_home_score, expected_away_score = test_case["expected_score"]

                if home_score != expected_home_score:
                    self.log(f"❌ Expected home score: {expected_home_score}, found: {home_score}")
                    return False

                if away_score != expected_away_score:
                    self.log(f"❌ Expected away score: {expected_away_score}, found: {away_score}")
                    return False

            # Venue validation (if available)
            if test_case.get("expected_venue"):
                venue = event_body.get("venue")
                if venue != test_case["expected_venue"]:
                    self.log(f"❌ Expected venue: {test_case['expected_venue']}, found: {venue}")
                    return False

            self.log("✅ Event data validation successful")
            return True

        except Exception as e:
            self.log(f"❌ Error during data validation: {e}")
            return False

    def test_market_integrity(self, test_case: dict) -> bool:
        """Tests the complete integrity of a market."""
        self.log(f"🧪 Testing market: {test_case['description']}")

        # Pre-validation of test case
        validation_errors = validate_test_case(test_case)
        if validation_errors:
            for error in validation_errors:
                self.log(f"❌ Validation error: {error}")
            return False

        # Navigation
        if not self.navigate_to_match(test_case["url"]):
            return False

        # Wait for tabs
        if not self.wait_for_market_tabs():
            return False

        # Get available tabs
        available_tabs = self.get_market_tabs_text()
        if not available_tabs:
            return False

        # Test each expected market
        markets_to_test = test_case["markets"]
        successful_markets = 0
        market_results = {}

        for i, market in enumerate(markets_to_test):
            self.log(f"📊 Testing market: {market}")

            # Click on corresponding tab
            if i < len(available_tabs):
                if self.click_market_tab(i):
                    odds_present = self.check_odds_presence(market)
                    if odds_present:
                        successful_markets += 1
                        market_results[market] = "SUCCESS"
                        self.log(f"✅ Market {market} validated")
                    else:
                        market_results[market] = "NO_ODDS"
                        self.log(f"❌ Market {market} failed - no odds")
                else:
                    market_results[market] = "CLICK_FAILED"
                    self.log(f"❌ Unable to click on tab for {market}")
            else:
                market_results[market] = "TAB_NOT_AVAILABLE"
                self.log(f"⚠️ Tab {i} not available for {market}")

        # Event data validation
        event_data = self.extract_event_header_data()
        event_validation = True
        if event_data:
            event_validation = self.validate_event_data(event_data, test_case)
        else:
            self.log("⚠️ No event data to validate")

        # Calculate success rate
        success_rate = successful_markets / len(markets_to_test) if markets_to_test else 0
        min_success_rate = VALIDATION_THRESHOLDS["min_success_rate"]

        # Detailed summary
        self.log("📈 Test Summary:")
        self.log(f"   - Markets tested: {len(markets_to_test)}")
        self.log(f"   - Successful markets: {successful_markets}")
        self.log(f"   - Success rate: {success_rate:.1%}")
        self.log(f"   - Minimum threshold: {min_success_rate:.1%}")

        for market, result in market_results.items():
            status_emoji = "✅" if result == "SUCCESS" else "❌"
            self.log(f"   {status_emoji} {market}: {result}")

        # Final validation
        overall_success = success_rate >= min_success_rate and event_validation

        if overall_success:
            self.log("🎉 Integrity test successful!")
        else:
            self.log("💥 Integrity test failed!")
            if success_rate < min_success_rate:
                self.log(f"   - Insufficient success rate ({success_rate:.1%} < {min_success_rate:.1%})")
            if not event_validation:
                self.log("   - Event data validation failed")

        return overall_success


@pytest.mark.skip(reason="Requires Playwright browser installation")
@pytest.mark.parametrize("test_case", TEST_CASES, ids=[case["sport"] for case in TEST_CASES])
def test_match_layout_integrity(page, test_case):
    """Parameterized test to verify layout integrity for different sports."""
    tester = WebsiteLayoutTester(page)

    assert tester.test_market_integrity(
        test_case
    ), f"Test failed for {test_case['sport']}: {test_case['description']}\nLogs: {chr(10).join(tester.logs)}"


@pytest.mark.skip(reason="Requires Playwright browser installation")
def test_website_basic_functionality(page):
    """Basic test to verify that the site works."""
    tester = WebsiteLayoutTester(page)

    # Test with the first test case
    test_case = TEST_CASES[0]

    # Simple navigation
    assert tester.navigate_to_match(test_case["url"]), "Navigation failed"

    # Tab verification
    assert tester.wait_for_market_tabs(), "Market tabs not found"

    # Event data verification
    event_data = tester.extract_event_header_data()
    assert event_data is not None, "Event data not found"

    print("✅ Basic test successful - site works correctly")


def test_test_configuration():
    """Test to verify test configuration."""
    assert len(TEST_CASES) > 0, "No test cases defined"

    for i, case in enumerate(TEST_CASES):
        assert "url" in case, f"URL missing in test case {i}"
        assert "markets" in case, f"Markets missing in test case {i}"
        assert "expected_teams" in case, f"Expected teams missing in test case {i}"
        assert len(case["expected_teams"]) == 2, f"Two teams expected in test case {i}"

    print("✅ Test configuration valid")


def test_sport_coverage():
    """Test to verify sport coverage."""
    sports = [case["sport"] for case in TEST_CASES]
    unique_sports = set(sports)

    # Check that we have at least 2 different sports (football variants count as football)
    football_variants = [s for s in sports if s.startswith("football")]
    assert (
        len(football_variants) >= 2
    ), f"Insufficient football coverage: only {len(football_variants)} football variants"

    # Check that we have football coverage
    assert "football" in unique_sports or any(s.startswith("football") for s in unique_sports), "No football coverage"

    print(f"✅ Sport coverage: {unique_sports}")


def test_market_variety():
    """Test to verify market variety."""
    all_markets = []
    for case in TEST_CASES:
        all_markets.extend(case["markets"])

    unique_markets = set(all_markets)

    # Check that we have good market variety
    assert len(unique_markets) >= 5, f"Insufficient variety: only {len(unique_markets)} unique markets"

    # Check that we have the main markets
    expected_markets = {"1X2", "Draw No Bet", "Both Teams to Score", "Double Chance"}
    covered_markets = expected_markets.intersection(unique_markets)
    assert len(covered_markets) >= 2, f"Main markets missing: {expected_markets - unique_markets}"

    print(f"✅ Market variety: {unique_markets}")


def test_url_validity():
    """Test to verify URL validity."""
    for i, case in enumerate(TEST_CASES):
        url = case["url"]

        # Check that URL is valid
        assert url.startswith("https://www.oddsportal.com/"), f"Invalid URL in case {i}: {url}"
        assert "/" in url[25:], f"Malformed URL in case {i}: {url}"

        # Check that URL contains the base sport (football for football variants)
        base_sport = case["sport"].split("-")[0]  # Extract base sport from football-2, football-3, etc.
        sport_in_url = base_sport in url
        assert sport_in_url, f"Sport '{base_sport}' not found in URL: {url}"

    print("✅ URLs valid")


@pytest.mark.skip(reason="Requires Playwright browser installation")
def test_individual_sport_functionality(page):
    """Individual test for each sport."""
    tester = WebsiteLayoutTester(page)

    for test_case in TEST_CASES:
        sport = test_case["sport"]
        print(f"\n🧪 Individual test for {sport}")

        # Navigation test
        navigation_success = tester.navigate_to_match(test_case["url"])
        assert navigation_success, f"Navigation failed for {sport}"

        # Tab test
        tabs_success = tester.wait_for_market_tabs()
        assert tabs_success, f"Tabs not found for {sport}"

        # Event data test
        event_data = tester.extract_event_header_data()
        if event_data:
            validation_success = tester.validate_event_data(event_data, test_case)
            assert validation_success, f"Data validation failed for {sport}"

        print(f"✅ {sport} works correctly")
