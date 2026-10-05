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


@pytest.fixture
def storage_site():
    """A page on 127.0.0.1 that frames localhost, whose frame stores a value; yields the page and a localhost page."""
    pages = {
        "/top": "<html><body><iframe id='f' src='http://localhost:{port}/frame'></iframe></body></html>",
        "/frame": "<html><body><script>localStorage.setItem('k', 'set-by-3p-iframe');</script></body></html>",
        "/read": "<html><body>read</body></html>",
    }

    class Site(BaseHTTPRequestHandler):
        def do_GET(self):
            body = pages.get(self.path, "").format(port=self.server.server_address[1]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    yield f"http://127.0.0.1:{port}/top", f"http://localhost:{port}/read"
    server.shutdown()
    server.server_close()


@pytest.mark.parametrize("docker", [False, True], ids=["local", "docker"])
async def test_playwrights_disabled_features_still_apply(launch, monkeypatch, storage_site, docker):
    """Playwright disables ThirdPartyStoragePartitioning; an argument replacing its list would partition the frame."""
    monkeypatch.setattr("oddsharvester.core.playwright_manager.is_running_in_docker", lambda: docker)
    manager = await launch()
    top, read = storage_site

    await manager.page.goto(top)
    frame = next(f for f in manager.page.frames if f.url.endswith("/frame"))
    await frame.wait_for_function("localStorage.getItem('k') !== null")
    await manager.page.goto(read)

    assert await manager.page.evaluate("localStorage.getItem('k')") == "set-by-3p-iframe"


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


async def test_the_client_hints_and_the_plugins_are_a_headed_chromiums(launch, echo):
    """The headless shell names HeadlessChrome in sec-ch-ua whatever the user agent, and has no plugins."""
    url, seen = echo
    manager = await launch()

    await manager.page.goto(url)

    major = manager.browser.version.split(".")[0]
    assert "HeadlessChrome" not in seen[-1]["sec-ch-ua"]
    assert f'"Chromium";v="{major}"' in seen[-1]["sec-ch-ua"]
    assert await manager.page.evaluate("typeof navigator.plugins[0]") == "object"
