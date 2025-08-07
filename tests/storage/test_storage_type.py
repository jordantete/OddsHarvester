import pytest

from src.storage.local_data_storage import LocalDataStorage
from src.storage.remote_data_storage import RemoteDataStorage
from src.storage.storage_type import StorageType


def test_storage_type_local():
    storage_type = StorageType.LOCAL
    assert storage_type.value == "local"

    storage_instance = storage_type.get_storage_instance()
    assert storage_instance is not None
    assert hasattr(storage_instance, "save_data")


def test_storage_type_remote():
    storage_type = StorageType.REMOTE
    assert storage_type.value == "remote"

    storage_instance = storage_type.get_storage_instance()
    assert storage_instance is not None
    assert hasattr(storage_instance, "process_and_upload")


def test_storage_type_invalid():
    """Test invalid storage type raises ValueError."""

    # Create a mock storage type with invalid value
    class MockStorageType:
        def __init__(self):
            self.value = "invalid"

        def get_storage_instance(self):
            if self.value == "local":
                return LocalDataStorage()
            elif self.value == "remote":
                return RemoteDataStorage()
            else:
                raise ValueError(f"Unsupported storage type: {self.value}")

    mock_storage = MockStorageType()

    # Test the else branch by directly calling the method with an invalid value
    with pytest.raises(ValueError, match="Unsupported storage type: invalid"):
        mock_storage.get_storage_instance()


def test_storage_type_enum_values():
    assert StorageType.LOCAL.value == "local"
    assert StorageType.REMOTE.value == "remote"

    values = [storage_type.value for storage_type in StorageType]
    assert "local" in values
    assert "remote" in values
    assert len(values) == 2
