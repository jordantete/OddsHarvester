import click
import pytest

from oddsharvester.cli.validators import validate_seasons


def test_accepts_list_of_valid_seasons():
    assert validate_seasons(None, None, ["2020", "2021-2022"]) == ["2020", "2021-2022"]


def test_preserves_input_order():
    assert validate_seasons(None, None, ["2022-2023", "2020-2021"]) == ["2022-2023", "2020-2021"]


def test_deduplicates_preserving_first_seen_order():
    assert validate_seasons(None, None, ["2020", "2021", "2020"]) == ["2020", "2021"]


def test_accepts_current_mixed_with_explicit_seasons():
    assert validate_seasons(None, None, ["2021-2022", "current"]) == ["2021-2022", "current"]


def test_accepts_single_season():
    assert validate_seasons(None, None, ["2022-2023"]) == ["2022-2023"]


def test_raises_for_empty_value():
    with pytest.raises(click.BadParameter, match="At least one season must be provided"):
        validate_seasons(None, None, None)
    with pytest.raises(click.BadParameter, match="At least one season must be provided"):
        validate_seasons(None, None, [])


def test_rejects_invalid_format_with_existing_message():
    with pytest.raises(click.BadParameter, match="Invalid season format"):
        validate_seasons(None, None, ["2020", "invalid"])


def test_rejects_non_consecutive_range_with_existing_message():
    with pytest.raises(click.BadParameter, match="Second year must be exactly one year after the first"):
        validate_seasons(None, None, ["2020-2025"])
