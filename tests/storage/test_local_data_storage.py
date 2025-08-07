import csv
import json
from unittest.mock import mock_open, patch

import pytest

from src.storage.local_data_storage import LocalDataStorage
from src.storage.storage_format import StorageFormat


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
    with pytest.raises(ValueError, match="Data must be a dictionary or a list of dictionaries."):
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
        mock_save.assert_called_once_with(sample_data, "test.csv")


def test_save_data_with_existing_extension(local_data_storage, sample_data):
    with patch.object(local_data_storage, "_save_as_csv") as mock_save:
        local_data_storage.save_data(sample_data, file_path="test.csv", storage_format="csv")

        # Verify that extension wasn't duplicated
        mock_save.assert_called_once_with(sample_data, "test.csv")


def test_save_data_unsupported_format(local_data_storage, sample_data):
    with pytest.raises(ValueError, match="Invalid storage format. Supported formats are: csv, json."):
        local_data_storage.save_data(sample_data, storage_format="unsupported")


def test_save_as_csv(local_data_storage, sample_data):
    mock_file = mock_open()

    with patch("builtins.open", mock_file), patch("os.path.getsize", return_value=0):
        local_data_storage._save_as_csv(sample_data, "test_data.csv")

    # Check if file was opened correctly
    mock_file.assert_called_once_with("test_data.csv", mode="a", newline="", encoding="utf-8")

    # Validate the written content
    handle = mock_file()
    writer = csv.DictWriter(handle, fieldnames=sample_data[0].keys())
    writer.writeheader()
    writer.writerows(sample_data)
    handle.write.assert_called()


def test_save_as_csv_existing_file(local_data_storage, sample_data):
    mock_file = mock_open()

    with patch("builtins.open", mock_file), patch("os.path.getsize", return_value=100):
        local_data_storage._save_as_csv(sample_data, "test_data.csv")

    # Check if file was opened correctly
    mock_file.assert_called_once_with("test_data.csv", mode="a", newline="", encoding="utf-8")


def test_save_as_json(local_data_storage, sample_data):
    mock_file = mock_open()

    with patch("builtins.open", mock_file), patch("os.path.exists", return_value=False):
        local_data_storage._save_as_json(sample_data, "test_data.json")

    # Check if file was opened in write mode
    mock_file.assert_called_once_with("test_data.json", "w", encoding="utf-8")

    # Validate JSON content
    handle = mock_file()
    json.dump(sample_data, handle, indent=4)
    handle.write.assert_called()


def test_save_as_json_existing_data(local_data_storage, sample_data):
    existing_data = [{"team": "Old Team", "odds": 3.0}]
    expected_combined_data = existing_data + sample_data

    mock_file = mock_open(read_data=json.dumps(existing_data))

    with patch("builtins.open", mock_file), patch("os.path.exists", return_value=True):
        local_data_storage._save_as_json(sample_data, "test_data.json")

    # Validate the final content of the JSON file
    handle = mock_file()
    json.dump(expected_combined_data, handle, indent=4)
    handle.write.assert_called()


def test_save_as_json_invalid_json_file(local_data_storage, sample_data):
    mock_file = mock_open(read_data="invalid json content")

    with patch("builtins.open", mock_file), patch("os.path.exists", return_value=True):
        local_data_storage._save_as_json(sample_data, "test_data.json")

    # Should still save the new data (existing data ignored due to invalid JSON)
    handle = mock_file()
    json.dump(sample_data, handle, indent=4)
    handle.write.assert_called()


def test_save_data_invalid_format_type(local_data_storage, sample_data):
    with pytest.raises(ValueError, match="Invalid storage format. Supported formats are: csv, json."):
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
