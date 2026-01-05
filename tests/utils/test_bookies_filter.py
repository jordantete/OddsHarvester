import pytest

from src.utils.bookies_filter_enum import BookiesFilter


class TestBookiesFilter:
    """Test cases for BookiesFilter enum."""

    def test_bookies_filter_values(self):
        """Test that BookiesFilter enum has the correct values."""
        assert BookiesFilter.ALL.value == "all"
        assert BookiesFilter.CLASSIC.value == "classic"
        assert BookiesFilter.CRYPTO.value == "crypto"

    def test_bookies_filter_from_string(self):
        """Test creating BookiesFilter enum from string values."""
        assert BookiesFilter("all") == BookiesFilter.ALL
        assert BookiesFilter("classic") == BookiesFilter.CLASSIC
        assert BookiesFilter("crypto") == BookiesFilter.CRYPTO

    def test_bookies_filter_invalid_value(self):
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError):
            BookiesFilter("invalid")

    def test_enum_value_as_data_testid(self):
        """Test that enum values can be used directly as data-testid values."""
        assert BookiesFilter.ALL.value == "all"
        assert BookiesFilter.CLASSIC.value == "classic"
        assert BookiesFilter.CRYPTO.value == "crypto"

    def test_get_display_label(self):
        """Test get_display_label method returns correct display labels."""
        assert BookiesFilter.get_display_label(BookiesFilter.ALL) == "All Bookies"
        assert BookiesFilter.get_display_label(BookiesFilter.CLASSIC) == "Classic Bookies"
        assert BookiesFilter.get_display_label(BookiesFilter.CRYPTO) == "Crypto Bookies"

    def test_all_enum_members(self):
        """Test that all enum members are accounted for."""
        expected_members = {"ALL", "CLASSIC", "CRYPTO"}
        actual_members = {member.name for member in BookiesFilter}
        assert actual_members == expected_members

    def test_enum_equality(self):
        """Test enum equality comparisons."""
        assert BookiesFilter.ALL == BookiesFilter.ALL
        assert BookiesFilter.ALL != BookiesFilter.CLASSIC
        assert BookiesFilter.CLASSIC != BookiesFilter.CRYPTO
