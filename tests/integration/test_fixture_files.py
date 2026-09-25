"""Tests for the fixture-file guards of the integration suite."""

import pytest

from tests.integration.helpers.fixture_files import har_path_for, require_file

pytestmark = pytest.mark.integration


def test_require_file_returns_existing_path(tmp_path):
    path = tmp_path / "fixture.json"
    path.write_text("[]")
    assert require_file(path) == path


def test_require_file_fails_on_missing_path(tmp_path):
    with pytest.raises(pytest.fail.Exception, match="missing"):
        require_file(tmp_path / "gone.json")


def test_har_path_for_returns_sibling_har(tmp_path):
    har = tmp_path / "1x2_full_time_all.har"
    har.write_text("{}")
    assert har_path_for(tmp_path / "1x2_full_time_all.json", live=False) == har


def test_har_path_for_fails_when_har_missing(tmp_path):
    with pytest.raises(pytest.fail.Exception, match="missing"):
        har_path_for(tmp_path / "1x2_full_time_all.json", live=False)


def test_har_path_for_is_none_under_live_even_without_har(tmp_path):
    assert har_path_for(tmp_path / "1x2_full_time_all.json", live=True) is None
