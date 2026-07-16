"""One-off helper: capture the rendered Community Top Predictions page as an HTML fixture.

Usage:
    uv run python scripts/capture_top_predictions_fixture.py \
        [--sport football] [--out tests/data/community/top_predictions_football.html]

Re-run when OddsPortal changes the predictions page structure (parser tests will start failing).
"""

import argparse
import asyncio
from pathlib import Path

from oddsharvester.core.browser.cookies import CookieDismisser
from oddsharvester.core.playwright_manager import PlaywrightManager
from oddsharvester.utils.constants import ODDSPORTAL_BASE_URL, SELECTOR_TIMEOUT_MS


async def capture(sport: str, out_path: Path) -> None:
    manager = PlaywrightManager()
    try:
        await manager.initialize(headless=True)
        page = manager.page
        await page.goto(f"{ODDSPORTAL_BASE_URL}/predictions/#sport/{sport}/", wait_until="domcontentloaded")
        await CookieDismisser().dismiss(page)
        await page.wait_for_selector('[data-testid="game-row"]', timeout=SELECTOR_TIMEOUT_MS)
        html = await page.content()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        print(f"Saved {len(html)} chars to {out_path}")
    finally:
        await manager.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sport", default="football")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    out = Path(args.out) if args.out else Path("tests/data/community") / f"top_predictions_{args.sport}.html"
    asyncio.run(capture(args.sport, out))
