"""Every command declares the output and browser options from one place, the scrape commands' own."""

import pytest

from oddsharvester.cli.cli import cli

SHARED = (
    "storage",
    "storage_format",
    "file_path",
    "append",
    "headless",
    "proxy_url",
    "proxy_user",
    "proxy_pass",
    "browser_user_agent",
    "browser_locale_timezone",
    "browser_timezone_id",
    "base_url",
)


def _declaration(command: str, name: str) -> tuple:
    [param] = [param for param in cli.commands[command].params if param.name == name]
    return (
        param.opts,
        param.secondary_opts,
        param.envvar,
        param.default,
        param.multiple,
        param.type.name,
        param.callback,
        param.help,
    )


@pytest.mark.parametrize("command", ["historic", "live", "community", "team"])
def test_each_command_declares_the_shared_options_as_upcoming_does(command):
    assert [_declaration(command, name) for name in SHARED] == [_declaration("upcoming", name) for name in SHARED]
