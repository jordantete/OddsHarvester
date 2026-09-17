import io
import json
import sys

import pytest

from oddsharvester.storage.ndjson_stream import NdjsonStreamWriter


class FlushCountingStream(io.StringIO):
    """StringIO that records how many times flush() was called."""

    def __init__(self):
        super().__init__()
        self.flush_count = 0

    def flush(self):
        self.flush_count += 1
        super().flush()


class BrokenStream(io.StringIO):
    """Stream that fails on write, like a pipe whose consumer has exited."""

    def write(self, data):
        raise BrokenPipeError("consumer closed the pipe")


def test_emit_writes_one_flushed_json_line_per_record():
    stream = FlushCountingStream()
    writer = NdjsonStreamWriter(stream=stream)

    writer.emit({"match_link": "https://x/a", "home_team": "A"})
    writer.emit({"match_link": "https://x/b", "home_team": "B"})

    lines = stream.getvalue().splitlines()
    assert [json.loads(line) for line in lines] == [
        {"match_link": "https://x/a", "home_team": "A"},
        {"match_link": "https://x/b", "home_team": "B"},
    ]
    assert stream.flush_count == 2


def test_emit_preserves_non_ascii_characters():
    stream = FlushCountingStream()
    writer = NdjsonStreamWriter(stream=stream)

    writer.emit({"match_link": "https://x/a", "home_team": "Beşiktaş"})

    assert "Beşiktaş" in stream.getvalue()


def test_emit_serializes_unsupported_values_as_strings():
    from datetime import UTC, datetime

    stream = FlushCountingStream()
    writer = NdjsonStreamWriter(stream=stream)

    writer.emit({"match_link": "https://x/a", "scraped_at": datetime(2026, 9, 17, tzinfo=UTC)})

    assert json.loads(stream.getvalue())["scraped_at"] == "2026-09-17 00:00:00+00:00"


def test_emit_deduplicates_on_match_link():
    """A whole-run retry replays matches already emitted; consumers must not see them twice."""
    stream = FlushCountingStream()
    writer = NdjsonStreamWriter(stream=stream)

    writer.emit({"match_link": "https://x/a", "attempt": 1})
    writer.emit({"match_link": "https://x/a", "attempt": 2})

    assert len(stream.getvalue().splitlines()) == 1
    assert json.loads(stream.getvalue())["attempt"] == 1


def test_emit_keeps_records_without_match_link():
    stream = FlushCountingStream()
    writer = NdjsonStreamWriter(stream=stream)

    writer.emit({"home_team": "A"})
    writer.emit({"home_team": "B"})

    assert len(stream.getvalue().splitlines()) == 2


def test_emit_skips_live_ended_sentinel():
    """The ended-match sentinel is internal and is filtered out of the batch output too."""
    stream = FlushCountingStream()
    writer = NdjsonStreamWriter(stream=stream)

    writer.emit({"_live_ended": True, "match_link": "https://x/a"})

    assert stream.getvalue() == ""


def test_emit_survives_a_closed_consumer_and_stops_streaming(caplog):
    writer = NdjsonStreamWriter(stream=BrokenStream())

    with caplog.at_level("WARNING"):
        writer.emit({"match_link": "https://x/a"})
        writer.emit({"match_link": "https://x/b"})

    assert len(caplog.records) == 1, "the stream failure must be reported once, not per record"


def test_writer_defaults_to_stdout():
    assert NdjsonStreamWriter().stream is sys.stdout


@pytest.mark.parametrize("record", [{"a": 1}, {"match_link": "https://x/a"}])
def test_emit_never_raises_on_a_broken_stream(record):
    writer = NdjsonStreamWriter(stream=BrokenStream())

    writer.emit(record)
