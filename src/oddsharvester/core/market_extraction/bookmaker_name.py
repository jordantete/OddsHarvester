"""Resolve a bookmaker's name from the two sources an odds row offers."""


def resolve_bookmaker_name(visible_text: str | None, title: str | None) -> str | None:
    """Name shown next to the logo, else the logo link title with its call-to-action wording removed."""
    name = (visible_text or "").strip()
    if name:
        return name
    title = (title or "").strip()
    if not title:
        return None
    if title.lower().startswith("go to ") and title.endswith("!"):
        title = title[len("go to ") : -1].strip()
        if title.lower().endswith(" website"):
            title = title[: -len(" website")].strip()
    return title


def bookmaker_match_key(name: str) -> str:
    """Comparison key for bookmaker names read by different DOM APIs."""
    # BeautifulSoup's get_text(strip=True) drops the spaces between nested text nodes; Playwright keeps them.
    return "".join(name.split()).casefold()
