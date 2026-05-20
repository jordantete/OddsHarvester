import logging

from oddsharvester.storage.storage_format import StorageFormat
from oddsharvester.storage.storage_type import StorageType

logger = logging.getLogger("StorageManager")


def store_data(
    storage_type: StorageType,
    data: list,
    storage_format: StorageFormat,
    file_path: str,
    append: bool = False,
):
    """Handles storing data in the chosen storage type.

    When ``append`` is True and the storage is local, the new data is concatenated to
    any existing file at ``file_path``. When False (default), the file is overwritten.
    Remote storage ignores ``append``.
    """
    try:
        storage_enum = StorageType(storage_type)
        storage = storage_enum.get_storage_instance()

        if storage_type == StorageType.REMOTE.value:
            storage.process_and_upload(data=data, file_path=file_path)
        else:
            storage.save_data(data=data, file_path=file_path, storage_format=storage_format, append=append)

        logger.info(f"Successfully stored {len(data)} records.")
        return True

    except Exception as e:
        logger.error(f"Error during data storage: {e!s}")
        return False
