"""What the browser PlaywrightManager launches tells a site, read on a page served on 127.0.0.1: no network, no HAR."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest

from oddsharvester.core.playwright_manager import PlaywrightManager

pytestmark = pytest.mark.integration

NAVIGATOR_JS = """() => ({
    userAgent: navigator.userAgent,
    languages: navigator.languages,
    webdriver: navigator.webdriver,
    webdriverOwn: Object.prototype.hasOwnProperty.call(navigator, "webdriver"),
})"""


@pytest.fixture
def echo():
    """A local page that records the headers of each request; yields its URL and the list of header dicts."""
    seen = []

    class Echo(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append({name.lower(): value for name, value in self.headers.items()})
            body = b"<html><body>echo</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Echo)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/", seen
    server.shutdown()
    server.server_close()


@pytest.fixture
async def launch(monkeypatch):
    """Initialize a PlaywrightManager headless with the given options; every manager is cleaned up afterwards."""
    monkeypatch.delenv("ODDSHARVESTER_HAR_REPLAY", raising=False)
    monkeypatch.delenv("ODDSHARVESTER_HAR_RECORD", raising=False)
    managers = []

    async def _launch(**options):
        manager = PlaywrightManager()
        managers.append(manager)
        await manager.initialize(headless=True, **options)
        return manager

    yield _launch
    for manager in managers:
        await manager.cleanup()


@pytest.mark.parametrize("docker", [False, True], ids=["local", "docker"])
async def test_the_disable_features_switch_chromium_reads_keeps_playwrights_list(launch, monkeypatch, docker):
    """Chromium reads only the last --disable-features switch, and Playwright puts its own before ours."""
    monkeypatch.setattr("oddsharvester.core.playwright_manager.is_running_in_docker", lambda: docker)
    manager = await launch()

    session = await manager.browser.new_browser_cdp_session()
    arguments = (await session.send("Browser.getBrowserCommandLine"))["arguments"]
    switches = [set(a.split("=", 1)[1].split(",")) for a in arguments if a.startswith("--disable-features=")]

    assert sorted(switches[0] - switches[-1]) == []
    assert {"IsolateOrigins", "site-per-process"} <= switches[-1]


async def test_the_user_agent_and_the_languages_agree_with_the_browser(launch, echo):
    url, seen = echo
    manager = await launch(locale="en-GB")

    await manager.page.goto(url)
    navigator = await manager.page.evaluate(NAVIGATOR_JS)

    headers = seen[-1]
    major = manager.browser.version.split(".")[0]
    assert headers["user-agent"] == navigator["userAgent"]
    assert "HeadlessChrome" not in headers["user-agent"]
    assert f" Chrome/{major}." in headers["user-agent"]
    assert headers["accept-language"] == "en-GB"
    assert navigator["languages"][0] == "en-GB"
    assert navigator["webdriver"] is False
    assert navigator["webdriverOwn"] is False


async def test_without_a_locale_the_browser_asks_for_en_us(launch, echo):
    url, seen = echo
    manager = await launch()

    await manager.page.goto(url)

    assert seen[-1]["accept-language"] == "en-US"
    assert await manager.page.evaluate("navigator.languages") == ["en-US"]
