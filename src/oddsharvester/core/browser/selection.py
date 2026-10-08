"""See module docstring in core/browser/__init__.py."""

from dataclasses import dataclass
import logging
import re

from playwright.async_api import ElementHandle, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from oddsharvester.core.browser.market_navigation import VIEW_DATA_CAP_MS, switch_view
from oddsharvester.core.browser.waits import wait_for_signal
from oddsharvester.core.exceptions import MarketDataError
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.core.sport_period_registry import SportPeriodRegistry
from oddsharvester.utils.constants import (
    FALLBACK_VERIFY_WAIT_MS,
    MARKET_SWITCH_WAIT_TIME_MS,
)

# The period bar is the second sub-nav group, after the bookies filter. Returns
# its tab count and the index of its bold tab (-1 when none), or null.
_PERIOD_BAR_JS = """
(args) => {
    const groups = new Map();
    for (const button of document.querySelectorAll(args.buttons)) {
        const group = button.parentElement;
        if (!group || !group.matches(args.group)) continue;
        if (!groups.has(group)) groups.set(group, []);
        groups.get(group).push(button);
    }
    const tabs = Array.from(groups.values())[1];
    if (!tabs) return null;
    const active = tabs.findIndex((tab) => (tab.getAttribute("style") || "").replaceAll(" ", "").includes(args.marker));
    return { tabs: tabs.length, active };
}
"""

# Finds the period bar exactly like _PERIOD_BAR_JS, then clicks its tab at
# args.index. Returns true when it clicked, false when the bar is not there.
_CLICK_PERIOD_TAB_JS = """
(args) => {
    const groups = new Map();
    for (const button of document.querySelectorAll(args.buttons)) {
        const group = button.parentElement;
        if (!group || !group.matches(args.group)) continue;
        if (!groups.has(group)) groups.set(group, []);
        groups.get(group).push(button);
    }
    const tabs = Array.from(groups.values())[1];
    if (!tabs || !tabs[args.index]) return false;
    tabs[args.index].click();
    return true;
}
"""


# The period bar shows its tab at args.index bold.
_PERIOD_TAB_ACTIVE_JS = (
    "(args) => { const bar = (" + _PERIOD_BAR_JS.strip() + ")(args); return !!bar && bar.active === args.index; }"
)

# Clears the recorded view data, then clicks the period bar's tab at args.index.
_INPLAY_CLICK_PERIOD_TAB_JS = (
    "(args) => { window.__ohViewData = []; return (" + _CLICK_PERIOD_TAB_JS.strip() + ")(args); }"
)

# The period bar shows its tab at args.index bold, and the view rendered the data of args.scope.
_INPLAY_PERIOD_SHOWN_JS = (
    "(args) => { const bar = (" + _PERIOD_BAR_JS.strip() + ")(args);"
    " return !!bar && bar.active === args.index"
    " && (window.__ohViewData || []).some((r) => r.event === args.event && r.scope === args.scope); }"
)

# A sub-nav button whose text is args.label carries the selected style.
_TAB_SHOWN_ACTIVE_JS = """
(args) => Array.from(document.querySelectorAll(args.selector)).some(
    (tab) =>
        (tab.textContent || "").trim().toLowerCase() === args.label &&
        (tab.getAttribute("style") || "").replaceAll(" ", "").includes(args.marker)
)
"""


@dataclass(frozen=True)
class SelectionStrategy:
    """Configuration for a sub-nav selection (bookies filter, period, ...).

    Both controls are rendered as plain sub-nav buttons; a tab is targeted by its
    display text and verified by the inline font-weight the SPA sets on the
    selected one (gotchas §20).
    """

    name: str
    tab_selector: str
    active_style_marker: str


def _is_active(style: str | None, strategy: SelectionStrategy) -> bool:
    """True when a sub-nav button carries the inline style marking it selected."""
    return strategy.active_style_marker.replace(" ", "") in (style or "").replace(" ", "")


