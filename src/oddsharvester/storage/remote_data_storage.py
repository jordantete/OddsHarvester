import logging
import os

from oddsharvester.storage.local_data_storage import LocalDataStorage
from oddsharvester.storage.storage_format import StorageFormat

_DEFAULT_AWS_REGION = "eu-west-3"


def s3_bucket() -> str:
    """The bucket named by OH_S3_BUCKET, empty when it is unset or blank."""
    return os.environ.get("OH_S3_BUCKET", "").strip()


class S3UploadError(Exception):
    """The batch reached the local file but not the bucket."""

    def __init__(self, local_path: str, s3_uri: str, error: Exception):
        super().__init__(f"Upload of {local_path} to {s3_uri} failed: {error}")
        self.local_path = local_path
        self.s3_uri = s3_uri
        self.error = error


class RemoteDataStorage:
    """Writes the output file as local storage does, then uploads that file to the S3 bucket."""

    def __init__(self):
        """
        Initializes the RemoteDataStorage class with an S3 client and logger.

        Raises:
            ValueError: If OH_S3_BUCKET is unset or blank.
        """
        # Imported here so the package runs without the s3 extra.
        import boto3

        self.logger = logging.getLogger(self.__class__.__name__)
        self.bucket = s3_bucket()
        if not self.bucket:
            raise ValueError("Remote storage needs a bucket: export OH_S3_BUCKET=<bucket>")
        self.region = os.environ.get("OH_AWS_REGION", "").strip() or _DEFAULT_AWS_REGION
        self.s3_client = boto3.client("s3", region_name=self.region)
        self.local_storage = LocalDataStorage()
        self.logger.info(f"RemoteDataStorage initialized for region: {self.region} and bucket: {self.bucket}")

    def save_data(
        self,
        data: dict | list[dict],
        file_path: str | None = None,
        storage_format: StorageFormat | None = None,
        append: bool = False,
    ) -> str:
        """
        Write the local file exactly as local storage does, then upload it with its path as the object key.

        Returns:
            str: The local path written, which is also the object key.

        Raises:
            S3UploadError: If the local file was written but the upload failed.
            Exception: Whatever the local write raised; nothing is uploaded then.
        """
        local_path = self.local_storage.save_data(
            data=data, file_path=file_path, storage_format=storage_format, append=append
        )
        s3_uri = f"s3://{self.bucket}/{local_path}"
        try:
            self.s3_client.upload_file(local_path, self.bucket, local_path)
        except Exception as e:
            self.logger.error(f"Failed to upload {local_path} to {s3_uri}: {e}")
            raise S3UploadError(local_path=local_path, s3_uri=s3_uri, error=e) from e

        self.logger.info(f"File uploaded successfully to {s3_uri}")
        return local_path
