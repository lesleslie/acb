import typing as t
from contextlib import asynccontextmanager
from functools import cached_property

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel

from acb.config import ac
from acb.config import gen_password
from acb.config import Settings
from acb.logger import debug
from acb.logger import logger
from aioconsole import ainput
from aioconsole import aprint
from pydantic import SecretStr
from sqlalchemy import inspect
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_utils import create_database
from sqlalchemy_utils import database_exists
from sqlalchemy_utils import drop_database


# from calendar import isleap
# from calendar import monthrange
# from datetime import date
# from datetime import datetime
# from datetime import timedelta
# from itertools import chain
# from re import search
# import arrow
# from acb.adapters import storage
# from acb.depends import depends
# from aiopath import AsyncPath
# from pydantic import BaseModel
# from sqlalchemy.exc import IntegrityError
# from sqlalchemy.exc import InvalidRequestError
# from sqlalchemy.ext.serializer import dumps as sdumps
# from sqlalchemy.ext.serializer import loads as sloads
# from acb.actions import dump
# from acb.actions import load
# from inflection import underscore
# # from sqlalchemy.ext.hybrid import hybrid_property
# from sqlalchemy.orm.exc import UnmappedInstanceError
# from sqlalchemy.orm import declared_attr
# from sqlmodel import Field
# from ulid import ULID
# from sqlmodel import select
# from sqlmodel import SQLModel


class SqlBaseSettings(Settings):
    driver: str
    async_driver: str
    port: int
    pool_pre_ping: bool = False
    poolclass: t.Optional[t.Any] = None
    host: SecretStr = SecretStr("127.0.0.1")
    user: SecretStr = SecretStr("root")
    password: SecretStr = SecretStr(gen_password(10))
    _url: t.Optional[URL] = None
    _async_url: t.Optional[URL] = None
    engine_kwargs: t.Optional[dict[str, t.Any]] = {}

    def model_post_init(self, __context: t.Any) -> None:
        url_kwargs = dict(
            drivername=self.driver,
            username=self.user.get_secret_value(),
            password=self.password.get_secret_value(),
            host="127.0.0.1" if not ac.deployed else self.host.get_secret_value(),
            port=self.port,
            database=ac.app.name,
        )
        self._url = URL.create(**url_kwargs)  # type: ignore
        async_url_kwargs = dict(drivername=self.async_driver)
        self._async_url = URL.create(**(url_kwargs | async_url_kwargs))  # type: ignore


class SqlBase:
    @cached_property
    def engine(self) -> AsyncEngine:
        return create_async_engine(ac.sql._async_url, **ac.sql.engine_kwargs)

    @cached_property
    def session(self) -> AsyncSession:
        return AsyncSession(self.engine, expire_on_commit=False)

    async def create(self, demo: bool = False) -> None:
        exists = database_exists(ac.sql._url)
        if exists:
            logger.debug("Database exists")

        if ac.debug.sql and not (ac.deployed or ac.debug.production) and exists:
            msg = (
                "\n\nRESETTING THE DATABASE WILL CAUSE ALL OF YOUR"
                " CURRENT DATA TO BE LOST!\n"
            )
            if demo:
                msg = (
                    "\nBy running this module,\n\nYOUR DATABASE WILL BE DELETED AND "
                    "REPLACED WITH DEMO DATA.\nALL OF YOUR CURRENT DATA WILL BE LOST!\n"
                )
            await aprint(msg)
            delete_db = await ainput("Would you like to reset the database? (y/N) ")
            await aprint()
            if delete_db.upper().strip() == "Y":
                drop_database(ac.sql._url)
                logger.warning("Database dropped")
                exists = database_exists(ac.sql._url)
        if not exists:
            create_database(ac.sql._url)
            logger.debug("Database created")

    @asynccontextmanager
    async def get_session(self) -> t.AsyncGenerator[AsyncSession, None]:
        async with self.session as sess:
            yield sess

    @asynccontextmanager
    async def get_conn(self) -> t.AsyncGenerator[AsyncConnection, None]:
        async with self.engine.begin() as conn:
            yield conn

    @staticmethod
    def get_table_names(conn: object) -> list[str]:
        inspector = inspect(conn)
        return inspector.get_table_names() or []

    async def init(self, demo: bool = False) -> None:
        await self.create(demo)
        async with self.get_conn() as conn:
            # if ac.debug.sql:
            #     sql = text("DROP TABLE IF EXISTS alembic_version")
            #     await conn.execute(sql)
            logger.debug("Creating database tables...")

            await conn.run_sync(SQLModel.metadata.create_all)
            if ac.debug.sql:
                table_names = await conn.run_sync(self.get_table_names)
                debug(table_names)
        logger.debug("Database initialized")


