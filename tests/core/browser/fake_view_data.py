"""Stand-ins for the data a hash switch makes the match view request and render, for tests on mocked pages."""

from unittest.mock import AsyncMock, MagicMock

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from oddsharvester.core.browser.market_navigation import HASH_SWITCH_JS
from oddsharvester.core.browser.view_data import VIEW_DATA_JS, VIEW_DATA_RECORDED_JS
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors

NO_RESPONSE = "no response"
ALL_MARKETS = sorted(set(OddsPortalSelectors.MARKET_FEED_IDS.values()))


class _Sent:
    """Stands for page.expect_request: the data request the block sent, or a timeout at the cap."""

    def __init__(self, page, status, requested):
        self.page = page
        self.status = status
        self.requested = requested

    async def __aenter__(self):
        self.page.inside_data_wait = True
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.page.inside_data_wait = False
        if exc_type is None and self.status is None:
            raise PlaywrightTimeoutError("Timeout 10000ms exceeded.")
        return False

    @property
    def value(self):
        async def request():
            written = self.page.written
            market = self.requested or OddsPortalSelectors.MARKET_FEED_IDS[written["code"]]
            url = f"https://www.oddsportal.com/proxy/match-event/1-1-{written['fragment']}-{market}-{written['scope']}-c5.dat"
            sent = MagicMock(url=url)
            answer = None if self.status == NO_RESPONSE else MagicMock(status=self.status, ok=200 <= self.status < 300)
            sent.response = AsyncMock(return_value=answer)
            return sent

        return request()


def _loaded_view(url: str) -> dict:
    """The view already active when a page's URL names its market ('#<id>:<code>;<scope>'), before any switch."""
    return {
        "fragment": OddsPortalSelectors.event_id_from_url(url),
        "code": OddsPortalSelectors.market_code_from_url(url),
        "scope": OddsPortalSelectors.period_scope_from_url(url),
    }


def serve_view_data(page, status=200, requested=None, rendered=None, offered=None, decrypted=True) -> None:
    """Answer every hash switch on `page`, and record each hash written by an evaluate of HASH_SWITCH_JS.

    `status` is the HTTP status of the data answer (None: never sent, NO_RESPONSE: failed), `requested` the
    market id the view asks for (None: the code's), `rendered` the market id the decrypted data carries (None:
    the one requested), `offered` the markets the match offers (None: all), `decrypted=False` a view whose
    data the hook never recorded. Before any switch, the data are those of the view the page's URL names.
    Install after the page's own wait_for_function and evaluate mocks.
    """
    page.inside_data_wait = False
    page.written = None
    page.written_while_waiting = None
    page.expect_request = MagicMock(side_effect=lambda *args, **kwargs: _Sent(page, status, requested))

    def records():
        written = page.written or _loaded_view(page.url)
        market = rendered or requested or OddsPortalSelectors.MARKET_FEED_IDS[written["code"]]
        return [
            {
                "event": written["fragment"],
                "market": market,
                "scope": written["scope"],
                "offered": offered or ALL_MARKETS,
            }
        ]

    signals = page.wait_for_function

    async def wait_for_function(expression, *args, **kwargs):
        if expression != VIEW_DATA_JS:
            return await signals(expression, *args, **kwargs)
        settled = records()
        target = kwargs["arg"]["market"]
        if not decrypted or not any(r["market"] == target or target not in r["offered"] for r in settled):
            raise PlaywrightTimeoutError(f"Timeout {kwargs['timeout']}ms exceeded.")
        return MagicMock(json_value=AsyncMock(return_value=settled))

    page.wait_for_function = AsyncMock(side_effect=wait_for_function)
    scripts = page.evaluate

    async def evaluate(expression, *args):
        if expression == HASH_SWITCH_JS:
            page.written = args[0]
            page.written_while_waiting = page.inside_data_wait
        if expression == VIEW_DATA_RECORDED_JS:
            return records() if decrypted else []
        return await scripts(expression, *args)

    page.evaluate = AsyncMock(side_effect=evaluate)
