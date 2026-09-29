import logging

from oddsharvester.storage.remote_data_storage import S3UploadError
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

    Both storage types write the local file at ``file_path``; ``append`` concatenates the new data to
    it, otherwise it is overwritten. Remote storage then uploads that file. False when the local write
    fails; an upload failure raises S3UploadError instead, since the local file already holds the data.
    """
    try:
        storage_enum = StorageType(storage_type)
        storage = storage_enum.get_storage_instance()
        storage.save_data(data=data, file_path=file_path, storage_format=storage_format, append=append)

        logger.info(f"Successfully stored {len(data)} records.")
        return True

    except S3UploadError:
        raise

    except Exception as e:
        logger.error(f"Error during data storage: {e!s}", exc_info=True)
        return False
