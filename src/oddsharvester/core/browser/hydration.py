"""Bring the hash-driven match view of a match page on screen (gotchas §19, §20)."""

import logging

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from oddsharvester.core.browser.waits import wait_for_element
from oddsharvester.core.exceptions import H2HFragmentResolutionError
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import (
    HASH_NUDGE_DELAY_MS,
    LOGIN_MODAL_CLOSE_WAIT_MS,
    MATCH_HYDRATION_ATTEMPTS,
    MATCH_HYDRATION_TIMEOUT_MS,
)

logger = logging.getLogger(__name__)

# Hydration needs a market tab that exists for the sport; two-outcome sports
# have no 1X2 tab. Adjusted by live validation, not exhaustive.
DEFAULT_MARKET_CODE_BY_SPORT: dict[str, str] = {
    "tennis": "home-away",
    "basketball": "home-away",
    "baseball": "home-away",
    "american-football": "home-away",
    "volleyball": "home-away",
    "cricket": "home-away",
}

# The SPA renders the fragment match on load again since 2026-09, so the hash
# nudge is only a retry. Setting the bare id first guarantees the second
# assignment is a change even when the page URL already carried the full form.
HASH_NUDGE_JS = """
(args) => {
    if (args.bare) {
        window.location.hash = '';
        setTimeout(() => {
            window.location.hash = '#' + args.fragment;
            window.dispatchEvent(new HashChangeEvent('hashchange', { newURL: window.location.href }));
        }, args.delayMs);
        return;
    }
    window.location.hash = '#' + args.fragment;
    setTimeout(() => {
        window.location.hash = '#' + args.fragment + ':' + args.code + ';' + args.scope;
        window.dispatchEvent(new HashChangeEvent('hashchange', { newURL: window.location.href }));
    }, args.delayMs);
}
"""


def default_market_code(sport: str | None) -> str:
    """The market code a match view of `sport` opens on: its own default tab, else 1X2."""
    return DEFAULT_MARKET_CODE_BY_SPORT.get((sport or "").lower(), "1X2")


async def dismiss_login_modal(page: Page) -> None:
    """Close the login modal that can block match-page rendering on cold profiles."""
    try:
        el = await page.query_selector(OddsPortalSelectors.LOGIN_MODAL_CLOSE)
        if el and await el.is_visible():
            await el.click()
            await wait_for_element(
                page,
                OddsPortalSelectors.LOGIN_MODAL_CLOSE,
                LOGIN_MODAL_CLOSE_WAIT_MS,
                "login modal closing",
                state="hidden",
            )
            logger.info("Dismissed the login modal.")
    except Exception as e:
        logger.debug(f"Login modal dismissal skipped: {e}")


async def hydrate_match_view(page: Page, match_link: str, sport: str | None = None) -> None:
    """Wait for the SPA to render the match view, nudging the hash if it does not.

    The view renders on load, so each attempt waits for the market tabs and
    only then re-routes the hash (bare id on in-play pages, which own their
    market codes; '#<id>:<market>;<scope>' elsewhere, the market being the
    sport's default). Raises H2HFragmentResolutionError (retryable,
    proxy-neutral) when the view never renders.
    """
    fragment = OddsPortalSelectors.event_id_from_url(match_link)
    inplay = "/inplay-odds/" in match_link
    code = default_market_code(sport)
    scope = OddsPortalSelectors.period_scope_code("FullTime") or 2

    for attempt in range(1, MATCH_HYDRATION_ATTEMPTS + 1):
        try:
            await page.wait_for_selector(
                OddsPortalSelectors.MATCH_CONTENT_READY_SELECTOR, timeout=MATCH_HYDRATION_TIMEOUT_MS
            )
            return
        except PlaywrightTimeoutError:
            logger.warning(
                f"Match view hydration attempt {attempt}/{MATCH_HYDRATION_ATTEMPTS} timed out for {match_link}"
            )
            await dismiss_login_modal(page)
            if fragment is None:
                # Without an event id in the URL the hash nudge has nothing to route to.
                break
            nudge = {"fragment": fragment, "delayMs": HASH_NUDGE_DELAY_MS}
            nudge.update({"bare": True} if inplay else {"code": code, "scope": scope})
            await page.evaluate(HASH_NUDGE_JS, nudge)

    raise H2HFragmentResolutionError(
        f"match view hydration failed: {match_link} never rendered match content", url=match_link
    )
