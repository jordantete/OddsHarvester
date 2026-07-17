from oddsharvester.core.community.row_helpers import to_float, to_pct


def test_to_float_parses_valid_and_rejects_garbage():
    assert to_float("2.05") == 2.05
    assert to_float("-") is None


def test_to_pct_extracts_integer_percent():
    assert to_pct("87%") == 87
    assert to_pct("no pct") == 0
