#!/usr/bin/env python3
import asyncio

from playwright.async_api import async_playwright


async def check_page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(
            "https://www.oddsportal.com/football/czech-republic/chance-liga-2023-2024/results/"
        )
        await asyncio.sleep(5)

        # Check page content
        content = await page.content()
        print("Page length:", len(content))

        # Check for event rows with different selectors
        selectors = [
            "div.eventRow",
            '[class*="eventRow"]',
            'div[class*="event"]',
            'a[href*="/football/czech-republic/"]',
            "div.flex.flex-col",
            "div[data-testid]",
        ]

        for sel in selectors:
            count = await page.locator(sel).count()
            print(f"{sel}: {count}")

        # Get page title
        title = await page.title()
        print(f"Title: {title}")

        # Check if there's a no results message
        no_results = await page.locator('text="No data"').count()
        print(f"No data message: {no_results}")

        # Save screenshot
        await page.screenshot(path="/tmp/czech_page.png")
        print("Screenshot saved to /tmp/czech_page.png")

        await browser.close()


asyncio.run(check_page())
