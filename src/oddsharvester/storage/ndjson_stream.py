import json
import logging
import sys
from typing import Any, TextIO


class NdjsonStreamWriter:
    """Writes one JSON line per scraped match, flushed as soon as it is produced."""

    def __init__(self, stream: TextIO | None = None):
        """
        Args:
            stream (TextIO | None): Destination for the NDJSON lines. Defaults to stdout.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.stream = stream if stream is not None else sys.stdout
        self._emitted_links: set[str] = set()
        self._disabled = False

    def emit(self, record: dict[str, Any]) -> None:
        """Write one record, skipping internal sentinels and matches already streamed."""
        if self._disabled or record.get("_live_ended"):
            return

        match_link = record.get("match_link")

        if match_link is not None:
            # A transient failure retries the whole scrape operation, replaying
            # matches that were already streamed.
            if match_link in self._emitted_links:
                return
            self._emitted_links.add(match_link)

        try:
            self.stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            self.stream.flush()

        except Exception as e:
            # A consumer that walked away must not bring down the run in progress.
            self._disabled = True
            self.logger.warning(f"NDJSON stream unavailable, stopping emission: {e}")
