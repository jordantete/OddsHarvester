import json
from unittest.mock import mock_open, patch

from botocore.exceptions import BotoCoreError, NoCredentialsError
import pytest

from src.storage.remote_data_storage import RemoteDataStorage


@pytest.fixture
def remote_data_storage():
    return RemoteDataStorage()


@pytest.fixture
def sample_data():
    return [{"team": "Team A", "odds": 2.5}, {"team": "Team B", "odds": 1.8}]


def test_initialization(remote_data_storage):
    assert remote_data_storage.s3_client is not None
    assert remote_data_storage.logger is not None
    assert remote_data_storage.S3_BUCKET_NAME == "odds-portal-scrapped-odds-cad8822c179f12cg"
    assert remote_data_storage.AWE_REGION == "eu-west-3"


def test_save_to_json(remote_data_storage, sample_data):
    mock_file = mock_open()

    with patch("builtins.open", mock_file):
        remote_data_storage._save_to_json(sample_data, "test_data.json")

    # Check if file was opened in write mode
    mock_file.assert_called_once_with("test_data.json", "w", encoding="utf-8")

    # Validate JSON content
    handle = mock_file()
    json.dump(sample_data, handle, indent=4)
    handle.write.assert_called()


def test_save_to_json_error(remote_data_storage, sample_data):
    with (
        patch("builtins.open", side_effect=OSError("File write error")),
        patch.object(remote_data_storage.logger, "error") as mock_logger,
    ):
        with pytest.raises(OSError, match="File write error"):
            remote_data_storage._save_to_json(sample_data, "test_data.json")

    mock_logger.assert_called()


def test_upload_to_s3_success(remote_data_storage):
    with patch.object(remote_data_storage.s3_client, "upload_file") as mock_upload:
        remote_data_storage._upload_to_s3("test_data.json", "s3_object.json")

    mock_upload.assert_called_once_with("test_data.json", remote_data_storage.S3_BUCKET_NAME, "s3_object.json")


def test_upload_to_s3_default_object_name(remote_data_storage):
    with patch.object(remote_data_storage.s3_client, "upload_file") as mock_upload:
        remote_data_storage._upload_to_s3("test_data.json")

    mock_upload.assert_called_once_with("test_data.json", remote_data_storage.S3_BUCKET_NAME, "test_data.json")


def test_upload_to_s3_error(remote_data_storage):
    with (
        patch.object(remote_data_storage.s3_client, "upload_file", side_effect=BotoCoreError),
        patch.object(remote_data_storage.logger, "error") as mock_logger,
    ):
        with pytest.raises(BotoCoreError):
            remote_data_storage._upload_to_s3("test_data.json", "s3_object.json")

    mock_logger.assert_called()


def test_upload_to_s3_no_credentials(remote_data_storage):
    with (
        patch.object(remote_data_storage.s3_client, "upload_file", side_effect=NoCredentialsError()),
        patch.object(remote_data_storage.logger, "error") as mock_logger,
    ):
        with pytest.raises(NoCredentialsError):
            remote_data_storage._upload_to_s3("test_data.json", "s3_object.json")

    mock_logger.assert_called()


def test_process_and_upload(remote_data_storage, sample_data):
    with (
        patch.object(remote_data_storage, "_save_to_json") as mock_save_json,
        patch.object(remote_data_storage, "_upload_to_s3") as mock_upload_s3,
    ):
        remote_data_storage.process_and_upload(sample_data, "test_data.json", "s3_object.json")

    mock_save_json.assert_called_once_with(data=sample_data, file_name="test_data.json")
    mock_upload_s3.assert_called_once_with(file_name="test_data.json", object_name="s3_object.json")


def test_process_and_upload_error(remote_data_storage, sample_data):
    with (
        patch.object(remote_data_storage, "_save_to_json", side_effect=OSError("File save error")),
        patch.object(remote_data_storage.logger, "error") as mock_logger,
    ):
        with pytest.raises(OSError, match="File save error"):
            remote_data_storage.process_and_upload(sample_data, "test_data.json", "s3_object.json")

    mock_logger.assert_called()