# class AppBaseModel(SQLModel):
#     __table_args__ = {"extend_existing": True}
#     __mapper_args__ = {"always_refresh": True}
#     id: t.Optional[ULID] = Field(default_factory=ULID, primary_key=True)
#
#     # @property
#     # def date_created(self) -> arrow.Arrow:
#     #     return arrow.get(ULID(self.id).timestamp)
#
#     @declared_attr
#     def __tablename__(cls):
#         return underscore(cls.__name__)
#
#     class Config:
#         arbitrary_types_allowed = True
#         extra = "allow"
#         json_loads = load.json
#         json_dumps = dump.json
#
#     async def save(self) -> None:
#         async with sql.get_session() as session:
#             session.add(self)
#             await session.commit()


# class BackupDbUtils(BaseModel):
#     storage: storage = depends()
#
#     @staticmethod
#     def get_timestamp(name: str) -> str | None:
#         pattern = r"(.*)(-)(?P<timestamp>[\d]{10})(-)(.*)"
#         match = search(pattern, name)
#         return match.group("timestamp") or None
#
#     def get_files(self):
#         blobs = self.storage.sql.list()
#         for blob in blobs:
#             if self.get_timestamp(blob.name):
#                 yield blob.name
#
#     def get_timestamps(self) -> list[str]:
#         if not self.files:
#             self.files = tuple(self.get_files())
#         different_timestamps = []
#         for name in self.files:
#             timestamp = self.get_timestamp(name)
#             if timestamp and timestamp not in different_timestamps:
#                 different_timestamps.append(timestamp)
#         return different_timestamps
#
#     async def by_timestamp(self, timestamp: int) -> t.Generator:
#         if not self.files:
#             self.files = tuple(self.get_files())
#         for name in self.files:
#             if timestamp == self.get_timestamp(name):
#                 yield name
#
#     def valid(self, timestamp: str) -> bool:
#         if timestamp in self.get_timestamps():
#             return True
#         # print('==> Invalid id. Use "history" to list existing downloads')
#         return False
#
#     def get_path(self, class_name: str,
#           timestamp: t.Optional[int] = None) -> AsyncPath:
#         timestamp = timestamp or arrow.utcnow().int_timestamp
#         self.backup_path = AsyncPath(f"{ac.app.name}-{timestamp}-{class_name}.sqla")
#         return self.backup_path
#
#
# class BackupDbDates(BaseModel, arbitrary_types_allowed=True):
#     today: arrow.Arrow = arrow.utcnow()
#     white_list: list[int] = []
#     black_list: list[int] = []
#     dates: list[int] = []
#
#     def __init__(self, dates=None, **data: t.Any) -> None:
#         super().__init__(**data)
#         self.dates = sorted(dates, reverse=True) if dates else []
#         self.run()  # feed self.white_list & self.black_list
#
#     def get_last_month_length(self) -> int:
#         return monthrange(self.today.year, self.today.shift(months=-1).month)[1]
#
#     def get_last_year_length(self):
#         first_day = date(self.today.year, 1, 1)  # current year
#         last_day = first_day - timedelta(days=1)  # last year
#         return 366 if isleap(last_day.year) else 365
#
#     def filter_dates(
#         self, dates: list[t.Any], period: str = "week"
#     ) -> t.Generator[t.Any, t.Any, t.Any]:
#         reference = self.today.int_timestamp
#         method_mapping: dict[str, t.Any()] = {
#             "week": lambda obj: getattr(obj, "isocalendar")()[1],
#             "month": lambda obj: getattr(obj, "month"),
#             "year": lambda obj: getattr(obj, "year"),
#         }
#         for dt in dates:
#             comp_date = datetime.fromtimestamp(int(dt))
#             comparison = method_mapping.get(period)(comp_date)
#             ref_date = datetime.fromtimestamp(reference)
#             if comparison != method_mapping.get(period)(ref_date):
#                 reference = dt
#                 yield dt
#
#     def run(self) -> None:
#         last_w = self.today.shift(days=-7).int_timestamp
#         last_m = self.today.shift(days=-(self.get_last_month_length())).int_timestamp
#         last_y = self.today.shift(days=-(self.get_last_year_length())).int_timestamp
#         backups_week = []
#         backups_month = []
#         backups_year = []
#         backups_older = []
#         for timestamp in self.dates:
#             if timestamp >= last_w:
#                 backups_week.append(timestamp)
#             elif timestamp >= last_m:
#                 backups_month.append(timestamp)
#             elif timestamp >= last_y:
#                 backups_year.append(timestamp)
#             else:
#                 backups_older.append(timestamp)
#         self.white_list.extend(
#             chain(
#                 backups_week,
#                 self.filter_dates(backups_month),
#                 self.filter_dates(backups_year, "month"),
#                 self.filter_dates(backups_older, "year"),
#             )
#         )
#         diff_as_list = [d for d in self.dates if d not in self.white_list]
#         self.black_list.extend(sorted(diff_as_list, reverse=True))


