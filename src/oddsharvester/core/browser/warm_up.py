"""The per-context warm-up of a page: the cookie banner, then the odds format (gotchas §11)."""

from collections.abc import Awaitable, Callable
import logging
from urllib.parse import urlsplit

from playwright.async_api import Page, TimeoutError

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.browser.waits import wait_for_element, wait_for_signal
from oddsharvester.utils.constants import ODDS_FORMAT_SELECTOR_TIMEOUT_MS, ODDS_FORMAT_WAIT_MS, ODDSPORTAL_BASE_URL
from oddsharvester.utils.odds_format_enum import OddsFormat

# The odds format button (the first button whose text holds 'Odds') reads the label.
_ODDS_FORMAT_SHOWN_JS = """
(label) => {
    const button = Array.from(document.querySelectorAll("button")).find((b) => /odds/i.test(b.textContent || ""));
    return !!button && button.innerText.trim() === label;
}
"""


async def set_odds_format(
    page: Page, logger: logging.Logger, odds_format: OddsFormat = OddsFormat.DECIMAL_ODDS, strict: bool = False
) -> None:
    """
    Sets the odds format on the page.

    Args:
        page (Page): The Playwright page instance.
        logger (logging.Logger): The scraper's logger, whose name the log lines carry.
        odds_format (OddsFormat): The desired odds format.
        strict (bool): Raise instead of logging when the format cannot be set: a timeout, any other
            error, or the format missing from the dropdown. Only the proxy warm-up sets it.
    """
    try:
        logger.info(f"Setting odds format: {odds_format.value}")
        # Text-based selector: OddsPortal's React build periodically reshuffles
        # Tailwind utility classes on this control (issue #68: the old
        # `div.group > button.gap-2` stopped matching when it became
        # `button.flex gap-3`). The button label is always the current odds
        # format ("Decimal Odds", "Fractional Odds", ...), so matching on the
        # "Odds" text survives class refactors. Verified live 2026-05-15.
        button_selector = "button:has-text('Odds')"
        await page.wait_for_selector(button_selector, state="attached", timeout=ODDS_FORMAT_SELECTOR_TIMEOUT_MS)
        dropdown_button = await page.query_selector(button_selector)

        # Check if the desired format is already selected
        current_format = await dropdown_button.inner_text()
        logger.info(f"Current odds format detected: {current_format}")

        if current_format == odds_format.value:
            logger.info(f"Odds format is already set to '{odds_format.value}'. Skipping.")
            return

        await dropdown_button.click()
        format_option_selector = "div.group > div.dropdown-content > ul > li > a"
        await wait_for_element(page, format_option_selector, ODDS_FORMAT_WAIT_MS, "odds format options")
        format_options = await page.query_selector_all(format_option_selector)

        for option in format_options:
            option_text = await option.inner_text()

            if odds_format.value.lower() in option_text.lower():
                logger.info(f"Selecting odds format: {option_text}")
                await option.click()
                await wait_for_signal(
                    page,
                    _ODDS_FORMAT_SHOWN_JS,
                    ODDS_FORMAT_WAIT_MS,
                    f"'{odds_format.value}' on the odds format button",
                    arg=odds_format.value,
                )
                logger.info(f"Odds format changed to '{odds_format.value}'.")
                return

        if strict:
            raise ValueError(f"Desired odds format '{odds_format.value}' not found in dropdown options.")
        logger.warning(f"Desired odds format '{odds_format.value}' not found in dropdown options.")

    except TimeoutError:
        if strict:
            raise
        logger.error("Timeout while setting odds format. Dropdown may not have loaded.")

    except Exception as e:
        if strict:
            raise
        logger.error(f"Error while setting odds format: {e}", exc_info=True)


async def warm_up_page(
    page: Page,
    cookie_dismisser: CookieDismisser,
    odds_format_setter: Callable[..., Awaitable[None]],
    base_url: str | None,
    home_timeout_ms: int | None = None,
    strict_on_canonical_host: bool = False,
) -> None:
    """Accept the cookie banner, then set decimal odds; both are per-context state (gotchas §11).

    Args:
        page (Page): The page to warm up, already on an OddsPortal page unless `home_timeout_ms` is given.
        cookie_dismisser (CookieDismisser): Accepts the cookie banner.
        odds_format_setter: Sets the odds format, called as `odds_format_setter(page=page, strict=strict)`.
        base_url (str | None): The run's `--base-url`, None for www.oddsportal.com.
        home_timeout_ms (int | None): Load the run's home page first (`--base-url`, else www.oddsportal.com),
            within this timeout.
        strict_on_canonical_host (bool): Raise when the odds format cannot be set on a page that landed on
            www.oddsportal.com. A proxy can be geo-redirected to a localized mirror even when the canonical
            domain was requested, and a mirror's localized labels defeat the English match (gotchas §7), so
            strictness follows the page's actual host.
    """
    if home_timeout_ms is not None:
        await page.goto(base_url or ODDSPORTAL_BASE_URL, timeout=home_timeout_ms, wait_until="domcontentloaded")
    await cookie_dismisser.dismiss(page=page)
    strict = strict_on_canonical_host and urlsplit(page.url).hostname == urlsplit(ODDSPORTAL_BASE_URL).hostname
    await odds_format_setter(page=page, strict=strict)
