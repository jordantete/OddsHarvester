"""Capped waits on what the page does.

Each wait returns as soon as its signal shows, or at its cap, which is the fixed sleep it replaced; at the cap it
logs a warning and the caller carries on with the page as it is, as it did after the sleep.
"""

import logging
from typing import Any

from playwright.async_api import JSHandle, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Interval polling keeps working in a background tab, where animation frames stop.
SIGNAL_POLL_MS = 50


async def wait_for_signal(page: Page, expression: str, cap_ms: int, signal: str, arg: Any = None) -> JSHandle | None:
    """Poll the JS `expression` until it returns a truthy value, at most `cap_ms`.

    Returns the handle of that value, or None after a warning naming `signal` when the cap is reached.
    """
    try:
        return await page.wait_for_function(expression, arg=arg, timeout=cap_ms, polling=SIGNAL_POLL_MS)
    except PlaywrightTimeoutError:
        logger.warning(f"No {signal} within {cap_ms} ms; carrying on with the page as it is.")
        return None


async def wait_for_element(page: Page, selector: str, cap_ms: int, signal: str, state: str = "visible") -> bool:
    """Wait until the first element matching `selector` is in `state`, at most `cap_ms`.

    Returns False after a warning naming `signal` when the cap is reached.
    """
    try:
        await page.wait_for_selector(selector, state=state, timeout=cap_ms)
        return True
    except PlaywrightTimeoutError:
        logger.warning(f"No {signal} within {cap_ms} ms; carrying on with the page as it is.")
        return False
