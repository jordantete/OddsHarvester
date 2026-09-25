from collections.abc import Callable
import csv
import json
import logging
import os
import stat
from typing import TextIO
import uuid

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
            # Union of all rows' keys in first-seen order: line markets (Over/Under,
            # Asian Handicap) yield different columns per match, so the first row
            # alone cannot define the header (issue #78).
            fieldnames = list(dict.fromkeys(key for row in data for key in row))

            if append:
                # Appending in place: an atomic append would rewrite the whole file.
                with open(file_path, mode="a", newline="", encoding="utf-8") as file:
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    # Only write a header if the file is newly created (empty).
                    if os.path.getsize(file_path) == 0:
                        writer.writeheader()
                    writer.writerows(data)
            else:

                def write(file: TextIO) -> None:
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(data)

                self._write_atomically(file_path, write, newline="")

            self.logger.info(f"Successfully saved {len(data)} record(s) to {file_path}")

        except Exception as e:
            self.logger.error(f"Error saving data to {file_path}: {e!s}", exc_info=True)
            raise

    def _save_as_json(self, data: list[dict], file_path: str, append: bool = False):
        """Save data in JSON format. Overwrites by default; appends when append=True."""
        try:
            if append:
                data = self._read_json_list(file_path) + data

            self._write_atomically(file_path, lambda file: json.dump(data, file, indent=4))

            self.logger.info(f"Successfully saved {len(data)} record(s) to {file_path}")

        except Exception as e:
            self.logger.error(f"Error saving data to {file_path}: {e!s}", exc_info=True)
            raise

    @staticmethod
    def _read_json_list(file_path: str) -> list:
        """Records already in a JSON output; refuses a file that appending would destroy."""
        if not os.path.exists(file_path):
            return []
        with open(file_path, encoding="utf-8") as file:
            content = file.read()
        if not content.strip():
            return []
        try:
            existing = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Cannot append to {file_path}: it is not valid JSON ({e}); it was left unchanged.") from e
        if not isinstance(existing, list):
            raise ValueError(
                f"Cannot append to {file_path}: it holds a JSON {type(existing).__name__}, not a list; "
                "it was left unchanged."
            )
        return existing

    @staticmethod
    def _write_atomically(file_path: str, write: Callable[[TextIO], None], newline: str | None = None) -> None:
        """Write to a temporary file next to the target, then move it over the target in one step."""
        # A symlinked output keeps its link; the file it points to is replaced.
        target = os.path.realpath(file_path)
        # os.replace only needs a writable directory, so a read-only output would be replaced silently.
        if os.path.exists(target) and not os.access(target, os.W_OK):
            raise PermissionError(f"Output file is not writable: {target}")
        temp_path = os.path.join(os.path.dirname(target), f".{os.path.basename(target)}.{uuid.uuid4().hex}.tmp")
        try:
            with open(temp_path, "x", newline=newline, encoding="utf-8") as file:
                write(file)
                file.flush()
                os.fsync(file.fileno())
            if os.path.exists(target):
                os.chmod(temp_path, stat.S_IMODE(os.stat(target).st_mode))
            os.replace(temp_path, target)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def _ensure_directory_exists(self, file_path: str):
        """Ensures the directory for the given file path exists. If it doesn't exist, creates it."""
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