class SelectionManager:
    """Ensure a sub-nav control is set to a target value."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def ensure_selected(
        self,
        page: Page,
        target_value: str,
        display_label: str,
        strategy: SelectionStrategy,
    ) -> bool:
        """Ensure the control described by `strategy` shows `display_label` as active.

        Returns True on success, False on tabs missing, target missing, or verify failure.
        """
        try:
            self.logger.info(f"Ensuring {strategy.name} is set to: {display_label}")

            label = (display_label or target_value).strip().lower()
            target = await self._find_tab(page, strategy, label)
            if target is None:
                tabs = await page.query_selector_all(strategy.tab_selector)
                if not tabs:
                    self.logger.warning(f"{strategy.name} navigation not found on page. Skipping selection.")
                else:
                    self.logger.warning(f"{strategy.name} target element not found for: {display_label}")
                return False

            if _is_active(await target.get_attribute("style"), strategy):
                self.logger.info(f"{strategy.name} already set to '{display_label}'. No action needed.")
                return True

            self.logger.info(f"Clicking {strategy.name}: {display_label}")
            await target.click()
            await wait_for_signal(
                page,
                _TAB_SHOWN_ACTIVE_JS,
                FALLBACK_VERIFY_WAIT_MS,
                f"selected {strategy.name} '{display_label}'",
                arg={
                    "selector": strategy.tab_selector,
                    "label": label,
                    "marker": strategy.active_style_marker.replace(" ", ""),
                },
            )

            # Re-locate: the SPA re-renders the tab on selection.
            target = await self._find_tab(page, strategy, label)
            if target is not None and _is_active(await target.get_attribute("style"), strategy):
                self.logger.info(f"Successfully set {strategy.name} to: {display_label}")
                return True

            self.logger.warning(f"Failed to set {strategy.name} to: {display_label}")
            return False

        except Exception as e:
            self.logger.warning(f"Error setting {strategy.name}: {e}")
            return False

    async def _find_tab(self, page: Page, strategy: SelectionStrategy, label: str) -> ElementHandle | None:
        tabs = await page.query_selector_all(strategy.tab_selector)
        for tab in tabs:
            text = (await tab.text_content() or "").strip()
            if text.lower() == label:
                return tab
        return None


def _is_default_period(sport: str | None, internal_period: str) -> bool:
    default = SportPeriodRegistry.get_default_period(sport or "")
    return default is not None and type(default).get_internal_value(default) == internal_period


class PeriodSelector:
    """Select a match period by its language-independent URL-fragment scope code.

    The active period is the `;<scope>` segment of the fragment (e.g.
    `…:over-under;2`). Scope ids are global and identical across localized
    mirrors (gotchas §7). The redesigned SPA routes the whole match view off
    the hash, so the scope is selected by rewriting the fragment directly.
    An in-play view is switched by clicking its period bar instead (_select_inplay).
    Returns None when no scope code is known for the period, signalling the
    caller to fall back to label-based selection.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def select_by_scope(self, page: Page, sport: str | None, internal_period: str) -> bool | None:
        """Return True if the target period is active, False if unreachable, None if no scope is known.

        The sport's default period needs the target scope in the URL. Any other
        period must also be on screen: a non-default period is kept when a later
        tab is bold, or when the first tab, clicked back to, writes the target
        scope. No label is read, so the check holds on localized mirrors.
        """
        target = OddsPortalSelectors.period_scope_code(internal_period)
        if target is None:
            return None

        if "/inplay-odds/" in page.url:
            return await self._select_inplay(page, sport, target, internal_period)

        if OddsPortalSelectors.period_scope_from_url(page.url) == target:
            self.logger.info(f"Period scope {target} already in the URL for '{internal_period}'.")
        else:
            fragment = OddsPortalSelectors.event_id_from_url(page.url)
            code = OddsPortalSelectors.market_code_from_url(page.url)
            if not fragment or not code:
                self.logger.warning(
                    f"Cannot select period scope {target} for '{internal_period}': no market fragment in URL."
                )
                return False

            try:
                await switch_view(page, fragment, code, target, MARKET_SWITCH_WAIT_TIME_MS)
            except MarketDataError:
                raise
            except Exception as e:
                self.logger.warning(f"Hash switch to period scope {target} failed: {e}")
                return False

            if OddsPortalSelectors.period_scope_from_url(page.url) != target:
                self.logger.warning(f"Could not reach period scope {target} for '{internal_period}' via the URL hash.")
                return False
            self.logger.info(f"Selected period scope {target} for '{internal_period}' via the URL hash.")

        if _is_default_period(sport, internal_period):
            return True
        return await self._period_is_on_screen(page, target, internal_period)

    async def _select_inplay(self, page: Page, sport: str | None, target: int, internal_period: str) -> bool:
        """Click the in-play period bar by position until a tab's data request carries the target scope.

        A scope written into an in-play hash requests nothing, or another market's data, for a period the
        market lacks; the bar lists only the shown market's periods (gotchas §16).
        """
        current = OddsPortalSelectors.period_scope_from_url(page.url)
        if current == target or (current is None and _is_default_period(sport, internal_period)):
            return True

        fragment = OddsPortalSelectors.event_id_from_url(page.url)
        bar_args = {
            "buttons": OddsPortalSelectors.SUB_NAV_TAB_ANY,
            "group": OddsPortalSelectors.SUB_NAV_GROUP_CSS,
            "marker": OddsPortalSelectors.SUB_NAV_ACTIVE_STYLE_MARKER.replace(" ", ""),
        }
        bar = await page.evaluate(_PERIOD_BAR_JS, bar_args)
        if not fragment or not bar or bar["tabs"] < 2:
            return self._refuse(target, internal_period, "the in-play view shows no period bar")

        is_view_data = re.compile(rf"/proxy/feed/live-event/[^/?]*-{re.escape(fragment)}-\d+-(\d+)-")
        seen = []
        for index in range(bar["tabs"]):
            if index == bar["active"]:
                continue
            try:
                async with page.expect_request(
                    lambda request: is_view_data.search(request.url) is not None, timeout=VIEW_DATA_CAP_MS
                ) as sent:
                    await page.evaluate(_INPLAY_CLICK_PERIOD_TAB_JS, {**bar_args, "index": index})
                request = await sent.value
            except PlaywrightTimeoutError as e:
                raise MarketDataError(
                    f"The in-play period tab {index + 1} sent no data request within {VIEW_DATA_CAP_MS} ms",
                    url=page.url,
                ) from e

            scope = int(is_view_data.search(request.url).group(1))
            if scope != target:
                seen.append(scope)
                continue

            response = await request.response()
            if response is None or not response.ok:
                answer = "no response" if response is None else f"HTTP {response.status}"
                raise MarketDataError(
                    f"OddsPortal refused the data of the in-play period scope {target}: {answer}", url=page.url
                )
            await wait_for_signal(
                page,
                _INPLAY_PERIOD_SHOWN_JS,
                MARKET_SWITCH_WAIT_TIME_MS,
                f"in-play period scope {target} shown",
                arg={**bar_args, "index": index, "event": fragment, "scope": target},
            )
            if OddsPortalSelectors.period_scope_from_url(page.url) != target:
                raise MarketDataError(f"The in-play period scope {target} did not reach the URL", url=page.url)
            self.logger.info(
                f"Selected in-play period scope {target} for '{internal_period}' (tab {index + 1} of {bar['tabs']})."
            )
            return True

        return self._refuse(
            target, internal_period, f"the in-play view offers no tab for it (its other tabs request scopes {seen})"
        )

    async def _period_is_on_screen(self, page: Page, target: int, internal_period: str) -> bool:
        """True when a later tab is bold, or the first tab, clicked back to, writes the target scope."""
        try:
            bar = await page.evaluate(
                _PERIOD_BAR_JS,
                {
                    "buttons": OddsPortalSelectors.SUB_NAV_TAB_ANY,
                    "group": OddsPortalSelectors.SUB_NAV_GROUP_CSS,
                    "marker": OddsPortalSelectors.SUB_NAV_ACTIVE_STYLE_MARKER.replace(" ", ""),
                },
            )
            if bar and bar["active"] > 0:
                self.logger.info(
                    f"Period scope {target} for '{internal_period}' is on screen "
                    f"(tab {bar['active'] + 1} of {bar['tabs']})."
                )
                return True

            if bar and bar["active"] == 0 and bar["tabs"] > 1:
                first_click = await self._click_period_tab(page, 1)
                if first_click is None:
                    return self._refuse(target, internal_period, "the page shows no period bar")

                back = await self._click_period_tab(page, 0)
                if back is None:
                    return self._refuse(target, internal_period, "the page shows no period bar")

                if first_click == target:
                    return self._refuse(target, internal_period, "clicking its period tabs did not change the URL")
                if back == target:
                    self.logger.info(
                        f"Period scope {target} for '{internal_period}' is on screen (tab 1 of {bar['tabs']})."
                    )
                    return True
                return self._refuse(
                    target,
                    internal_period,
                    "the page still shows its first period tab, so the match has no such period",
                )

            if not bar:
                reason = "the page shows no period bar"
            elif bar["active"] == 0:
                reason = "the page still shows its first period tab, so the match has no such period"
            else:
                reason = "no period tab is active"
            return self._refuse(target, internal_period, reason)
        except Exception as e:
            reason = f"reading the period bar failed: {e}"
            self.logger.warning(f"Period scope {target} for '{internal_period}' is not on screen: {reason}.")
            return False

    async def _click_period_tab(self, page: Page, index: int) -> int | None:
        """Click the period bar's tab at `index` and return the scope now in the URL, or None if not clicked."""
        clicked = await page.evaluate(
            _CLICK_PERIOD_TAB_JS,
            {
                "buttons": OddsPortalSelectors.SUB_NAV_TAB_ANY,
                "group": OddsPortalSelectors.SUB_NAV_GROUP_CSS,
                "index": index,
            },
        )
        if not clicked:
            return None
        await wait_for_signal(
            page,
            _PERIOD_TAB_ACTIVE_JS,
            FALLBACK_VERIFY_WAIT_MS if index == 1 else MARKET_SWITCH_WAIT_TIME_MS,
            f"period tab {index + 1} shown active",
            arg={
                "buttons": OddsPortalSelectors.SUB_NAV_TAB_ANY,
                "group": OddsPortalSelectors.SUB_NAV_GROUP_CSS,
                "marker": OddsPortalSelectors.SUB_NAV_ACTIVE_STYLE_MARKER.replace(" ", ""),
                "index": index,
            },
        )
        return OddsPortalSelectors.period_scope_from_url(page.url)

    def _refuse(self, target: int, internal_period: str, reason: str) -> bool:
        self.logger.warning(f"Period scope {target} for '{internal_period}' is not on screen: {reason}.")
        return False


# === Concrete strategies ===

BOOKIES_FILTER_STRATEGY = SelectionStrategy(
    name="bookies-filter",
    tab_selector=OddsPortalSelectors.SUB_NAV_TAB_ANY,
    active_style_marker=OddsPortalSelectors.SUB_NAV_ACTIVE_STYLE_MARKER,
)

PERIOD_STRATEGY = SelectionStrategy(
    name="period",
    tab_selector=OddsPortalSelectors.SUB_NAV_TAB_ANY,
    active_style_marker=OddsPortalSelectors.SUB_NAV_ACTIVE_STYLE_MARKER,
)
