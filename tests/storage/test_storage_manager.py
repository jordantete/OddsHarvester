from unittest.mock import MagicMock, patch

import pytest

from oddsharvester.storage.remote_data_storage import S3UploadError
from oddsharvester.storage.storage_format import StorageFormat
from oddsharvester.storage.storage_manager import store_data
from oddsharvester.storage.storage_type import StorageType


@pytest.fixture
def sample_data():
    return [{"id": 1, "value": 100}, {"id": 2, "value": 200}]


@pytest.fixture
def mock_storage():
    return MagicMock()


def test_store_data_local_storage(sample_data, mock_storage):
    with patch("oddsharvester.storage.storage_type.StorageType.get_storage_instance", return_value=mock_storage):
        result = store_data(StorageType.LOCAL.value, sample_data, StorageFormat.JSON, "test.json")

        mock_storage.save_data.assert_called_once_with(
            data=sample_data, file_path="test.json", storage_format=StorageFormat.JSON, append=False
        )
        assert result is True


def test_store_data_local_storage_append(sample_data, mock_storage):
    with patch("oddsharvester.storage.storage_type.StorageType.get_storage_instance", return_value=mock_storage):
        result = store_data(StorageType.LOCAL.value, sample_data, StorageFormat.JSON, "test.json", append=True)

        mock_storage.save_data.assert_called_once_with(
            data=sample_data, file_path="test.json", storage_format=StorageFormat.JSON, append=True
        )
        assert result is True


@pytest.mark.parametrize("append", [False, True])
def test_store_data_remote_storage_writes_like_local(sample_data, mock_storage, append):
    with patch("oddsharvester.storage.storage_type.StorageType.get_storage_instance", return_value=mock_storage):
        result = store_data(StorageType.REMOTE.value, sample_data, StorageFormat.CSV, "test.csv", append=append)

        mock_storage.save_data.assert_called_once_with(
            data=sample_data, file_path="test.csv", storage_format=StorageFormat.CSV, append=append
        )
        assert result is True


def test_store_data_lets_an_upload_failure_through(sample_data, mock_storage):
    mock_storage.save_data.side_effect = S3UploadError("test.json", "s3://bucket/test.json", OSError("denied"))

    with (
        patch("oddsharvester.storage.storage_type.StorageType.get_storage_instance", return_value=mock_storage),
        pytest.raises(S3UploadError),
    ):
        store_data(StorageType.REMOTE.value, sample_data, StorageFormat.JSON, "test.json")


def test_store_data_invalid_storage(sample_data):
    with patch("oddsharvester.storage.storage_manager.logger") as mock_logger:
        result = store_data("INVALID_STORAGE", sample_data, StorageFormat.JSON, "test.json")

        mock_logger.error.assert_called_once()
        assert result is False


def test_store_data_exception_handling(sample_data, mock_storage):
    mock_storage.save_data.side_effect = Exception("Storage error")

    with (
        patch("oddsharvester.storage.storage_type.StorageType.get_storage_instance", return_value=mock_storage),
        patch("oddsharvester.storage.storage_manager.logger") as mock_logger,
    ):
        result = store_data(StorageType.LOCAL.value, sample_data, StorageFormat.JSON, "test.json")

        mock_logger.error.assert_called_once_with("Error during data storage: Storage error", exc_info=True)
        assert result is False
