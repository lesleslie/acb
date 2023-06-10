import json
import os
import re
from contextlib import suppress
from pathlib import Path
from typing import BinaryIO

from pathy import Pathy
from pathy import set_client_params
from pathy import use_fs
from pathy import use_fs_cache

_filename_ascii_strip_re = re.compile(r"[^A-Za-z0-9_.-]")


def secure_filename(filename: str) -> str:
    """
    From Werkzeug secure_filename.
    """

    for sep in os.path.sep, os.path.altsep:
        if sep:
            filename = filename.replace(sep, " ")

    normalized_filename = _filename_ascii_strip_re.sub("", "_".join(filename.split()))
    filename = normalized_filename.strip("._")
    return filename


class BaseStorage:  # pragma: no cover
    def get_name(self, name: str) -> str:
        ...

    def get_path(self, name: str) -> str:
        ...

    def get_size(self, name: str) -> int:
        ...

    def open(self, name: str) -> BinaryIO:
        ...

    def write(self, file: BinaryIO, name: str) -> str:
        ...


class StorageFile:
    """
    The file obect returned by the storage.
    """

    def __init__(self, *, name: str, storage: BaseStorage) -> None:
        self._name = name
        self._storage = storage

    @property
    def name(self) -> str:
        """File name including extension."""

        return self._storage.get_name(self._name)

    @property
    def path(self) -> str:
        """Complete file path."""

        return self._storage.get_path(self._name)

    @property
    def size(self) -> int:
        """File size in bytes."""

        return self._storage.get_size(self._name)

    def open(self) -> BinaryIO:
        """
        Open a file handle of the file.
        """

        return self._storage.open(self._name)

    def write(self, file: BinaryIO) -> str:
        """
        Write input file which is opened in binary mode to destination.
        """

        return self._storage.write(file=file, name=self._name)

    def __str__(self) -> str:
        return self.path


class StorageImage(StorageFile):
    """
    Inherits features of `StorageFile` and adds image specific properties.
    """

    def __init__(
        self, *, name: str, storage: BaseStorage, height: int, width: int
    ) -> None:
        super().__init__(name=name, storage=storage)
        self._width = width
        self._height = height

    @property
    def height(self) -> int:
        """
        Image height in pixels.
        """

        return self._height

    @property
    def width(self) -> int:
        """
        Image width in pixels.
        """

        return self._width


class PathyStorage(BaseStorage):
    """
    Pathy storage class which stores files on the local filesystem or in the cloud.
    You might want to use this with the `FileType` type.
    """

    default_chunk_size = 64 * 1024

    def __init__(self, path: str) -> None:
        self._path = Pathy(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self.bucket = os.environ.get("SQLALCHEMY_FIELDS_STORAGE_BUCKET")
        if os.environ.get("SQLALCHEMY_FIELDS_USE_FS_CACHE", None):
            use_fs_cache(os.environ.get("SQLALCHEMY_FIELDS_FS_CACHE_DIR", None))

    def get_name(self, name: str) -> str:
        """
        Get the normalized name of the file.
        """

        return secure_filename(Path(name).name)

    def get_path(self, name: str) -> str:
        """
        Get full path to the file.
        """

        return str(self._path / Path(name))

    def get_size(self, name: str) -> int:
        """
        Get file size in bytes.
        """

        return (self._path / name).stat().size

    def open(self, name: str) -> BinaryIO:
        """
        Open a file handle of the file object in binary mode.
        """

        path = self._path / Path(name)
        return open(path, "rb")

    def write(self, file: BinaryIO, name: str) -> str:
        """
        Write input file which is opened in binary mode to destination.
        """

        filename = secure_filename(name)
        path = self._path / Path(filename)

        file.seek(0, 0)
        with open(path, "wb") as output:
            while True:
                chunk = file.read(self.default_chunk_size)
                if not chunk:
                    break
                output.write(chunk)

        return str(path)


class FileSystemStorage(PathyStorage):
    """
    File system storage backend.
    You might want to use this with the `FileType` type.
    """

    def __init__(self, path: str) -> None:
        super().__init__(path)
        use_fs(os.environ.get("SQLALCHEMY_FIELDS_FS_DIR", None))


class GCSStorage(PathyStorage):
    """
    Google Cloud Storage backend.
    You might want to use this with the `FileType` type.
    """

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.bucket = Pathy.from_bucket(self.bucket)
        self._path = self.bucket / self._path
        from google.oauth2 import service_account

        _creds = os.environ.get("GCS_CREDENTIALS", "")
        account = service_account.Credentials
        with suppress(TypeError, OSError, FileNotFoundError):
            _creds = Path(_creds).read_text()
        creds = json.loads(_creds)
        set_client_params("gs", credentials=account.from_service_account_info(creds))


class S3Storage(PathyStorage):
    """
    Amazon S3 or any S3 compatible storage backend.
    You might want to use this with the `FileType` type.
    """

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.bucket = Pathy.from_bucket(self.bucket, scheme="s3")
        self._path = self.bucket / self._path
        access_key_id = os.environ.get("AWS_ACCESS_KEY_ID", "")
        secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        set_client_params("s3", key_id=access_key_id, key_secret=secret_access_key)


class AzureStorage(PathyStorage):  # pragma: no cover
    """
    Azure Storage backend.
    You might want to use this with the `FileType` type.
    """

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.bucket = Pathy.from_bucket(self.bucket, scheme="azure")
        self._path = self.bucket / self._path
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        set_client_params("azure", connection_string=connection_string)
