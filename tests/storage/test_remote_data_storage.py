import csv
import json
from unittest.mock import MagicMock, patch

from botocore.exceptions import NoCredentialsError
import pytest

from oddsharvester.storage.remote_data_storage import RemoteDataStorage, S3UploadError


@pytest.fixture
def s3_client():
    return MagicMock()


@pytest.fixture
def remote_data_storage(monkeypatch, s3_client):
    monkeypatch.setenv("OH_S3_BUCKET", "test-bucket")
    monkeypatch.delenv("OH_AWS_REGION", raising=False)
    with patch("boto3.client", return_value=s3_client) as client_factory:
        storage = RemoteDataStorage()
    client_factory.assert_called_once_with("s3", region_name="eu-west-3")
    return storage


@pytest.fixture
def sample_data():
    return [{"team": "Team A", "odds": 2.5}, {"team": "Team B", "odds": 1.8}]


def test_initialization(remote_data_storage, s3_client):
    assert remote_data_storage.s3_client is s3_client
    assert remote_data_storage.bucket == "test-bucket"
    assert remote_data_storage.region == "eu-west-3"


def test_bucket_and_region_are_read_when_the_storage_is_created(monkeypatch):
    monkeypatch.setenv("OH_S3_BUCKET", "my-custom-bucket")
    monkeypatch.setenv("OH_AWS_REGION", "us-east-1")

    with patch("boto3.client") as client_factory:
        storage = RemoteDataStorage()

    assert (storage.bucket, storage.region) == ("my-custom-bucket", "us-east-1")
    client_factory.assert_called_once_with("s3", region_name="us-east-1")


@pytest.mark.parametrize("bucket", [None, "", "   "])
def test_no_bucket_is_refused(bucket, monkeypatch):
    if bucket is None:
        monkeypatch.delenv("OH_S3_BUCKET", raising=False)
    else:
        monkeypatch.setenv("OH_S3_BUCKET", bucket)

    with pytest.raises(ValueError, match="export OH_S3_BUCKET=<bucket>"):
        RemoteDataStorage()


def test_save_data_writes_the_local_file_then_uploads_it(
    remote_data_storage, s3_client, sample_data, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)

    written = remote_data_storage.save_data(sample_data, file_path="data/out", storage_format="json")

    assert written == "data/out.json"
    assert json.loads((tmp_path / "data" / "out.json").read_text(encoding="utf-8")) == sample_data
    s3_client.upload_file.assert_called_once_with("data/out.json", "test-bucket", "data/out.json")


def test_save_data_writes_the_local_default_path(remote_data_storage, s3_client, sample_data, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    written = remote_data_storage.save_data(sample_data, storage_format="csv")

    assert written == "scraped_data.csv"
    assert (tmp_path / "scraped_data.csv").exists()
    s3_client.upload_file.assert_called_once_with("scraped_data.csv", "test-bucket", "scraped_data.csv")


def test_save_data_appends_to_the_local_csv_before_uploading(
    remote_data_storage, s3_client, sample_data, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out.csv").write_text("team,odds\r\nOld Team,3.0\r\n", encoding="utf-8")

    remote_data_storage.save_data(sample_data, file_path="out.csv", storage_format="csv", append=True)

    with open(tmp_path / "out.csv", newline="", encoding="utf-8") as handle:
        assert [row["team"] for row in csv.DictReader(handle)] == ["Old Team", "Team A", "Team B"]
    s3_client.upload_file.assert_called_once_with("out.csv", "test-bucket", "out.csv")


def test_failed_upload_raises_with_both_locations_and_keeps_the_file(
    remote_data_storage, s3_client, sample_data, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    s3_client.upload_file.side_effect = NoCredentialsError()

    with pytest.raises(S3UploadError) as excinfo:
        remote_data_storage.save_data(sample_data, file_path="out.json", storage_format="json")

    assert excinfo.value.local_path == "out.json"
    assert excinfo.value.s3_uri == "s3://test-bucket/out.json"
    assert isinstance(excinfo.value.error, NoCredentialsError)
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8")) == sample_data


def test_failed_local_write_raises_before_any_upload(
    remote_data_storage, s3_client, sample_data, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "out.json").write_text("not json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        remote_data_storage.save_data(sample_data, file_path="out.json", storage_format="json", append=True)

    s3_client.upload_file.assert_not_called()
