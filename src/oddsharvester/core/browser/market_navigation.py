"""See module docstring in core/browser/__init__.py."""

import asyncio
import logging
import re
import weakref

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from oddsharvester.core.browser.view_data import VIEW_DATA_JS, VIEW_DATA_RECORDED_JS
from oddsharvester.core.browser.waits import SIGNAL_POLL_MS, wait_for_signal
from oddsharvester.core.exceptions import MarketDataError
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import (
    MARKET_SWITCH_WAIT_TIME_MS,
    MARKET_TAB_TIMEOUT_MS,
    SCROLL_PAUSE_TIME_MS,
    TAB_SWITCH_WAIT_MS,
)

logger = logging.getLogger(__name__)

# What a market switch slept before its table was read: the tab switch, the market switch and the page load.
MARKET_VIEW_CAP_MS = TAB_SWITCH_WAIT_MS + MARKET_SWITCH_WAIT_TIME_MS + SCROLL_PAUSE_TIME_MS

STALE_TAB_ATTRIBUTE = "data-oh-stale"

# The data request of a switch answers in about 50 ms; a slow proxy gets the tab timeout, not the render cap.
VIEW_DATA_CAP_MS = MARKET_TAB_TIMEOUT_MS
# The view renders only once it decrypted its data, which the hook records about 7 ms later.
VIEW_DATA_RECORD_CAP_MS = 500

# Pages whose views recorded no decrypted data, warned about once.
_PAGES_WITHOUT_VIEW_DATA: weakref.WeakSet[Page] = weakref.WeakSet()

# In-page hash switch: the SPA routes the match view off location.hash
# ('#<id>:<market>;<scope>') and re-renders on hashchange (2026-08 redesign).
# The tabs are marked first: the view the switch renders brings unmarked ones.
HASH_SWITCH_JS = """
(args) => {
    window.__ohViewData = [];
    for (const tab of document.querySelectorAll(args.tabs)) tab.setAttribute(args.stale, '');
    window.location.hash = '#' + args.fragment + ':' + args.code + ';' + args.scope;
    window.dispatchEvent(new HashChangeEvent('hashchange', { newURL: window.location.href }));
}
"""

# The view of '#<id>:<code>;<scope>' rendered: unmarked tabs, and that code and scope in the hash.
FRESH_VIEW_JS = """
(args) => {
    if (!document.querySelector(args.tabs + ':not([' + args.stale + '])')) return false;
    const [code, scope] = (location.hash.split(':')[1] || '').split(';');
    return code === args.code && parseInt(scope, 10) === args.scope;
}
"""

# The active market tab names the market.
ACTIVE_TAB_JS = """
(args) => {
    const tab = document.querySelector(args.selector);
    return !!tab && (tab.textContent || '').toLowerCase().includes(args.name);
}
"""


async def switch_view(page: Page, fragment: str, code: str, scope: int, cap_ms: int) -> int:
    """Write '#<fragment>:<code>;<scope>' and wait for the view it renders; the id of the market it shows.

    Raises MarketDataError when the data request is not sent or not answered within VIEW_DATA_CAP_MS, comes back
    with an error, the view does not render within `cap_ms`, or its data carry another market the match offers:
    the table would show the previous view or the wrong market.
    """
    args = {
        "fragment": fragment,
        "code": code,
        "scope": scope,
        "tabs": OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR,
        "stale": STALE_TAB_ATTRIBUTE,
    }
    view = f"'{code};{scope}'"
    is_view_data = re.compile(rf"/proxy/match-event/[^/?]*-{re.escape(fragment)}-(\d+)-")
    try:
        async with page.expect_request(
            lambda request: is_view_data.search(request.url) is not None, timeout=VIEW_DATA_CAP_MS
        ) as sent:
            await page.evaluate(HASH_SWITCH_JS, args)
        request = await sent.value
        response = await asyncio.wait_for(request.response(), VIEW_DATA_CAP_MS / 1000)
    except (PlaywrightTimeoutError, TimeoutError) as e:
        raise MarketDataError(
            f"OddsPortal sent no data for the view {view} within {VIEW_DATA_CAP_MS} ms", url=page.url
        ) from e
    if response is None or not response.ok:
        answer = "no response" if response is None else f"HTTP {response.status}"
        raise MarketDataError(f"OddsPortal refused the data of the view {view}: {answer}", url=page.url)
    try:
        await page.wait_for_function(FRESH_VIEW_JS, arg=args, timeout=cap_ms, polling=SIGNAL_POLL_MS)
    except PlaywrightTimeoutError as e:
        raise MarketDataError(f"The view {view} did not render within {cap_ms} ms", url=page.url) from e

    market = OddsPortalSelectors.MARKET_FEED_IDS.get(code)
    records = await _view_data(page, fragment, market)
    if not records:
        if page not in _PAGES_WITHOUT_VIEW_DATA:
            _PAGES_WITHOUT_VIEW_DATA.add(page)
            logger.warning(f"No decrypted data recorded for the view {view}; reading markets from the requests.")
        return int(is_view_data.search(request.url).group(1))
    shown = market if any(record["market"] == market for record in records) else records[-1]["market"]
    if market is not None and market in records[-1]["offered"] and shown != market:
        raise MarketDataError(f"OddsPortal sent the data of market {shown} for the view {view}", url=page.url)
    return shown


