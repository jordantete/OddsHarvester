"""The README documents every option, variable and command the CLI declares, and nothing it does not."""

from pathlib import Path
import re

import click

from oddsharvester.cli.cli import cli

README = Path(__file__).resolve().parents[2] / "README.md"
REFERENCE = "### CLI Options Reference"
VARIABLES = "## Environment Variables"
# Read from os.environ in storage/remote_data_storage.py; no option declares them.
NON_OPTION_VARIABLES = {"OH_S3_BUCKET", "OH_AWS_REGION"}


def _section(heading: str) -> list[str]:
    """The README lines under `heading`, up to the next heading of the same or a higher level outside code blocks."""
    lines = README.read_text(encoding="utf-8").splitlines()
    start = lines.index(heading) + 1
    level = len(heading.split(" ")[0])
    in_code = False
    for end in range(start, len(lines)):
        in_code ^= lines[end].startswith("```")
        if not in_code and re.match(rf"#{{1,{level}}} ", lines[end]):
            return lines[start:end]
    return lines[start:]


def _cells(line: str) -> list[str]:
    """The cells of a table line; an escaped pipe (`\\|`) stays inside its cell, as GitHub renders it."""
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip())[1:-1]]


def _tables(lines: list[str]) -> list[list[dict[str, str]]]:
    """Each markdown table of `lines`, as its rows mapping the header's cells to the row's cells."""
    tables, block = [], []
    for line in [*lines, ""]:
        if line.startswith("|"):
            block.append(line)
        elif block:
            header, _separator, *body = block
            names = _cells(header)
            for row in body:
                assert len(_cells(row)) == len(names), f"{len(_cells(row))} cells under {len(names)} headers: {row}"
            tables.append([dict(zip(names, _cells(row), strict=True)) for row in body])
            block = []
    return tables


def _code(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def _option_rows() -> dict[str, dict[str, str]]:
    """The rows of the reference's option tables, by the first name of their Option cell."""
    rows = {}
    for table in _tables(_section(REFERENCE)):
        for row in table:
            if "Option" in row:
                name = _code(row["Option"])[0]
                assert name not in rows, f"{name} has two rows"
                rows[name] = row
    return rows


def _declared() -> list[tuple[str | None, click.Option]]:
    """Every visible option with the command that takes it; the group's own options come with None."""
    pairs = [(None, param) for param in cli.params]
    pairs += [(name, param) for name, command in cli.commands.items() for param in command.params]
    return [(name, param) for name, param in pairs if isinstance(param, click.Option) and not param.hidden]


def _long(option: click.Option) -> str:
    return next(name for name in option.opts if name.startswith("--"))


def test_each_option_has_one_row_giving_its_short_name_and_the_commands_that_take_it():
    expected: dict[str, tuple[set[str], set[str]]] = {}
    for command, option in _declared():
        commands, short = expected.setdefault(_long(option), (set(), set()))
        if command:
            commands.add(command)
        short.update(name for name in option.opts if not name.startswith("--"))

    documented = {}
    for name, row in _option_rows().items():
        commands = set(re.findall(r"[a-z]+", row.get("Commands", "")))
        documented[name] = (set(cli.commands) if commands == {"all"} else commands, set(_code(row.get("Short", ""))))

    assert documented == expected


def test_a_second_flag_name_that_is_not_the_no_form_is_named_in_the_reference():
    reference = "\n".join(_section(REFERENCE))
    for _, option in _declared():
        for name in option.secondary_opts:
            if name != f"--no-{_long(option)[2:]}":
                assert f"`{name}`" in reference, name


def test_a_required_option_names_on_its_row_exactly_the_commands_that_require_it():
    """`_required_ on <commands>` for Click's required options; `_required_ with ...` is a validator's rule."""
    expected: dict[str, set[str]] = {}
    for command, option in _declared():
        if option.required:
            expected.setdefault(_long(option), set()).add(command)

    documented = {}
    for name, row in _option_rows().items():
        required_on = re.search(r"required_? on (.+)", row.get("Default", ""))
        if required_on:
            documented[name] = set(re.findall(r"[a-z]+", required_on.group(1))) & set(cli.commands)

    assert documented == expected


def test_the_global_options_table_holds_the_group_s_own_options():
    [table] = _tables(_section("#### Global Options"))
    group = {_long(param) for param in cli.params if isinstance(param, click.Option) and not param.hidden}

    assert {_code(row["Option"])[0] for row in table} == group


def test_each_variable_sits_on_the_row_of_its_option():
    expected = {option.envvar: _long(option) for _, option in _declared() if option.envvar}
    expected.update(dict.fromkeys(NON_OPTION_VARIABLES, "none"))

    [table] = _tables(_section(VARIABLES))
    rows = [(_code(row["Variable"])[0], (_code(row["CLI Option"]) or [row["CLI Option"]])[0]) for row in table]

    assert len(rows) == len(dict(rows)), "a variable has two rows"
    assert dict(rows) == expected


def test_each_command_is_named_in_the_usage_intro_and_has_its_own_section():
    usage = _section("## CLI Usage")
    intro = next(line for line in usage if line.strip())
    assert set(re.findall(r"\*\*`(\w+)`\*\*", intro)) == set(cli.commands)
    for name in cli.commands:
        assert f"### `oddsharvester {name}`" in usage, name


def test_no_option_or_variable_table_sits_outside_the_checked_sections():
    def headers(lines: list[str]) -> list[str]:
        return [line for line in lines if re.match(r"\|\s*(Option|Variable)\s*\|", line)]

    checked = headers(_section(REFERENCE)) + headers(_section(VARIABLES))
    assert headers(README.read_text(encoding="utf-8").splitlines()) == checked


def test_no_table_outside_the_checked_sections_keys_a_row_on_an_option_or_a_variable():
    names = {name for _, option in _declared() for name in option.opts} | {
        option.envvar for _, option in _declared() if option.envvar
    }
    checked = set(_section(REFERENCE)) | set(_section(VARIABLES))
    outside = [
        line
        for line in README.read_text(encoding="utf-8").splitlines()
        if line.startswith("|") and line not in checked and set(_code(_cells(line)[0])) & names
    ]

    assert outside == []
