import typing as t

from acb.config import ac
from acb.config import Settings
from acb.logger import logger
from aiopathy import AsyncPathy
from aiopathy import use_fs_cache
from icecream import ic
from pydantic import HttpUrl


# from google.cloud.exceptions import NotFound


# CORS policy for upload bucket - upload-cors.json
#
# [
#     {
#       "origin": ["*"],
#       "method": ["*"],
#       "responseHeader": ["*"],
#       "maxAgeSeconds": 600
#     }
# ]


class StorageBaseSettings(Settings):
    scheme: t.Literal["gs", "s3", "azure"]
    https_url: HttpUrl
    prefix: t.Optional[str] = None
    user_project: t.Optional[str] = None  # used for billing
    buckets: dict[str, str] = {}
    use_fs_cache: bool = False

    def model_post_init(self, __context: t.Any) -> None:
        self.prefix: str = ac.app.name
        self.user_project: str = ac.app.name  # used for billing


class StorageBase:
    async def init(self) -> t.NoReturn:
        if ac.storage.use_fs_cache:
            await use_fs_cache(root=ac.tmp / "storage")
        for bucket in ac.storage.buckets:
            ic(bucket)
            # setattr(self, bucket, StorageBucket(bucket))
            setattr(
                self,
                bucket,
                AsyncPathy(
                    f"{ac.storage.scheme}://{ac.storage.buckets[bucket]}/"
                    f"{ac.storage.prefix}/"
                ),
            )
            logger.debug(f"{bucket.title()} storage bucket initialized.")
        logger.info("Storage initialized.")


# storage = load_adapter("storage")


# class StorageBucket:
#     bucket: t.Optional[str]
#     path: t.Optional[AsyncPathy]
#     prefix: str = ""
#     cache_control: t.Optional[str] = None
#
#     def __init__(self, bucket: str, prefix: str = None, **data: t.Any) -> None:
#         super().__init__(**data)
#         self.prefix = prefix or self.prefix
#         self.bucket = ac.storage.buckets[bucket]
#         self.path = AsyncPathy(f"{ac.storage.scheme}://{self.bucket}/{self.prefix}/")
#
#     def save(self, obj_path: AsyncPath, data: t.Any) -> None:
#         stor_path = self.get_path(obj_path)
#         logger.debug(f"Saving {stor_path}...")
#         if isinstance(data, bytes):
#             stor_path.write_bytes(data)
#         else:
#             stor_path.write_text(data)
#         logger.debug(f"Saved - {stor_path}")
#
#     def get(self, obj_path: AsyncPath):
#         stor_path = self.get_path(obj_path)
#         logger.debug(f"Getting {stor_path}...")
#         # try:
#         data = stor_path.read_text()
#         # except NotFound:
#         #     raise FileNotFoundError
#         logger.debug(f"Got - {stor_path}")
#         return data
#
#     def stat(self, obj_path: AsyncPath):
#         return self.get_path(obj_path).stat()
#
#     def list(self, dir_path: AsyncPath):
#         return self.get_path(dir_path).rglob("*")
#
#     def exists(self, obj_path: AsyncPath):
#         return self.get_path(obj_path).exists()
#
#     def get_path(self, obj_path: AsyncPath) -> AsyncPath:
#         ic(self.path / "/".join(obj_path.parts[1:]))
#         return self.path / "/".join(obj_path.parts[1:])
#
#     async def get_url(self, obj_path: AsyncPath):
#         return str(self.get_path(obj_path).resolve()).replace(
#             f"{ac.storage.scheme}://", ac.storage.https_url
#         )


# class BaseStorage:  # pragma: no cover
#     def get_name(self, name: str) -> str:
#         ...
#
#     def get_path(self, name: str) -> str:
#         ...
#
#     def get_size(self, name: str) -> int:
#         ...
#
#     def open(self, name: str) -> BinaryIO:
#         ...
#
#     def write(self, file: BinaryIO, name: str) -> str:
#         ...
#
#
# class StorageFile:
#     """
#     The file obect returned by the storage.
#     """
#
#     def __init__(self, *, name: str, storage: BaseStorage) -> None:
#         self._name = name
#         self._storage = storage
#
#     @property
#     def name(self) -> str:
#         """File name including extension."""
#
#         return self._storage.get_name(self._name)
#
#     @property
#     def path(self) -> str:
#         """Complete file path."""
#
#         return self._storage.get_path(self._name)
#
#     @property
#     def size(self) -> int:
#         """File size in bytes."""
#
#         return self._storage.get_size(self._name)
#
#     def open(self) -> BinaryIO:
#         """
#         Open a file handle of the file.
#         """
#
#         return self._storage.open(self._name)
#
#     def write(self, file: BinaryIO) -> str:
#         """
#         Write input file which is opened in binary mode to destination.
#         """
#
#         return self._storage.write(file=file, name=self._name)
#
#     def __str__(self) -> str:
#         return self.path
#
#
# class StorageImage(StorageFile):
#     """
#     Inherits features of `StorageFile` and adds image specific properties.
#     """
#
#     def __init__(
#         self, *, name: str, storage: BaseStorage, height: int, width: int
#     ) -> None:
#         super().__init__(name=name, storage=storage)
#         self._width = width
#         self._height = height
#
#     @property
#     def height(self) -> int:
#         """
#         Image height in pixels.
#         """
#
#         return self._height
#
#     @property
#     def width(self) -> int:
#         """
#         Image width in pixels.
#         """
#
#         return self._width
