import json
import logging
from typing import Any

import boto3


class RemoteDataStorage:
    S3_BUCKET_NAME = "odds-portal-scrapped-odds-cad8822c179f12cg"
    AWE_REGION = "eu-west-3"

    def __init__(self):
        """
        Initializes the RemoteDataStorage class with an S3 client and logger.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.s3_client = boto3.client("s3", region_name=self.AWE_REGION)
        self.logger.info(
            f"RemoteDataStorage initialized for region: {self.AWE_REGION} and bucket: {self.S3_BUCKET_NAME}"
        )

    def _save_to_json(self, data: list[dict[str, Any]], file_name: str) -> None:
        """
        Saves the data to a JSON file locally.

        Args:
            data: The raw scraped data.
            file_name: The name of the JSON file.
        """
        self.logger.info(f"Saving data to JSON file: {file_name}")
        try:
            with open(file_name, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4)
            self.logger.info(f"Data successfully saved to {file_name}")

        except Exception as e:
            self.logger.error(f"Failed to save data to JSON: {e}")
            raise

    def _upload_to_s3(self, file_name: str, object_name: str | None = None) -> None:
        """
        Uploads a file to the configured S3 bucket.

        Args:
            file_name: The file to upload.
            object_name: The name of the object in S3. Defaults to the filename.
        """
        if object_name is None:
            object_name = file_name

        try:
            self.logger.info(f"Uploading {file_name} to bucket {self.S3_BUCKET_NAME} as {object_name}")
            self.s3_client.upload_file(file_name, self.S3_BUCKET_NAME, object_name)
            self.logger.info(f"File uploaded successfully to {self.S3_BUCKET_NAME}/{object_name}")

        except Exception as e:
            self.logger.error(f"Failed to upload {file_name} to S3: {e}")
            raise

    def process_and_upload(self, data: list[dict[str, Any]], file_path: str, object_name: str | None = None) -> None:
        """
        Saves data as a JSON file locally and uploads it to S3.

        Args:
            data: The raw scraped data.
            file_name: The name of the JSON file.
            object_name: The name of the object in S3. Defaults to the filename.
        """
        try:
            self.logger.info("Starting the process to save and upload data.")
            self._save_to_json(data=data, file_name=file_path)
            self._upload_to_s3(file_name=file_path, object_name=object_name)
            self.logger.info("Data processed and uploaded successfully.")

        except Exception as e:
            self.logger.error(f"Failed to process and upload data: {e}")
            raise
