import click
import pytest

from oddsharvester.cli.validators import validate_base_url


def test_none_is_valid():
    assert validate_base_url(None, None, None) is None


def test_empty_is_valid():
    assert validate_base_url(None, None, "") is None


def test_valid_https_host_only():
    assert validate_base_url(None, None, "https://www.centroquote.it") == "https://www.centroquote.it"


def test_valid_http_host_only():
    assert validate_base_url(None, None, "http://mirror.example.com") == "http://mirror.example.com"


def test_strips_trailing_slash():
    assert validate_base_url(None, None, "https://www.centroquote.it/") == "https://www.centroquote.it"


def test_missing_scheme_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "www.centroquote.it")


def test_non_http_scheme_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "ftp://www.centroquote.it")


def test_url_with_path_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "https://www.centroquote.it/football")


def test_url_with_query_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "https://www.centroquote.it?x=1")


def test_empty_host_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "https://")


def test_url_with_fragment_rejected():
    with pytest.raises(click.BadParameter):
        validate_base_url(None, None, "https://www.centroquote.it#section")


def test_valid_host_with_port():
    assert validate_base_url(None, None, "https://www.centroquote.it:8080") == "https://www.centroquote.it:8080"