# class BackupDb(BackupDbDates, BackupDbUtils):
#     do_not_backup: list = []
#     models: list = []
#     sql: SqlBase = depends()
#     sure_delete: bool = False
#
#     def show(self):
#         return [
#             m
#             for m in SQLModel.metadata.schema
#             if isinstance(m, type) and issubclass(m, AppBaseModel)
#         ]
#
#     def get_mapped_classes(self) -> list[str]:
#         self.add_subclasses(AppBaseModel)
#         return self.models
#
#     def add_subclasses(self, model) -> None:
#         if model.__subclasses__():
#             for submodel in model.__subclasses__():
#                 self.add_subclasses(submodel)
#         else:
#             self.models.append(model)
#
#     async def get_data(self) -> dict[str, str]:
#         data = {}
#         async with self.session() as session:
#             for model in self.get_mapped_classes():
#                 query = select(model)
#                 results = session.exec(query)
#                 data[model.__name__] = sdumps(results)
#         return data
#
#     def parse_data(self, contents) -> bytes:
#         with suppress(AttributeError):
#             contents = sloads(
#                 contents,
#                 metadata=SQLModel.metadata,
#                 engine=self.sql.engine,
#                 scoped_session=self.sql.session(),
#             )
#         return contents
#
#     async def backup(self, class_name: str, data, now) -> None:
#         path = self.get_path(class_name, now)
#         await self.storage.sql.save(data, path)
#
#     async def save(self) -> None:
#         data = await self.get_data()
#         now = arrow.utcnow().int_timestamp
#
#         for class_name in data.keys():
#             path = self.get_path(class_name, now)
#             logger.debug(f"Backing up - {path.name}")
#             await self.backup(class_name, data[class_name], now)
#
#     async def get_backups(self) -> list[str]:
#         timestamps = self.get_timestamps()
#         backups = {}
#         for timestamp in timestamps:
#             adate = arrow.Arrow.fromtimestamp(timestamp)
#             date_formatted = adate.humanize()
#             backups[timestamp] = []
#             fps = [
#                 AsyncPath(b)
#                 async for b in self.storage.sql.list()
#                 if timestamp in b.name
#             ]
#             for fp in fps:
#                 if await self.storage.sql.exists(fp):
#                     backups[timestamp].append(fp.name)
#             adate_formatted = adate.format("MM-DD-YYYY HH:mm:ss ZZ")
#             logger.debug(f"{date_formatted} ==> {adate_formatted}:")
#         return sorted(backups, reverse=True)
#
#     def get_last_backup(self) -> str | bool:
#         timestamps = self.get_timestamps()
#         if not timestamps:
#             return False
#         timestamp = sorted(timestamps, reverse=True)[0]
#         adate = arrow.Arrow.fromtimestamp(timestamp)
#         logger.info(f"Last backup: {adate.format('MM-DD-YYYY HH:mm:ss ZZ')}")
#         return timestamp
#
#     async def restore_rows(self, path: AsyncPath) -> tuple[str, list]:
#         contents = await self.storage.sql.get(path)
#         fails = []
#         try:
#             model = search("-(\D+).sqla", path.name).group(1)
#             if contents:
#                 # contents = sub(
#                 #     b"_sp.{31,32}\.",
#                 #     bytes(f"{plugin_source.spaceid}.", encoding="utf8"),
#                 #     contents,
#                 # )
#                 is_pickled = load.pickle(contents)
#                 if not isinstance(is_pickled, list):
#                     contents = is_pickled
#                 loaded = self.parse_data(contents)
#                 if "app" in path.stem:
#                     loaded = [loaded[0]]
#                 if loaded != []:
#                     for m in self.show():
#                         m_name = m.__name__
#                         if m_name == model:
#                             self.async_session.query(m).delete()
#                     await self.session.commit()
#                     for row in loaded:
#                         try:
#                             with suppress(UnmappedInstanceError):
#                                 self.async_session.merge(row)
#                             await self.session.commit()
#                         except (IntegrityError, InvalidRequestError):
#                             self.async_session.rollback()
#                             fails.append(row)
#                     status = "partially" if fails else "totally"
#                     status = (
#                         f"\t==> {path.name} {status} "
#                         f"restored{':' if fails else '.'}"
#                     )
#                 else:
#                     status = f"\t!=> No or bad data for {model}."
#             else:
#                 status = f"\t!=> File {path.name} does not exist."
#         except Exception as err:
#             status = err
#         return status, fails
#
#     async def restore_backup(self, timestamp: str) -> None:
#         paths = [
#             AsyncPath(b.name)
#             async for b in self.storage.sql.list()
#             if (timestamp in b.name)
#         ]
#         when = arrow.Arrow.fromtimestamp(timestamp).humanize()
#         logger.info(f"Restoring backup from {when}.....")
#         for path in paths:
#             logger.debug(f"\tRestoring:  {path.name}")
#             status, fails = await self.restore_rows(path)
#             logger.info(status)
#             for f in fails:
#                 logger.error(f"\t\tRestore of {f} failed!")
#
#     def delete_backups(self, delete_list: list[str]) -> None:
#         delete_me = self.storage.sql.delete(delete_list)
#         if delete_me:
#             for name in delete_list:
#                 logger.debug(f"Deleted {name}")
#
#     def clean(self) -> str | bool:
#         """
#         Remove a series of backup files based on the following rules:
#         * Keeps all the backups from the last 7 days
#         * Keeps the most recent backup from each week of the last month
#         * Keeps the most recent backup from each month of the last year
#         * Keeps the most recent backup from each year of the remaining years
#         """
#
#         # get black and white list
#         cleaning = BackupDbDates(self.get_timestamps())
#         white_list = cleaning.white_list
#         black_list = cleaning.black_list
#         if not black_list:
#             logger.debug("==> No backup to be deleted.")
#             return True
#
#         logger.debug(f"==> {len(white_list)} backups will be kept:")
#         for timestamp in white_list:
#             date_formatted = arrow.Arrow.fromtimestamp(timestamp).humanize()
#             logger.debug(f"ID: {timestamp} (from {date_formatted})")
#             if ac.debug.database:
#                 for f in self.by_timestamp(timestamp):
#                     logger.debug(f)
#
#         delete_list = []
#         logger.debug(f"==> {len(black_list)} backups will be deleted:")
#         for timestamp in black_list:
#             date_formatted = arrow.Arrow.fromtimestamp(timestamp).humanize()
#             logger.debug(f"ID: {timestamp} (from {date_formatted})")
#             for f in self.by_timestamp(timestamp):
#                 if ac.debug.database:
#                     logger.debug(f)
#                 delete_list.append(f)
#
#         self.delete_backups(delete_list)
#         return "cleandb"
#
#     async def run(self) -> None:
#         if not ac.deployed:
#             last_backup = self.get_last_backup()
#             if ac.debug.database and self.sure_delete:
#                 blobs = [b.name for b in self.storage.sql.list()]
#                 for b in blobs:
#                     self.storage.sql.delete(b)
#                 # clear_resized_images()
#                 last_backup = None
#             if not last_backup:
#                 await self.save()
#             elif last_backup and ac.debug.database and not self.sure_delete:
#                 logger.info(f"Restoring last backup - {last_backup}")
#                 await self.restore_backup(last_backup)
#             self.clean()
#             logger.info("Backups complete.")
#
#
# backup_db = BackupDb()
