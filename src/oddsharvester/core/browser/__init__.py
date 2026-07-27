"""Browser interaction helpers for OddsPortal scraping.

Each helper is independent and focused on one responsibility:
- CookieDismisser: dismiss the cookie consent banner
- SelectionManager: ensure a navigation control (filter, period) is set to a target value
- MarketTabNavigator: navigate to a market tab, including those hidden under "More"
- PageScroller: incremental scrolling and scroll-to-element-and-click
- PaginationWalker: decide how far a listing walk goes when the pagination widget is unreliable
"""
