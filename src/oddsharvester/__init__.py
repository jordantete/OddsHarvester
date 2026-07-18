"""OddsHarvester - A web scraper for sports betting odds from OddsPortal."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("oddsharvester")
except PackageNotFoundError:  # running from a source checkout without an installed distribution
    __version__ = "0.0.0"
