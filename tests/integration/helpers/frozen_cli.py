"""Run the oddsharvester CLI with the page clock frozen at an instant: `python -m ... <iso instant> <cli args>`.

A HAR replays the times as the site rendered them at capture, at the zone's offset of that moment (gotchas §10).
"""

from datetime import datetime
import sys
from unittest.mock import patch

from oddsharvester.cli.cli import main
from tests.clock import frozen_clock

if __name__ == "__main__":
    clock = frozen_clock(datetime.fromisoformat(sys.argv[1]))
    with (
        patch("oddsharvester.utils.page_time.datetime", clock),
        patch("oddsharvester.core.market_extraction.odds_parser.datetime", clock),
    ):
        sys.argv = ["oddsharvester", *sys.argv[2:]]
        main()
