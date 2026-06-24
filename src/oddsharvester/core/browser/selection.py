"""See module docstring in core/browser/__init__.py."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Literal

from playwright.async_api import ElementHandle, Page

from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors
from oddsharvester.utils.constants import (
    BOOKIES_FILTER_TIMEOUT_MS,
    FALLBACK_VERIFY_WAIT_MS,
    MARKET_SWITCH_WAIT_TIME_MS,
    PERIOD_SELECTOR_TIMEOUT_MS,
)

_SELECTION_WAIT_PREDICATE = """
(args) => {
    const container = document.querySelector(args.containerSelector);
    if (!container) return false;
    const activeElement = container.querySelector('.' + args.activeClass);
    if (!activeElement) return false;
    if (args.matchMode === 'attribute') {
        return activeElement.getAttribute(args.attributeName) === args.targetValue;
    }
    return activeElement.textContent.trim() === args.targetValue;
}
"""


@dataclass(frozen=True)
class SelectionStrategy:
    """Configuration for a navigation selection (bookies filter, period, ...)."""

    name: str
    container_selector: str
    active_class: str
    target_click_selector: Callable[[str], str]
    extract_active_value: Callable[[ElementHandle], Awaitable[str | None]]
    match_mode: Literal["attribute", "text"]
    attribute_name: str | None
    timeout_ms: int


class SelectionManager:
    """Ensure a navigation control is set to a target value.

    Replaces duplicate ensure_bookies_filter_selected / ensure_period_selected logic
    with a strategy-driven implementation. The wait_for_function predicate is invoked
    with a parameterized `arg=` payload, eliminating f-string-built JS.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    async def ensure_selected(
        self,
        page: Page,
        target_value: str,
        display_label: str,
        strategy: SelectionStrategy,
    ) -> bool:
        """Ensure the control described by `strategy` is set to `target_value`.

        Returns True on success, False on container missing, target missing, or verify failure.
        """
        try:
            self.logger.info(f"Ensuring {strategy.name} is set to: {display_label}")

            container = await page.query_selector(strategy.container_selector)
            if not container:
                self.logger.warning(f"{strategy.name} navigation not found on page. Skipping selection.")
                return False

            current_value = await self._get_current_value(page, strategy)
            if current_value:
                self.logger.info(f"Current {strategy.name}: {current_value}")
                if current_value == target_value:
                    self.logger.info(f"{strategy.name} already set to '{target_value}'. No action needed.")
                    return True

            click_selector = strategy.target_click_selector(target_value)
            self.logger.info(f"Clicking {strategy.name}: {display_label}")
            click_element = await page.query_selector(click_selector)
            if not click_element:
                self.logger.error(f"{strategy.name} target element not found for: {target_value}")
                return False
            await click_element.click()

            try:
                await page.wait_for_function(
                    _SELECTION_WAIT_PREDICATE,
                    arg={
                        "containerSelector": strategy.container_selector,
                        "activeClass": strategy.active_class,
                        "targetValue": target_value,
                        "matchMode": strategy.match_mode,
                        "attributeName": strategy.attribute_name,
                    },
                    timeout=strategy.timeout_ms,
                )
                self.logger.info(f"Successfully set {strategy.name} to: {display_label}")
                return True

            except Exception as wait_error:
                self.logger.warning(f"Wait condition failed: {wait_error}. Verifying selection...")
                await page.wait_for_timeout(FALLBACK_VERIFY_WAIT_MS)
                new_value = await self._get_current_value(page, strategy)
                if new_value == target_value:
                    self.logger.info(f"{strategy.name} successfully set to: {target_value}")
                    return True
                self.logger.error(f"Failed to set {strategy.name} to: {target_value}")
                return False

        except Exception as e:
            self.logger.error(f"Error setting {strategy.name}: {e}")
            return False

    async def _get_current_value(self, page: Page, strategy: SelectionStrategy) -> str | None:
        try:
            active_selector = f"{strategy.container_selector} .{strategy.active_class}"
            active_element = await page.query_selector(active_selector)
            if active_element:
                return await strategy.extract_active_value(active_element)
            self.logger.warning(f"No active {strategy.name} found")
            return None
        except Exception as e:
            self.logger.error(f"Error getting current {strategy.name}: {e}")
            return None


class PeriodSelector:
    """Select a match period by its language-independent URL-fragment scope code.

    The active period is encoded in the fragment as `;<scope>` (e.g.
    `…:over-under;2`). Scope ids are global and identical across localized mirrors
    (gotchas §7), so we select by clicking period tabs and reading the resulting
    scope rather than matching the localized tab label. Returns None when no scope
    code is verified for `(sport, period)`, signalling the caller to fall back to
    label-based selection.
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

        tabs = await page.query_selector_all(OddsPortalSelectors.PERIOD_TAB_SELECTOR)
        for i in range(len(tabs)):
            tabs = await page.query_selector_all(OddsPortalSelectors.PERIOD_TAB_SELECTOR)
            if i >= len(tabs):
                break
            try:
                await tabs[i].click()
                await page.wait_for_timeout(MARKET_SWITCH_WAIT_TIME_MS)
            except Exception as e:
                self.logger.debug(f"Period tab click failed at index {i}: {e}")
                continue
            if OddsPortalSelectors.period_scope_from_url(page.url) == target:
                self.logger.info(f"Selected period scope {target} for '{internal_period}' (tab index {i}).")
                return True

        self.logger.warning(f"Could not reach period scope {target} for '{internal_period}' via tab scan.")
        return False


# === Concrete strategies ===


async def _extract_data_testid(elem: ElementHandle) -> str | None:
    return await elem.get_attribute("data-testid")


async def _extract_text_content(elem: ElementHandle) -> str | None:
    text = await elem.text_content()
    return text.strip() if text else None


BOOKIES_FILTER_STRATEGY = SelectionStrategy(
    name="bookies-filter",
    container_selector=OddsPortalSelectors.BOOKIES_FILTER_CONTAINER,
    active_class=OddsPortalSelectors.BOOKIES_FILTER_ACTIVE_CLASS,
    target_click_selector=lambda v: OddsPortalSelectors.get_bookies_filter_selector(v),
    extract_active_value=_extract_data_testid,
    match_mode="attribute",
    attribute_name="data-testid",
    timeout_ms=BOOKIES_FILTER_TIMEOUT_MS,
)

PERIOD_STRATEGY = SelectionStrategy(
    name="period",
    container_selector=OddsPortalSelectors.PERIOD_SELECTOR_CONTAINER,
    active_class=OddsPortalSelectors.PERIOD_ACTIVE_CLASS,
    target_click_selector=lambda v: f"{OddsPortalSelectors.PERIOD_SELECTOR_CONTAINER} div:has-text('{v}')",
    extract_active_value=_extract_text_content,
    match_mode="text",
    attribute_name=None,
    timeout_ms=PERIOD_SELECTOR_TIMEOUT_MS,
)
