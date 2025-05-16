import logging
from src.storage.storage_type import StorageType
from src.storage.storage_format import StorageFormat

logger = logging.getLogger("StorageManager")

def store_data(
    storage_type: StorageType, 
    data: list, 
    storage_format: StorageFormat, 
    file_path: str
):
    """Handles storing data in the chosen storage type."""
    try:
        storage_enum = StorageType(storage_type)
        storage = storage_enum.get_storage_instance()

        if storage_type == StorageType.REMOTE.value:
            storage.process_and_upload(data=data, file_path=file_path)
        else:
            storage.save_data(data=data, file_path=file_path, storage_format=storage_format)

        logger.info(f"Successfully stored {len(data)} records.")
        return True

    except Exception as e:
        logger.error(f"Error during data storage: {str(e)}")
        return False