async def _view_data(page: Page, fragment: str, market: int | None) -> list[dict]:
    """The decrypted view data recorded for the event since the switch, at most VIEW_DATA_RECORD_CAP_MS for them."""
    try:
        handle = await page.wait_for_function(
            VIEW_DATA_JS,
            arg={"event": fragment, "market": market},
            timeout=VIEW_DATA_RECORD_CAP_MS,
            polling=SIGNAL_POLL_MS,
        )
        return await handle.json_value()
    except PlaywrightTimeoutError:
        return await page.evaluate(VIEW_DATA_RECORDED_JS, fragment)


class MarketTabNavigator:
    """Switch the match view to a market tab, hash-first with a tab-click fallback."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def navigate_to_tab(self, page: Page, market_tab_name: str, timeout: int = MARKET_TAB_TIMEOUT_MS) -> bool:
        """Navigate to a market tab by its English name.

        Primary path rewrites the URL hash to the market's language-independent
        code (works on localized mirrors, gotchas §7). Fallback clicks the
        sports-nav tab matching the name (markets missing from MARKET_TAB_CODES,
        or a hash route the SPA refuses).
        """
        self.logger.info(f"Attempting to navigate to market tab: {market_tab_name}")

        # In-play views route their own market codes (e.g. 'O/U', not
        # 'over-under'); the pre-match hash path would flip or break the view.
        inplay = "/inplay-odds/" in page.url
        code = OddsPortalSelectors.MARKET_TAB_CODES.get(market_tab_name)
        if not inplay and code:
            reached = await self._navigate_by_hash(page, code, timeout)
            if reached:
                self.logger.info(f"Successfully navigated to {market_tab_name} tab (hash code '{code}').")
                return True
            if reached is None:
                return False

        if await self._click_tab_by_text(page, market_tab_name):
            self.logger.info(f"Successfully navigated to {market_tab_name} tab (tab click).")
            return True

        self.logger.error(f"Failed to reach the {market_tab_name} tab (hash and tab-click paths).")
        return False

    async def _navigate_by_hash(self, page: Page, code: str, timeout: int) -> bool | None:
        """True once the view shows `code`; None when the match does not offer it; False to try the tab click."""
        fragment = OddsPortalSelectors.event_id_from_url(page.url)
        if not fragment:
            return False
        current_scope = OddsPortalSelectors.period_scope_from_url(page.url)
        # Writing the hash the URL already holds does not re-render the view, so there is nothing to switch.
        if current_scope is not None and OddsPortalSelectors.market_code_from_url(page.url) == code:
            self.logger.info(f"Market code '{code}' and scope {current_scope} are already in the URL.")
            return True
        # Preserve the current period scope so a market switch keeps the period.
        scope = current_scope or 2
        try:
            shown = await switch_view(page, fragment, code, scope, MARKET_VIEW_CAP_MS)
            # For a market the match lacks, the view asks for its default market's data and shows that market.
            if shown != OddsPortalSelectors.MARKET_FEED_IDS.get(code, shown):
                self.logger.warning(f"The match offers no '{code}' market: OddsPortal showed market {shown} instead.")
                return None
            if OddsPortalSelectors.market_code_from_url(page.url) != code:
                return False
            await page.wait_for_selector(OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR, timeout=timeout)
            return True
        except MarketDataError:
            raise
        except Exception as e:
            self.logger.warning(f"Hash navigation to market code '{code}' failed: {e}")
            return False

    async def _click_tab_by_text(self, page: Page, market_tab_name: str) -> bool:
        try:
            elements = await page.query_selector_all(OddsPortalSelectors.MARKET_TAB_ANY)
            for element in elements:
                text = (await element.text_content() or "").strip()
                if text and market_tab_name.lower() in text.lower():
                    await element.click()
                    await wait_for_signal(
                        page,
                        ACTIVE_TAB_JS,
                        MARKET_VIEW_CAP_MS,
                        f"active '{market_tab_name}' tab",
                        arg={"selector": OddsPortalSelectors.MARKET_TAB_ACTIVE, "name": market_tab_name.lower()},
                    )
                    return await self._verify_tab_is_active(page, market_tab_name)
            self.logger.info(f"No sports-nav tab matched '{market_tab_name}'.")
            return False
        except Exception as e:
            self.logger.error(f"Error clicking market tab '{market_tab_name}': {e}")
            return False

    async def _verify_tab_is_active(self, page: Page, market_tab_name: str) -> bool:
        try:
            active = await page.query_selector(OddsPortalSelectors.MARKET_TAB_ACTIVE)
            if active:
                text = (await active.text_content() or "").strip()
                if text and market_tab_name.lower() in text.lower():
                    self.logger.info(f"Tab '{market_tab_name}' is confirmed active")
                    return True
            self.logger.warning(f"Tab '{market_tab_name}' is not confirmed as active")
            return False
        except Exception as e:
            self.logger.error(f"Error verifying active market tab: {e}")
            return False
