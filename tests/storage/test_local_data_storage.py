import csv
import errno
import json
import os
import stat
from unittest.mock import patch

import pytest

from oddsharvester.storage.local_data_storage import LocalDataStorage
from oddsharvester.storage.storage_format import StorageFormat


@pytest.fixture
def local_data_storage():
    return LocalDataStorage(default_file_path="test_data", default_storage_format=StorageFormat.CSV)


@pytest.fixture
def sample_data():
    return [{"team": "Team A", "odds": 2.5}, {"team": "Team B", "odds": 1.8}]


def test_initialization(local_data_storage):
    assert local_data_storage.default_file_path == "test_data"
    assert local_data_storage.default_storage_format == StorageFormat.CSV


def test_save_data_invalid_format(local_data_storage):
    with pytest.raises(ValueError, match=r"Data must be a dictionary or a list of dictionaries\."):
        local_data_storage.save_data("invalid_data")


def test_save_data_dict_conversion(local_data_storage):
    data = {"team": "Team A", "odds": 2.5}

    with patch.object(local_data_storage, "_save_as_csv") as mock_save:
        local_data_storage.save_data(data, file_path="test.csv", storage_format="csv")

        # Verify that data was converted to list
        mock_save.assert_called_once()
        called_data = mock_save.call_args[0][0]
        assert isinstance(called_data, list)
        assert len(called_data) == 1
        assert called_data[0] == data


def test_save_data_with_file_extension_handling(local_data_storage, sample_data):
    with patch.object(local_data_storage, "_save_as_csv") as mock_save:
        local_data_storage.save_data(sample_data, file_path="test", storage_format="csv")

        # Verify that .csv extension was added
        mock_save.assert_called_once_with(sample_data, "test.csv", append=False)


def test_save_data_with_existing_extension(local_data_storage, sample_data):
    with patch.object(local_data_storage, "_save_as_csv") as mock_save:
        local_data_storage.save_data(sample_data, file_path="test.csv", storage_format="csv")

        # Verify that extension wasn't duplicated
        mock_save.assert_called_once_with(sample_data, "test.csv", append=False)


def test_save_data_propagates_append(local_data_storage, sample_data):
    """append=True must reach the format-specific writer."""
    with patch.object(local_data_storage, "_save_as_json") as mock_save:
        local_data_storage.save_data(sample_data, file_path="test.json", storage_format="json", append=True)

        mock_save.assert_called_once_with(sample_data, "test.json", append=True)


@pytest.mark.parametrize(
    ("file_path", "storage_format", "written"),
    [("out", "csv", "out.csv"), ("out.json", "json", "out.json"), (None, "json", "test_data.json")],
)
def test_save_data_returns_the_path_it_wrote(
    local_data_storage, sample_data, tmp_path, monkeypatch, file_path, storage_format, written
):
    monkeypatch.chdir(tmp_path)

    assert local_data_storage.save_data(sample_data, file_path=file_path, storage_format=storage_format) == written
    assert (tmp_path / written).exists()


def test_save_data_unsupported_format(local_data_storage, sample_data):
    with pytest.raises(ValueError, match=r"Invalid storage format\. Supported formats are: csv, json\."):
        local_data_storage.save_data(sample_data, storage_format="unsupported")


