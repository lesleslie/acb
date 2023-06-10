# import typing as t
# from pathlib import Path
#
# from acb.actions.log import logger
#
# from acb.actions.debug import ic
# from acb.config import AppSettings
#
# # from aiologger import Logger
# from acb.config import tmp
# from aiopath import AsyncPath
# from google.cloud.exceptions import NotFound
# from pathy import Pathy
# from pathy import set_client_params
# from pathy import use_fs_cache
# from pydantic import BaseModel
# from pydantic import BaseSettings
#
#
# # from gcloud.aio.storage import Storage
#
# # from google.cloud.storage import Blob
# # from google.cloud.storage import Bucket
# # from actions.compress import compress
# # from actions.compress import decompress
# # from cloudpathlib import CloudPath
#
#
# # Credentials for upload to Cloud Storage
# # CORS policy for upload bucket
#
# #
# # upload-cors.json
# #
# # [
# #     {
# #       "origin": ["*"],
# #       "method": ["*"],
# #       "responseHeader": ["*"],
# #       "maxAgeSeconds": 600
# #     }
# # ]
#
#
# # async with Storage() as client:
# #     ...
#
#
# class StorageSettings(AppSettings):
#     class Bucket(BaseSettings):
#         media = "7e1028ec-569c-4aad-ac5c-824aa56382d6"
#         upload = "3f3a5536-e1d7-430a-a478-39794fa864a3"
#
#     class Cache(BaseSettings):
#         control = ac.cache.media_control
#         timeout = ac.cache.media_timeout
#
#     bucket = Bucket()
#     cache = Cache()
#
#
# class CloudStorageBucket(BaseModel):
#     prefix: str = ac.app.name
#     cache_control: t.Optional[str] = None
#     user_project: str = ac.app.name  # used for billing
#     bucket: t.Optional[str]
#     path: t.Optional[Pathy]
#     logger: Logger = None
#     ic: t.Any = None
#     pf: t.Any = None
#
#     class Config:
#         arbitrary_types_allowed = True
#
#     def __init__(self, bucket: str, prefix: str = None, **data: t.Any) -> None:
#         super().__init__(**data)
#
#     self.prefix = prefix if prefix else self.prefix
#     self.bucket = (
#         f"splashstand-{bucket}"
#         if bucket not in [ac.storage.bucket.media, ac.storage.bucket.upload]
#         else bucket
#     )
#     self.path = Pathy(f"gs://{self.bucket}/{self.prefix}/")
#
#     def save(self, obj_path: AsyncPath, data: t.Any) -> None:
#         self.get_path(obj_path)
#
#     logger.debug(f"Saving {stor_path}...")
#     if isinstance(data, bytes):
#         stor_path.write_bytes(data)
#     else:
#         stor_path.write_text(data)
#     logger.debug(f"Saved - {stor_path}")
#
#     def get(self, obj_path: AsyncPath):
#         stor_path = self.get_path(obj_path)
#         logger.debug(f"Getting {stor_path}...")
#         try:
#             data = stor_path.read_text()
#         except NotFound:
#             raise FileNotFoundError
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
#     def get_path(self, obj_path: AsyncPath) -> Path:
#         ic(self.path / "/".join(obj_path.parts[1:]))
#         return self.path / "/".join(obj_path.parts[1:])
#
#     async def get_url(self, obj_path: AsyncPath):
#         return str(self.get_path(obj_path).resolve()).replace(
#             "gs://", "https://storage.cloud.google.com/"
#         )
#
#
# class AppStorage:
#     logger: t.Optional[Logger]
#     stock_media = CloudStorageBucket(ac.storage.bucket.media, "stock")
#     media = CloudStorageBucket(ac.storage.bucket.media)
#     upload = CloudStorageBucket(ac.storage.bucket.upload)
#     database = CloudStorageBucket("database")
#     settings = CloudStorageBucket("settings")
#     plugins = CloudStorageBucket("plugins")
#     migrations = CloudStorageBucket("migrations")
#     theme = CloudStorageBucket("theme")
#
#     async def init(self) -> None:
#         set_client_params("gs", project=ac.app.project)
#
#     use_fs_cache(root=tmp / "storage")
#
#     for bucket in [
#         b for b in self.__dict__.values() if isinstance(b, CloudStorageBucket)
#     ]:
#         ic(type(bucket))
#         logger.debug(f"{bucket.__name__.title()} initialized.")
#     logger.info("Storage initialized.")
#
#
# stor = AppStorage()

# return blob(f"{url_pre}/{url_path.name}").public_url
# return f"https://storage.cloud.google.com/{stor.media.name}/{ac.app_name}/{path}"


# CORS policy for upload bucket
#
# [
#     {
#       "origin": ["*"],
#       "method": ["*"],
#       "responseHeader": ["*"],
#       "maxAgeSeconds": 600
#     }
# ]


# storage_backups = {}

# for b in list(storage_buckets)[:-2]:
#     storage_backups.update({f"{b}_backup": path = f"splashstand-backup-{b}")})
#
#     all_buckets = {**storage_buckets, **storage_backups}
#
#     if __name__ == "__main__":
#         pass
