"""See module docstring in core/browser/__init__.py."""

from dataclasses import dataclass
import logging

from playwright.async_api import ElementHandle, Page

from oddsharvester.core.browser.market_navigation import HASH_SWITCH_JS
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import (
    BOOKIES_FILTER_TIMEOUT_MS,
    FALLBACK_VERIFY_WAIT_MS,
    MARKET_SWITCH_WAIT_TIME_MS,
    PERIOD_SELECTOR_TIMEOUT_MS,
)


@dataclass(frozen=True)
class SelectionStrategy:
    """Configuration for a sub-nav selection (bookies filter, period, ...).

    2026-08 redesign: both controls are rendered as sub-nav tabs
    (`sub-nav-active-tab` / `sub-nav-inactive-tab`); a tab is targeted by its
    display text and verified by its testid flipping to the active variant.
    """

    name: str
    tab_selector: str
    active_testid: str
    timeout_ms: int


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
                    self.logger.error(f"{strategy.name} target element not found for: {display_label}")
                return False

            if await target.get_attribute("data-testid") == strategy.active_testid:
                self.logger.info(f"{strategy.name} already set to '{display_label}'. No action needed.")
                return True

            self.logger.info(f"Clicking {strategy.name}: {display_label}")
            await target.click()
            await page.wait_for_timeout(FALLBACK_VERIFY_WAIT_MS)

            # Re-locate: the SPA re-renders the tab on selection.
            target = await self._find_tab(page, strategy, label)
            if target is not None and await target.get_attribute("data-testid") == strategy.active_testid:
                self.logger.info(f"Successfully set {strategy.name} to: {display_label}")
                return True

            self.logger.error(f"Failed to set {strategy.name} to: {display_label}")
            return False

        except Exception as e:
            self.logger.error(f"Error setting {strategy.name}: {e}")
            return False

    async def _find_tab(self, page: Page, strategy: SelectionStrategy, label: str) -> ElementHandle | None:
        tabs = await page.query_selector_all(strategy.tab_selector)
        for tab in tabs:
            text = (await tab.text_content() or "").strip()
            if text.lower() == label:
                return tab
        return None


class PeriodSelector:
    """Select a match period by its language-independent URL-fragment scope code.

    The active period is the `;<scope>` segment of the fragment (e.g.
    `…:over-under;2`). Scope ids are global and identical across localized
    mirrors (gotchas §7). The redesigned SPA routes the whole match view off
    the hash, so the scope is selected by rewriting the fragment directly.
    Returns None when no scope code is verified for `(sport, period)`,
    signalling the caller to fall back to label-based selection.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def select_by_scope(self, page: Page, sport: str | None, internal_period: str) -> bool | None:
        """Return True if the target scope is active, False if unreachable, None if no scope is known.

        Only ever returns True when the active fragment scope equals the target, so
        a wrong period is never silently selected.
        """
        target = OddsPortalSelectors.period_scope_code(sport, internal_period)
        if target is None:
            return None

        if OddsPortalSelectors.period_scope_from_url(page.url) == target:
            self.logger.info(f"Period scope {target} already active for '{internal_period}'.")
            return True

        fragment = OddsPortalSelectors.event_id_from_url(page.url)
        code = OddsPortalSelectors.market_code_from_url(page.url)
        if not fragment or not code:
            self.logger.warning(
                f"Cannot select period scope {target} for '{internal_period}': no market fragment in URL."
            )
            return False

        try:
            await page.evaluate(HASH_SWITCH_JS, {"fragment": fragment, "code": code, "scope": target})
            await page.wait_for_timeout(MARKET_SWITCH_WAIT_TIME_MS)
        except Exception as e:
            self.logger.warning(f"Hash switch to period scope {target} failed: {e}")
            return False

        if OddsPortalSelectors.period_scope_from_url(page.url) == target:
            self.logger.info(f"Selected period scope {target} for '{internal_period}' via the URL hash.")
            return True

        self.logger.warning(f"Could not reach period scope {target} for '{internal_period}' via the URL hash.")
        return False


# === Concrete strategies ===

BOOKIES_FILTER_STRATEGY = SelectionStrategy(
    name="bookies-filter",
    tab_selector=OddsPortalSelectors.SUB_NAV_TAB_ANY,
    active_testid=OddsPortalSelectors.SUB_NAV_TAB_ACTIVE_TESTID,
    timeout_ms=BOOKIES_FILTER_TIMEOUT_MS,
)

PERIOD_STRATEGY = SelectionStrategy(
    name="period",
    tab_selector=OddsPortalSelectors.SUB_NAV_TAB_ANY,
    active_testid=OddsPortalSelectors.SUB_NAV_TAB_ACTIVE_TESTID,
    timeout_ms=PERIOD_SELECTOR_TIMEOUT_MS,
)
