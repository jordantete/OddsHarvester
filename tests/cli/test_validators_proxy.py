import click
import pytest

from oddsharvester.cli.validators import validate_proxy_url


def test_accepts_empty():
    assert validate_proxy_url(None, None, ()) == ()


def test_accepts_single_without_credentials():
    assert validate_proxy_url(None, None, ("http://proxy.example.com:8080",)) == ("http://proxy.example.com:8080",)


def test_accepts_embedded_credentials():
    value = ("http://user:pass@proxy.example.com:8080",)
    assert validate_proxy_url(None, None, value) == value


def test_accepts_multiple():
    value = ("http://a.example.com:1", "socks5://b.example.com:2")
    assert validate_proxy_url(None, None, value) == value


def test_rejects_bad_scheme():
    with pytest.raises(click.BadParameter):
        validate_proxy_url(None, None, ("ftp://proxy.example.com:8080",))


def test_rejects_missing_port():
    with pytest.raises(click.BadParameter):
        validate_proxy_url(None, None, ("http://proxy.example.com",))


@pytest.mark.parametrize("password", ["pa#s3cret", "pa?s3cret"])
def test_rejects_a_password_the_url_cannot_carry_without_echoing_it(password):
    with pytest.raises(click.BadParameter, match="--proxy-user and --proxy-pass") as excinfo:
        validate_proxy_url(None, None, (f"http://alice:{password}@p1.example:8080",))

    assert "s3cret" not in str(excinfo.value)
