"""_LINE_ROW_JS run in the bundled Chromium on pages set in place: no network, no HAR.

The JS reads the labels a person sees as OddsPortalSelectors.line_label_matches reads them; these tests keep the two
in step, and pin that a line row is clicked only once it is shown.
"""

from playwright.async_api import async_playwright
import pytest

from oddsharvester.core.browser.scrolling import _LINE_ROW_JS, PageScroller
from oddsharvester.core.odds_portal_selectors import OddsPortalSelectors

pytestmark = pytest.mark.integration

# Line rows as OddsPortal renders them (2026-09-29): the full label, the short label hidden on desktop, the bookmaker
# count. The sets row and the games row of a tennis Asian Handicap both read '+1.5'.
LABELS = ["Asian Handicap -1.75", "Asian Handicap -1", "Asian Handicap 0", "Asian Handicap +1.5", "Asian Handicap +1.5"]
COUNT = "3"
LINES = ["-1", "-1.75", "-2", "0", "+1.5", "1.5", COUNT, "Asian Handicap -1", "AH -1", ""]
BOOKMAKERS = '<tr><td><table><tr><td><a href="/bookmakers/bet365/">bet365</a></td></tr></table></td></tr>'


def _row(label: str, style: str = "") -> str:
    short = label.replace("Asian Handicap", "AH")
    return (
        f'<tr class="cursor-pointer" style="{style}" data-label="{label}" '
        'onclick="window.clicked = (window.clicked || []).concat([this.dataset.label])">'
        f'<td><span>{label}</span><span style="display:none">{short}</span><span>{COUNT}</span></td></tr>'
    )


def _args(line: str, want: str = "present") -> dict:
    return PageScroller._line_args(
        OddsPortalSelectors.SUB_MARKET_SELECTOR, line, OddsPortalSelectors.SUB_MARKET_CLICK_ANCESTOR, want
    )


@pytest.fixture
async def page():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        yield page
        await browser.close()


@pytest.mark.parametrize("line", LINES)
async def test_the_js_finds_a_line_exactly_where_line_label_matches_does(page, line):
    await page.set_content("<table>" + "".join(_row(label) for label in LABELS) + "</table>")
    shown = [text for label in LABELS for text in (label, COUNT)]

    found = await page.evaluate(_LINE_ROW_JS, _args(line))

    assert found is any(OddsPortalSelectors.line_label_matches(text, line) for text in shown)


@pytest.mark.parametrize(("line", "rows"), [("-1", 1), ("+1.5", 2), ("-2", 0)])
async def test_the_js_opens_only_a_line_one_row_holds(page, line, rows):
    """'open' needs exactly one row of the line, whose next row holds a bookmaker row."""
    await page.set_content("<table>" + "".join(_row(label) + BOOKMAKERS for label in LABELS) + "</table>")

    assert await page.evaluate(_LINE_ROW_JS, _args(line, "open")) is (rows == 1)


async def test_a_hidden_row_is_not_a_row_of_the_line(page):
    await page.set_content("<table>" + _row("Asian Handicap -1", style="display:none") + "</table>")

    assert await page.evaluate(_LINE_ROW_JS, _args("-1")) is False


async def test_a_line_row_shown_late_is_clicked_once_shown(page):
    """The row is in the table before it has a box: the click waits for the box instead of failing the market."""
    await page.set_content(
        "<table>"
        + _row("Asian Handicap -1.75")
        + _row("Asian Handicap -1", style="display:none")
        + "</table>"
        + "<script>setTimeout(() => { document.querySelectorAll('tr')[1].style.display = ''; }, 300);</script>"
    )

    clicked = await PageScroller().click_line_row(
        page, OddsPortalSelectors.SUB_MARKET_SELECTOR, "-1", OddsPortalSelectors.SUB_MARKET_CLICK_ANCESTOR, timeout=3
    )

    assert clicked is True
    assert await page.evaluate("window.clicked") == ["Asian Handicap -1"]
