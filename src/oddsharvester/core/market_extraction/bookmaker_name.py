"""Resolve a bookmaker's name from the sources an odds row offers."""

import logging
import re

logger = logging.getLogger(__name__)

# By the slug of their /proxy/bookmakers/<slug>/ link, so a row that shows only its logo keeps its usual name.
BOOKMAKER_NAME_BY_SLUG = {
    "betclic-fr": "Betclic.fr",
    "bets-io": "Bets.io",
    "bwin-fr": "bwin.fr",
    "roobet": "Roobet",
    "stake-com": "Stake.com",
    "unibet-fr": "Unibet.fr",
    "winamax": "Winamax",
}

_SLUG_RE = re.compile(r"/bookmakers/([^/?#]+)")


def resolve_bookmaker_name(visible_text: str | None, title: str | None, link_href: str | None = None) -> str | None:
    """Name shown next to the logo, else the logo link title with its call-to-action wording removed, else the
    name of the logo link's slug (the slug itself when it is not a known one)."""
    name = (visible_text or "").strip()
    if name:
        return name
    title = (title or "").strip()
    if title:
        if title.lower().startswith("go to ") and title.endswith("!"):
            title = title[len("go to ") : -1].strip()
            if title.lower().endswith(" website"):
                title = title[: -len(" website")].strip()
        return title
    match = _SLUG_RE.search(link_href or "")
    if match is None:
        return None
    slug = match.group(1)
    if slug not in BOOKMAKER_NAME_BY_SLUG:
        logger.warning(f"A bookmaker row shows only its logo and its link slug '{slug}' is not a known name; using it.")
    return BOOKMAKER_NAME_BY_SLUG.get(slug, slug)


def bookmaker_match_key(name: str) -> str:
    """Comparison key for bookmaker names read by different DOM APIs."""
    # BeautifulSoup's get_text(strip=True) drops the spaces between nested text nodes; Playwright keeps them.
    return "".join(name.split()).casefold()
