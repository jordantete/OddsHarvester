## Problem

When running OddsHarvester in headless mode on a server/Docker environment, OddsPortal returns empty pages with 0 event rows found. The scraper successfully loads the page but cannot find any matches.

**Symptoms:**

- `Found 0 event rows` in logs
- `Extracted 0 unique match links`
- Pages load but content appears empty
- Same configuration works locally with `headless=False`

## Root Cause

OddsPortal uses browser fingerprinting to detect automated/headless browsers:

1. Checks `navigator.webdriver` property
2. Analyzes browser arguments for automation flags
3. Inspects user agent strings

The critical flag `--disable-blink-features=AutomationControlled` was present in `PLAYWRIGHT_BROWSER_ARGS` (used locally) but **missing** from `PLAYWRIGHT_BROWSER_ARGS_DOCKER` (used in server/Docker environments).

## Solution

### 1. Browser Args Fix (constants.py)

Added missing anti-detection flags to `PLAYWRIGHT_BROWSER_ARGS_DOCKER`:

- `--disable-blink-features=AutomationControlled` - Prevents detection via automation APIs
- `--disable-features=IsolateOrigins,site-per-process` - Additional fingerprint protection
- `--mute-audio` and `--window-size=1280,720` - Consistency with non-Docker args

### 2. Stealth Script (playwright_manager.py)

Added JavaScript injection to hide automation signatures:

- `navigator.webdriver` returns `undefined` instead of `true`
- Fake `window.chrome.runtime` object
- Realistic `navigator.plugins` and `navigator.languages`

### 3. User Agent Rotation

Added pool of realistic Chrome user agents to avoid fingerprinting based on default Playwright user agent.

## Testing

| Scenario              | Before | After                                |
| --------------------- | ------ | ------------------------------------ |
| Event rows found      | 0      | 50 per page                          |
| Match links extracted | 0      | 380 (full season)                    |
| Odds parsed           | None   | Successfully for multiple bookmakers |

Tested on Debian 12 server with Python 3.14 and Playwright 1.50 in headless mode.
