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


def test_save_data_invalid_format_type(local_data_storage, sample_data):
    with pytest.raises(ValueError, match="Invalid storage format. Supported formats are: csv, json."):
        local_data_storage.save_data(sample_data, storage_format="xml")


def test_ensure_directory_exists(local_data_storage):
    with patch("os.path.exists", return_value=False), patch("os.makedirs") as mock_makedirs:
        local_data_storage._ensure_directory_exists("data/test_file.csv")

    mock_makedirs.assert_called_once_with("data")


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
