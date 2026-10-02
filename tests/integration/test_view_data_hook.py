"""The view data hook and its wait, run in the bundled Chromium on a page served locally: no network, no HAR."""

from playwright.async_api import async_playwright
import pytest

from oddsharvester.core.browser.market_navigation import HASH_SWITCH_JS, STALE_TAB_ATTRIBUTE
from oddsharvester.core.browser.view_data import VIEW_DATA_HOOK_JS, VIEW_DATA_JS
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors

# WebCrypto needs a secure context, so the page comes from a routed https origin.
ORIGIN = "https://view-data.test"
PAGE = "<html><body><main><ul><li class='tab-item'>1X2</li></ul></main><iframe src='/frame'></iframe></body></html>"

# Encrypts each case's plaintext as the site does (AES-CBC), decrypts it through crypto.subtle, and returns what the
# caller got back and what the hook recorded.
DECRYPT_CASES_JS = r"""
async (cases) => {
    const usages = ['encrypt', 'decrypt'];
    const key = await crypto.subtle.importKey('raw', new Uint8Array(32), {name: 'AES-CBC'}, false, usages);
    const iv = new Uint8Array(16);
    const gzip = async (bytes) => new Uint8Array(
        await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
    const out = {};
    for (const [name, spec] of Object.entries(cases)) {
        window.__ohViewData = [];
        let bytes = new TextEncoder().encode(JSON.stringify(spec.body) + (spec.trailing || ''));
        for (let i = 0; i < (spec.gzip || 0); i++) bytes = await gzip(bytes);
        const cipher = await crypto.subtle.encrypt({name: 'AES-CBC', iv}, key, bytes);
        const plain = new Uint8Array(await crypto.subtle.decrypt({name: 'AES-CBC', iv}, key, cipher));
        await new Promise((resolve) => setTimeout(resolve, 100));
        out[name] = {returned: plain.length === bytes.length && plain.every((b, i) => b === bytes[i]),
                     recorded: window.__ohViewData || []};
    }
    try {
        await crypto.subtle.decrypt({name: 'AES-CBC', iv}, key, new Uint8Array(15));
        out.rejected = false;
    } catch (e) {
        out.rejected = true;
    }
    return out;
}
"""


def _view(market, nav, event="EVT", scope=2):
    return {"s": 1, "d": {"bt": market, "sc": scope, "nav": nav, "encodeventId": event, "oddsdata": {}}}


@pytest.fixture
async def page():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_init_script(VIEW_DATA_HOOK_JS)

        async def serve(route):
            body = PAGE if route.request.url == f"{ORIGIN}/" else "<html><body>frame</body></html>"
            await route.fulfill(status=200, content_type="text/html", body=body)

        await context.route(f"{ORIGIN}/**", serve)
        page = await context.new_page()
        await page.goto(f"{ORIGIN}/")
        yield page
        await browser.close()


@pytest.mark.integration
class TestTheHook:
    async def test_each_view_data_answer_is_recorded_as_the_page_reads_it(self, page):
        offered = {"1": {"2": ["141"]}, "13": {"2": ["141", "909"]}}
        cases = {
            "gzip": {"body": _view(13, offered), "gzip": 1},
            "plain": {"body": _view(4, {"4": {"2": ["141"]}})},
            "gzip twice": {"body": _view(5, {"5": {"2": ["141"]}}), "gzip": 2},
            "trailing bytes": {"body": _view(2, {"2": {"2": ["141"]}}), "gzip": 1, "trailing": "\u0000\u0000junk"},
            "not view data": {"body": {"s": 1, "d": {"nav": offered, "defaultBettingType": 1}}, "gzip": 1},
        }

        out = await page.evaluate(DECRYPT_CASES_JS, cases)

        assert all(result["returned"] for name, result in out.items() if name != "rejected")
        assert out["rejected"] is True
        assert out["gzip"]["recorded"] == [{"event": "EVT", "market": 13, "scope": 2, "offered": [1, 13]}]
        assert [r["market"] for r in out["plain"]["recorded"]] == [4]
        assert [r["market"] for r in out["gzip twice"]["recorded"]] == [5]
        assert [r["market"] for r in out["trailing bytes"]["recorded"]] == [2]
        assert out["not view data"]["recorded"] == []

    async def test_a_market_without_any_bookmaker_is_not_offered(self, page):
        """The view asks for its default market when the requested one has no bookmaker list: so must the guard."""
        nav = {"1": {"2": ["141"]}, "13": {"2": [], "3": []}}

        out = await page.evaluate(DECRYPT_CASES_JS, {"empty lists": {"body": _view(1, nav), "gzip": 1}})

        assert out["empty lists"]["recorded"][0]["offered"] == [1]

    async def test_frames_other_than_the_view_keep_the_native_decrypt(self, page):
        """The view decrypts in the top frame; a third-party frame must not see a wrapped decrypt."""
        frame = page.frames[1]
        native = await frame.evaluate("Function.prototype.toString.call(SubtleCrypto.prototype.decrypt)")

        assert native == "function decrypt() { [native code] }"


@pytest.mark.integration
class TestTheWaitForViewData:
    @staticmethod
    async def _settled(page, records, market, event="EVT"):
        await page.evaluate("(records) => { window.__ohViewData = records; }", records)
        return await page.evaluate(VIEW_DATA_JS, {"event": event, "market": market})

    async def test_it_settles_on_any_record_of_the_market_switched_to(self, page):
        stale = {"event": "EVT", "market": 1, "scope": 2, "offered": [1, 13]}
        switched = {"event": "EVT", "market": 13, "scope": 2, "offered": [1, 13]}

        assert await self._settled(page, [stale], 13) is False
        assert await self._settled(page, [switched, stale], 13) == [switched, stale]

    async def test_it_settles_at_once_on_a_market_the_match_lacks(self, page):
        fallback = {"event": "EVT", "market": 1, "scope": 2, "offered": [1, 2]}

        assert await self._settled(page, [fallback], 13) == [fallback]

    async def test_it_reads_only_the_event_switched(self, page):
        other = {"event": "OTHER", "market": 13, "scope": 2, "offered": [13]}

        assert await self._settled(page, [other], 13) is False

    async def test_a_hash_switch_clears_the_records_of_the_previous_view(self, page):
        await page.evaluate("() => { window.__ohViewData = [{event: 'EVT', market: 2, scope: 2, offered: [2]}]; }")
        args = {
            "fragment": "EVT",
            "code": "over-under",
            "scope": 2,
            "tabs": OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR,
            "stale": STALE_TAB_ATTRIBUTE,
        }

        await page.evaluate(HASH_SWITCH_JS, args)

        assert await page.evaluate("window.__ohViewData") == []