def test_save_as_csv_overwrites_by_default(local_data_storage, sample_data, tmp_path):
    target = tmp_path / "test_data.csv"
    target.write_text("old,content\n1,2\n", encoding="utf-8")

    local_data_storage._save_as_csv(sample_data, str(target))

    with open(target, newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == [{"team": "Team A", "odds": "2.5"}, {"team": "Team B", "odds": "1.8"}]


def _read_csv(path, encoding="utf-8"):
    with open(path, newline="", encoding=encoding) as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames, list(reader)


@pytest.mark.parametrize("content", [None, ""])
def test_save_as_csv_append_to_an_absent_or_empty_file_writes_the_header(
    local_data_storage, sample_data, tmp_path, content
):
    target = tmp_path / "out.csv"
    if content is not None:
        target.write_text(content, encoding="utf-8")

    local_data_storage._save_as_csv(sample_data, str(target), append=True)

    assert _read_csv(target) == (
        ["team", "odds"],
        [{"team": "Team A", "odds": "2.5"}, {"team": "Team B", "odds": "1.8"}],
    )


def test_save_as_csv_append_keeps_reordered_columns_aligned(local_data_storage, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text("match_link,home_team\r\nhttps://x/1,A\r\n", encoding="utf-8")

    local_data_storage._save_as_csv([{"home_team": "B", "match_link": "https://x/2"}], str(target), append=True)

    assert _read_csv(target) == (
        ["match_link", "home_team"],
        [{"match_link": "https://x/1", "home_team": "A"}, {"match_link": "https://x/2", "home_team": "B"}],
    )


def test_save_as_csv_append_leaves_the_columns_a_subset_lacks_empty(local_data_storage, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text("match_link,home_team,away_team\r\nhttps://x/1,A,B\r\n", encoding="utf-8")

    local_data_storage._save_as_csv([{"match_link": "https://x/2", "away_team": "C"}], str(target), append=True)

    assert _read_csv(target)[1][1] == {"match_link": "https://x/2", "home_team": "", "away_team": "C"}


def test_save_as_csv_append_widens_the_header_for_new_columns(local_data_storage, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text("match_link,home_team\r\nhttps://x/1,A\r\n", encoding="utf-8")
    batch = [{"match_link": "https://x/2", "btts_market": "yes", "home_team": "B"}]

    local_data_storage._save_as_csv(batch, str(target), append=True)

    assert _read_csv(target) == (
        ["match_link", "home_team", "btts_market"],
        [
            {"match_link": "https://x/1", "home_team": "A", "btts_market": ""},
            {"match_link": "https://x/2", "home_team": "B", "btts_market": "yes"},
        ],
    )
    assert [p.name for p in tmp_path.iterdir()] == ["out.csv"]


def test_save_as_csv_append_failure_while_widening_leaves_the_file_unchanged(local_data_storage, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text("match_link,home_team\r\nhttps://x/1,A\r\n", encoding="utf-8")
    before = target.read_bytes()
    batch = [{"match_link": f"https://x/{i}", "home_team": "B", "btts_market": "yes"} for i in (2, 3)]
    real_writerows = csv.DictWriter.writerows

    def write_one_row_then_fail(writer, rows):
        real_writerows(writer, list(rows)[:1])
        raise OSError("disk full")

    with (
        patch("oddsharvester.storage.local_data_storage.csv.DictWriter.writerows", write_one_row_then_fail),
        pytest.raises(OSError, match="disk full"),
    ):
        local_data_storage._save_as_csv(batch, str(target), append=True)

    assert target.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["out.csv"]


def test_save_as_csv_append_reads_a_header_behind_a_bom(local_data_storage, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text("\ufeffmatch_link,home_team\r\nhttps://x/1,A\r\n", encoding="utf-8")

    local_data_storage._save_as_csv([{"home_team": "B", "match_link": "https://x/2"}], str(target), append=True)

    assert target.read_bytes().startswith("\ufeff".encode())
    assert _read_csv(target, encoding="utf-8-sig") == (
        ["match_link", "home_team"],
        [{"match_link": "https://x/1", "home_team": "A"}, {"match_link": "https://x/2", "home_team": "B"}],
    )


def test_save_as_csv_append_keeps_the_bom_when_widening(local_data_storage, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text("\ufeffmatch_link,home_team\r\nhttps://x/1,A\r\n", encoding="utf-8")

    local_data_storage._save_as_csv([{"match_link": "https://x/2", "away_team": "C"}], str(target), append=True)

    assert target.read_bytes().startswith("\ufeff".encode())
    header, rows = _read_csv(target, encoding="utf-8-sig")
    assert header == ["match_link", "home_team", "away_team"]
    assert rows[1] == {"match_link": "https://x/2", "home_team": "", "away_team": "C"}


def test_save_as_csv_append_matches_quoted_column_names(local_data_storage, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text('"odds, decimal",match_link\r\n2.5,https://x/1\r\n', encoding="utf-8")

    local_data_storage._save_as_csv([{"match_link": "https://x/2", "odds, decimal": "3.1"}], str(target), append=True)

    assert _read_csv(target) == (
        ["odds, decimal", "match_link"],
        [{"odds, decimal": "2.5", "match_link": "https://x/1"}, {"odds, decimal": "3.1", "match_link": "https://x/2"}],
    )


def test_save_as_csv_append_refuses_a_header_with_repeated_columns(local_data_storage, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text("match_link,odds,odds\r\nhttps://x/1,1.5,2.5\r\n", encoding="utf-8")
    before = target.read_bytes()

    with pytest.raises(ValueError, match=r"repeats \['odds'\]"):
        local_data_storage._save_as_csv([{"match_link": "https://x/2", "odds": "3.0"}], str(target), append=True)

    assert target.read_bytes() == before


def test_save_as_csv_append_refuses_a_whitespace_only_first_line(local_data_storage, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text(" \r\nx1,A\r\n", encoding="utf-8")
    before = target.read_bytes()

    with pytest.raises(ValueError, match="its first line is empty"):
        local_data_storage._save_as_csv([{"match_link": "https://x/2", "home_team": "B"}], str(target), append=True)

    assert target.read_bytes() == before


def test_save_as_csv_append_in_place_onto_a_file_without_a_final_newline(local_data_storage, tmp_path):
    """A hand edit or a crash mid-append can leave the last byte not '\\n'; the next
    append must not glue its first row onto the file's last line."""
    target = tmp_path / "out.csv"
    target.write_bytes(b"match_link,home_team\r\nx1,A")

    local_data_storage._save_as_csv([{"match_link": "x2", "home_team": "B"}], str(target), append=True)

    assert _read_csv(target) == (
        ["match_link", "home_team"],
        [{"match_link": "x1", "home_team": "A"}, {"match_link": "x2", "home_team": "B"}],
    )


def test_save_as_csv_append_refuses_widening_when_an_existing_row_is_longer_than_the_header(
    local_data_storage, tmp_path
):
    target = tmp_path / "out.csv"
    target.write_text("match_link,home_team\r\nx1,A\r\nx2,B,yes\r\n", encoding="utf-8")
    before = target.read_bytes()

    with pytest.raises(ValueError, match=r"row 2 has more cells than its header"):
        local_data_storage._save_as_csv(
            [{"match_link": "x3", "home_team": "C", "btts_market": "no"}], str(target), append=True
        )

    assert target.read_bytes() == before


def test_save_as_json_overwrites_by_default(local_data_storage, sample_data, tmp_path):
    target = tmp_path / "test_data.json"
    target.write_text(json.dumps([{"team": "Old Team", "odds": 3.0}]), encoding="utf-8")

    local_data_storage._save_as_json(sample_data, str(target))

    assert json.loads(target.read_text(encoding="utf-8")) == sample_data


def test_save_as_json_new_file(local_data_storage, sample_data, tmp_path):
    target = tmp_path / "test_data.json"

    local_data_storage._save_as_json(sample_data, str(target), append=True)

    assert json.loads(target.read_text(encoding="utf-8")) == sample_data


def test_save_as_json_append_existing_data(local_data_storage, sample_data, tmp_path):
    existing = [{"team": "Old Team", "odds": 3.0}]
    target = tmp_path / "test_data.json"
    target.write_text(json.dumps(existing), encoding="utf-8")

    local_data_storage._save_as_json(sample_data, str(target), append=True)

    assert json.loads(target.read_text(encoding="utf-8")) == existing + sample_data


def test_save_data_invalid_format_type(local_data_storage, sample_data):
    with pytest.raises(ValueError, match=r"Invalid storage format\. Supported formats are: csv, json\."):
        local_data_storage.save_data(sample_data, storage_format="xml")


def test_ensure_directory_exists(local_data_storage):
    with patch("os.path.exists", return_value=False), patch("os.makedirs") as mock_makedirs:
        local_data_storage._ensure_directory_exists("data/test_file.csv")

    mock_makedirs.assert_called_once_with("data")


def test_ensure_directory_exists_no_directory(local_data_storage):
    """Test when file path has no directory component."""
    with patch("os.path.exists", return_value=False), patch("os.makedirs") as mock_makedirs:
        local_data_storage._ensure_directory_exists("test_file.csv")

    # Should not call makedirs when no directory
    mock_makedirs.assert_not_called()


def test_ensure_directory_exists_directory_exists(local_data_storage):
    """Test when directory already exists."""
    with patch("os.path.exists", return_value=True), patch("os.makedirs") as mock_makedirs:
        local_data_storage._ensure_directory_exists("data/test_file.csv")

    # Should not call makedirs when directory exists
    mock_makedirs.assert_not_called()


def test_csv_save_error_handling(local_data_storage, sample_data):
    with (
        patch("builtins.open", side_effect=OSError("File write error")),
        patch.object(local_data_storage.logger, "error") as mock_logger,
    ):
        with pytest.raises(OSError, match="File write error"):
            local_data_storage._save_as_csv(sample_data, "test_data.csv")

    mock_logger.assert_called()


def test_json_save_error_handling(local_data_storage, sample_data):
    with (
        patch("builtins.open", side_effect=OSError("File write error")),
        patch.object(local_data_storage.logger, "error") as mock_logger,
    ):
        with pytest.raises(OSError, match="File write error"):
            local_data_storage._save_as_json(sample_data, "test_data.json")

    mock_logger.assert_called()


def test_save_as_csv_keeps_a_null_column_from_the_first_row(local_data_storage, tmp_path):
    """An optional column must be present-and-null rather than absent so its
    value lands in its own column, not merged into a union header (issue #81)."""
    rows = [
        {"match_link": "https://oddsportal.com/m1", "kickoff_utc": "2026-07-20 18:30:00 UTC"},
        {"match_link": "https://oddsportal.com/m2", "kickoff_utc": None},
    ]
    target = tmp_path / "links.csv"

    local_data_storage.save_data(rows, file_path=str(target), storage_format="csv")

    with open(target, newline="", encoding="utf-8") as handle:
        written = list(csv.DictReader(handle))

    assert list(written[0].keys()) == ["match_link", "kickoff_utc"]
    assert written[0]["kickoff_utc"] == "2026-07-20 18:30:00 UTC"
    assert written[1]["kickoff_utc"] == ""


def test_save_as_json_append_refuses_an_invalid_existing_file(local_data_storage, sample_data, tmp_path):
    """An unreadable file must never be replaced by the new batch alone."""
    target = tmp_path / "test_data.json"
    target.write_text("invalid json content", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        local_data_storage._save_as_json(sample_data, str(target), append=True)

    assert target.read_text(encoding="utf-8") == "invalid json content"


def test_save_as_json_append_refuses_a_json_object(local_data_storage, sample_data, tmp_path):
    target = tmp_path / "test_data.json"
    target.write_text('{"team": "Old Team"}', encoding="utf-8")

    with pytest.raises(ValueError, match="not a list"):
        local_data_storage._save_as_json(sample_data, str(target), append=True)

    assert target.read_text(encoding="utf-8") == '{"team": "Old Team"}'


@pytest.mark.parametrize("content", ["", "  \n"])
def test_save_as_json_append_treats_a_blank_file_as_empty(local_data_storage, sample_data, tmp_path, content):
    target = tmp_path / "test_data.json"
    target.write_text(content, encoding="utf-8")

    local_data_storage._save_as_json(sample_data, str(target), append=True)

    assert json.loads(target.read_text(encoding="utf-8")) == sample_data


def test_json_write_failure_leaves_the_previous_file_intact(local_data_storage, tmp_path):
    target = tmp_path / "out.json"
    target.write_text('[{"team": "Old Team"}]', encoding="utf-8")

    with pytest.raises(TypeError):
        local_data_storage._save_as_json([{"team": object()}], str(target))

    assert target.read_text(encoding="utf-8") == '[{"team": "Old Team"}]'
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


def test_csv_write_failure_leaves_the_previous_file_intact(local_data_storage, sample_data, tmp_path):
    target = tmp_path / "out.csv"
    target.write_text("team,odds\nOld Team,3.0\n", encoding="utf-8")

    with (
        patch("oddsharvester.storage.local_data_storage.csv.DictWriter.writerows", side_effect=OSError("disk full")),
        pytest.raises(OSError, match="disk full"),
    ):
        local_data_storage._save_as_csv(sample_data, str(target))

    assert target.read_text(encoding="utf-8") == "team,odds\nOld Team,3.0\n"
    assert [p.name for p in tmp_path.iterdir()] == ["out.csv"]


def test_atomic_write_keeps_the_existing_file_mode(local_data_storage, sample_data, tmp_path):
    target = tmp_path / "out.json"
    target.write_text("[]", encoding="utf-8")
    target.chmod(0o640)

    local_data_storage._save_as_json(sample_data, str(target))

    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_atomic_write_gives_a_new_file_the_umask_default_mode(local_data_storage, sample_data, tmp_path):
    old_umask = os.umask(0o022)
    try:
        local_data_storage._save_as_json(sample_data, str(tmp_path / "new.json"))
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE((tmp_path / "new.json").stat().st_mode) == 0o644


def test_atomic_write_follows_a_symlinked_output(local_data_storage, sample_data, tmp_path):
    real = tmp_path / "real.json"
    real.write_text("[]", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)

    local_data_storage._save_as_json(sample_data, str(link))

    assert link.is_symlink()
    assert json.loads(real.read_text(encoding="utf-8")) == sample_data


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can write any file")
def test_atomic_write_refuses_a_read_only_output(local_data_storage, sample_data, tmp_path):
    """os.replace only needs a writable directory, so a file the user made read-only is checked first."""
    target = tmp_path / "out.json"
    target.write_text("[]", encoding="utf-8")
    target.chmod(0o444)

    with pytest.raises(PermissionError):
        local_data_storage._save_as_json(sample_data, str(target))

    assert target.read_text(encoding="utf-8") == "[]"


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can write any file")
def test_atomic_write_falls_back_to_in_place_in_a_read_only_directory(local_data_storage, sample_data, tmp_path):
    """A temporary file cannot be created in a read-only directory, but the existing file is writable."""
    target = tmp_path / "out.json"
    target.write_text("[]", encoding="utf-8")
    tmp_path.chmod(0o555)

    try:
        local_data_storage._save_as_json(sample_data, str(target))
    finally:
        tmp_path.chmod(0o755)

    assert json.loads(target.read_text(encoding="utf-8")) == sample_data


def test_atomic_write_falls_back_to_in_place_when_replace_fails(local_data_storage, sample_data, tmp_path):
    """A single-file bind mount rejects os.replace with EBUSY; the fallback writes the mount point in place."""
    target = tmp_path / "out.json"
    target.write_text("[]", encoding="utf-8")

    with patch(
        "oddsharvester.storage.local_data_storage.os.replace",
        side_effect=OSError(errno.EBUSY, "Device or resource busy"),
    ):
        local_data_storage._save_as_json(sample_data, str(target))

    assert json.loads(target.read_text(encoding="utf-8")) == sample_data
    assert [p.name for p in tmp_path.iterdir()] == ["out.json"]


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root can write any file")
def test_atomic_write_still_raises_for_a_new_file_in_a_read_only_directory(local_data_storage, sample_data, tmp_path):
    """No target to fall back to writing in place, so a new file in a read-only directory still fails."""
    target = tmp_path / "new.json"
    tmp_path.chmod(0o555)

    try:
        with pytest.raises(OSError):
            local_data_storage._save_as_json(sample_data, str(target))
    finally:
        tmp_path.chmod(0o755)

    assert not target.exists()


def test_save_data_creates_missing_directories(local_data_storage, sample_data, tmp_path):
    target = tmp_path / "new" / "dir" / "out.json"

    local_data_storage.save_data(sample_data, file_path=str(target), storage_format="json")

    assert json.loads(target.read_text(encoding="utf-8")) == sample_data


def test_save_as_csv_unions_columns_across_rows(local_data_storage, tmp_path):
    """Line markets (Over/Under, AH) yield different columns per match, so the
    header must be the union of all rows' keys, not the first row's (issue #78)."""
    rows = [
        {"match_link": "https://oddsportal.com/m1", "over_under_2_5_market": "a"},
        {"match_link": "https://oddsportal.com/m2", "over_under_3_5_market": "b"},
    ]
    target = tmp_path / "odds.csv"

    local_data_storage.save_data(rows, file_path=str(target), storage_format="csv")

    with open(target, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        written = list(reader)
        header = reader.fieldnames

    # First-seen order: first row's columns first, later additions appended.
    assert header == ["match_link", "over_under_2_5_market", "over_under_3_5_market"]
    assert written[0]["over_under_2_5_market"] == "a"
    assert written[0]["over_under_3_5_market"] == ""
    assert written[1]["over_under_2_5_market"] == ""
    assert written[1]["over_under_3_5_market"] == "b"
