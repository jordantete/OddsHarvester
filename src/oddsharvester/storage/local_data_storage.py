import csv
import json
import logging
import os

from .storage_format import StorageFormat


class LocalDataStorage:
    """
    A class to handle the storage of scraped data locally in either JSON or CSV format.
    """

    def __init__(
        self, default_file_path: str = "scraped_data", default_storage_format: StorageFormat = StorageFormat.JSON
    ):
        """
        Initialize LocalDataStorage.

        Args:
            default_file_path (str): Default file path to use if none is provided in `save_data`.
            default_storage_format (StorageFormat): Default file format to use if none is provided in StorageFormat.CSV.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.default_file_path = default_file_path
        self.default_storage_format = default_storage_format

    def save_data(
        self,
        data: dict | list[dict],
        file_path: str | None = None,
        storage_format: StorageFormat | None = None,
        append: bool = False,
    ):
        """
        Save scraped data to a local CSV or JSON file.

        Args:
            data (Union[Dict, List[Dict]]): The data to save, either as a dictionary or a list of dictionaries.
            file_path (str, optional): The file path to save the data. Defaults to `self.default_file_path`.
            storage_format (StorageFormat, optional): The format to save the data in ("csv" or "json").
            Defaults to `self.default_storage_format`.
            append (bool): When True, append to the existing file; when False (default), overwrite it.

        Raises:
            ValueError: If the data is not in the correct format (dict or list of dicts).
            Exception: If an error occurs during file operations.
        """
        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise ValueError("Data must be a dictionary or a list of dictionaries.")

        target_file_path = file_path or self.default_file_path
        format_to_use = storage_format.lower() if storage_format else self.default_storage_format.value

        if format_to_use not in [f.value for f in StorageFormat]:
            raise ValueError(
                f"Invalid storage format. Supported formats are: {', '.join(f.value for f in StorageFormat)}."
            )

        if not target_file_path.endswith(f".{format_to_use}"):
            target_file_path = f"{target_file_path}.{format_to_use}"

        self._ensure_directory_exists(target_file_path)

        if format_to_use == StorageFormat.CSV.value:
            self._save_as_csv(data, target_file_path, append=append)
        elif format_to_use == StorageFormat.JSON.value:
            self._save_as_json(data, target_file_path, append=append)
        else:
            raise ValueError("Unsupported file format.")

    def _save_as_csv(self, data: list[dict], file_path: str, append: bool = False):
        """Save data in CSV format. Overwrites by default; appends when append=True."""
        try:
            mode = "a" if append else "w"
            with open(file_path, mode=mode, newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=data[0].keys())

                # In append mode, only write a header if the file is newly created (empty).
                # In overwrite mode, the header is always written.
                if not append or os.path.getsize(file_path) == 0:
                    writer.writeheader()

                writer.writerows(data)

            self.logger.info(f"Successfully saved {len(data)} record(s) to {file_path}")

        except Exception as e:
            self.logger.error(f"Error saving data to {file_path}: {e!s}", exc_info=True)
            raise

    def _save_as_json(self, data: list[dict], file_path: str, append: bool = False):
        """Save data in JSON format. Overwrites by default; appends when append=True."""
        try:
            if append and os.path.exists(file_path):
                existing_data = []
                with open(file_path, encoding="utf-8") as file:
                    try:
                        existing_data = json.load(file)
                    except json.JSONDecodeError:
                        self.logger.warning(f"File {file_path} exists but is empty or invalid JSON.")
                data = existing_data + data

            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(data, file, indent=4)

            self.logger.info(f"Successfully saved {len(data)} record(s) to {file_path}")

        except Exception as e:
            self.logger.error(f"Error saving data to {file_path}: {e!s}", exc_info=True)
            raise

    def _ensure_directory_exists(self, file_path: str):
        """Ensures the directory for the given file path exists. If it doesn't exist, creates it."""
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
