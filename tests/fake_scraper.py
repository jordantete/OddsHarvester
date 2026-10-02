"""A stand-in for OddsPortalScraper, for tests that run run_scraper or a CLI command without a browser."""

from typing import Any, ClassVar

from oddsharvester.core.odds_portal_scraper import ListingResult
from oddsharvester.core.scrape_result import ScrapeResult


def _empty_listing(**_: Any) -> ListingResult:
    return ListingResult()


def _empty_result(**_: Any) -> ScrapeResult:
    return ScrapeResult()


class FakeScraper:
    """Records every call a run makes, as (method, keywords), and answers it from `answers`.

    An answer is a value, an exception to raise, or a function called with the call's keywords. A method
    without an answer returns None for the browser lifecycle, an empty ListingResult for a listing and an
    empty ScrapeResult for a scrape. `build` replaces the OddsPortalScraper class: it keeps the keywords
    the run built the scraper with and returns this instance.
    """

    _DEFAULTS: ClassVar[dict[str, Any]] = {
        "collect_historic_links": _empty_listing,
        "collect_upcoming_links": _empty_listing,
        "scrape_live": _empty_result,
        "scrape_matches": _empty_result,
        "extract_match_odds": _empty_result,
    }

    def __init__(self) -> None:
        self.built_with: dict[str, Any] = {}
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.answers: dict[str, Any] = {}

    def build(self, **kwargs: Any) -> "FakeScraper":
        self.built_with = kwargs
        return self

    @property
    def preview_submarkets_only(self) -> bool:
        return self.built_with.get("preview_submarkets_only", False)

    def called(self, method: str) -> list[dict[str, Any]]:
        """The keywords of every call to `method`, in call order."""
        return [kwargs for name, kwargs in self.calls if name == method]

    def _answer(self, method: str, kwargs: dict[str, Any]) -> Any:
        self.calls.append((method, kwargs))
        answer = self.answers.get(method, self._DEFAULTS.get(method))
        if isinstance(answer, BaseException):
            raise answer
        return answer(**kwargs) if callable(answer) else answer

    async def start_playwright(self, **kwargs: Any) -> None:
        self._answer("start_playwright", kwargs)

    async def stop_playwright(self) -> None:
        self._answer("stop_playwright", {})

    async def scrape_live(self, **kwargs: Any) -> ScrapeResult:
        return self._answer("scrape_live", kwargs)

    async def scrape_matches(self, **kwargs: Any) -> ScrapeResult:
        return self._answer("scrape_matches", kwargs)

    async def collect_historic_links(self, **kwargs: Any) -> ListingResult:
        return self._answer("collect_historic_links", kwargs)

    async def collect_upcoming_links(self, **kwargs: Any) -> ListingResult:
        return self._answer("collect_upcoming_links", kwargs)

    async def extract_match_odds(self, **kwargs: Any) -> ScrapeResult:
        return self._answer("extract_match_odds", kwargs)
