from oddsharvester.core.community.row_helpers import to_float, to_pct


def test_to_float_parses_valid_and_rejects_garbage():
    assert to_float("2.05") == 2.05
    assert to_float("-") is None


def test_to_pct_extracts_integer_percent():
    assert to_pct("87%") == 87
    assert to_pct("no pct") == 0


def test_extract_datetime_handles_duplicated_responsive_date():
    """Redesign rows render the date twice (mobile + desktop variants):
    '20/Jun 12:10 20/Jun, 12:10 CS' must still yield a kickoff."""
    from bs4 import BeautifulSoup

    from oddsharvester.core.community.row_helpers import extract_datetime_and_market

    html = """
    <div data-testid="game-row">
      <div data-testid="date-time-item"><p>20/Jun</p><p>12:10</p><p>20/Jun, 12:10</p><p>CS</p></div>
    </div>
    """
    row = BeautifulSoup(html, "lxml").find(attrs={"data-testid": "game-row"})
    _kickoff_text, kickoff, market = extract_datetime_and_market(row, "UTC")
    assert market == "CS"
    assert kickoff is not None
    assert kickoff.endswith("T12:10")
    assert "-06-20" in kickoff
