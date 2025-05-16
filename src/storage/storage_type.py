from enum import Enum
from src.storage.local_data_storage import LocalDataStorage
from src.storage.remote_data_storage import RemoteDataStorage

class StorageType(Enum):
    LOCAL = "local"
    REMOTE = "remote"

    def get_storage_instance(self):
        if self == StorageType.LOCAL:
            return LocalDataStorage()
        elif self == StorageType.REMOTE:
            return RemoteDataStorage()
        else:
            raise ValueError(f"Unsupported storage type: {self.value}")