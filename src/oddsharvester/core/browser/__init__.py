"""Browser interaction helpers for OddsPortal scraping.

One module per page concern:
- cookies: CookieDismisser dismisses the cookie consent banner
- hydration: hydrate_match_view brings a match page's hash-driven view on screen
- market_navigation: MarketTabNavigator and switch_view move the match view to a market tab
- pagination: PaginationWalker decides how far a listing walk goes when the pagination widget is unreliable
- scrolling: PageScroller does incremental scrolling and scroll-to-element-and-click
- selection: SelectionManager and PeriodSelector set a navigation control (bookies filter, period) to a target value
- session: browser_session and open_page give community and team runs their browser and page load;
  raise_if_rate_limited turns a 429 answer into RateLimitError
- view_data: what the data a match view rendered says about its market and period
- waits: capped waits on page signals
- warm_up: set_odds_format picks the odds format; warm_up_page accepts the cookie banner, then sets decimal odds
"""
