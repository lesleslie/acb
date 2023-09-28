import typing as t
from calendar import isleap
from calendar import monthrange
from contextlib import suppress
from datetime import date
from datetime import datetime
from datetime import timedelta
from itertools import chain
from re import search

from sqlmodel import select
from sqlmodel import SQLModel

import arrow
from acb.actions import load
from acb.adapters.logger import Logger
from acb.adapters.sql import Sql
from acb.adapters.sql import SqlModel
from acb.adapters.storage import Storage
from acb.depends import depends
from aiopath import AsyncPath
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.serializer import dumps as sdumps
from sqlalchemy.ext.serializer import loads as sloads
from sqlalchemy.orm.exc import UnmappedInstanceError


# from sqlalchemy.ext.hybrid import hybrid_property


class BackupDbUtils(BaseModel):
    storage: Storage = depends()
    backup_path: t.Optional[AsyncPath] = None

    @staticmethod
    def get_timestamp(name: str) -> str | None:
        pattern = r"(.*)(-)(?P<timestamp>[\d]{10})(-)(.*)"
        match = search(pattern, name)
        return match.group("timestamp") or None

    def get_files(self):
        blobs = self.storage.sql.list()
        for blob in blobs:
            if self.get_timestamp(blob.name):
                yield blob.name

    def get_timestamps(self) -> list[str]:
        if not self.files:
            self.files = tuple(self.get_files())
        different_timestamps = []
        for name in self.files:
            timestamp = self.get_timestamp(name)
            if timestamp and timestamp not in different_timestamps:
                different_timestamps.append(timestamp)
        return different_timestamps

    async def by_timestamp(
        self, timestamp: str
    ) -> t.AsyncGenerator[t.Any, t.Any, t.Any]:
        if not self.files:
            self.files = tuple(self.get_files())
        for name in self.files:
            if timestamp == self.get_timestamp(name):
                yield name

    def valid(self, timestamp: str) -> bool:
        if timestamp in self.get_timestamps():
            return True
        # print('==> Invalid id. Use "history" to list existing downloads')
        return False

    def get_path(self, class_name: str, timestamp: t.Optional[str] = None) -> AsyncPath:
        timestamp = timestamp or arrow.utcnow().timestamp
        self.backup_path = AsyncPath(
            f"{self.config.app.name}-{timestamp}-{class_name}.sqla"
        )
        return self.backup_path


class BackupDbDates(BaseModel, arbitrary_types_allowed=True):
    today: arrow.Arrow = arrow.utcnow()
    white_list: list[int] = []
    black_list: list[int] = []
    dates: list[int] = []

    def __init__(self, dates: t.Optional[list[str]] = None, **data: t.Any) -> None:
        super().__init__(**data)
        self.dates = sorted(dates, reverse=True) if dates else []
        self.run()  # feed self.white_list & self.black_list

    def get_last_month_length(self) -> int:
        return monthrange(self.today.year, self.today.shift(months=-1).month)[1]

    def get_last_year_length(self):
        first_day = date(self.today.year, 1, 1)  # current year
        last_day = first_day - timedelta(days=1)  # last year
        return 366 if isleap(last_day.year) else 365

    def filter_dates(
        self, dates: list[t.Any], period: str = "week"
    ) -> t.Generator[t.Any, t.Any, t.Any]:
        reference = self.today.int_timestamp
        method_mapping: dict[str, t.Any()] = {
            "week": lambda obj: getattr(obj, "isocalendar")()[1],
            "month": lambda obj: getattr(obj, "month"),
            "year": lambda obj: getattr(obj, "year"),
        }
        for dt in dates:
            comp_date = datetime.fromtimestamp(int(dt))
            comparison = method_mapping.get(period)(comp_date)
            ref_date = datetime.fromtimestamp(reference)
            if comparison != method_mapping.get(period)(ref_date):
                reference = dt
                yield dt

    def run(self) -> None:
        last_w = self.today.shift(days=-7).int_timestamp
        last_m = self.today.shift(days=-(self.get_last_month_length())).int_timestamp
        last_y = self.today.shift(days=-(self.get_last_year_length())).int_timestamp
        backups_week = []
        backups_month = []
        backups_year = []
        backups_older = []
        for timestamp in self.dates:
            if timestamp >= last_w:
                backups_week.append(timestamp)
            elif timestamp >= last_m:
                backups_month.append(timestamp)
            elif timestamp >= last_y:
                backups_year.append(timestamp)
            else:
                backups_older.append(timestamp)
        self.white_list.extend(
            chain(
                backups_week,
                self.filter_dates(backups_month),
                self.filter_dates(backups_year, "month"),
                self.filter_dates(backups_older, "year"),
            )
        )
        diff_as_list = [d for d in self.dates if d not in self.white_list]
        self.black_list.extend(sorted(diff_as_list, reverse=True))


class BackupDb(BackupDbDates, BackupDbUtils):
    sql: Sql = depends()
    logger: Logger = depends()
    do_not_backup: list = []
    models: list = []
    sure_delete: bool = False

    @staticmethod
    def show():
        return [
            m
            for m in SQLModel.metadata.schema
            if isinstance(m, type) and issubclass(m, SqlModel)
        ]

    def get_mapped_classes(self) -> list[str]:
        self.add_subclasses(SqlModel)
        return self.models

    def add_subclasses(self, model) -> None:
        if model.__subclasses__():
            for submodel in model.__subclasses__():
                self.add_subclasses(submodel)
        else:
            self.models.append(model)

    async def get_data(self) -> dict[str, str]:
        data = {}
        async with self.session() as session:
            for model in self.get_mapped_classes():
                query = select(model)
                results = session.exec(query)
                data[model.__name__] = sdumps(results)
        return data

    def parse_data(self, contents) -> bytes:
        with suppress(AttributeError):
            contents = sloads(
                contents,
                metadata=SQLModel.metadata,
                engine=self.sql.engine,
                scoped_session=self.sql.session(),
            )
        return contents

    async def backup(self, class_name: str, data: str, now: str) -> None:
        path = self.get_path(class_name, now)
        await self.storage.sql.save(data, path)

    async def save(self) -> None:
        data = await self.get_data()
        now = str(arrow.utcnow().int_timestamp)

        for class_name in data.keys():
            path = self.get_path(class_name, now)
            self.self.logger.debug(f"Backing up - {path.name}")
            await self.backup(class_name, data[class_name], now)

    async def get_backups(self) -> list[str]:
        timestamps = self.get_timestamps()
        backups = {}
        for timestamp in timestamps:
            adate = arrow.Arrow.fromtimestamp(timestamp)
            date_formatted = adate.humanize()
            backups[timestamp] = []
            fps = [
                AsyncPath(b)
                async for b in self.storage.sql.list()
                if timestamp in b.name
            ]
            for fp in fps:
                if await self.storage.sql.exists(fp):
                    backups[timestamp].append(fp.name)
            adate_formatted = adate.format("MM-DD-YYYY HH:mm:ss ZZ")
            self.logger.debug(f"{date_formatted} ==> {adate_formatted}:")
        return sorted(backups, reverse=True)

    def get_last_backup(self) -> str | bool:
        timestamps = self.get_timestamps()
        if not timestamps:
            return False
        timestamp = sorted(timestamps, reverse=True)[0]
        adate = arrow.Arrow.fromtimestamp(timestamp)
        self.logger.info(f"Last backup: {adate.format('MM-DD-YYYY HH:mm:ss ZZ')}")
        return timestamp

    async def restore_rows(self, path: AsyncPath) -> tuple[str, list]:
        contents = await self.storage.sql.get(path)
        fails = []
        try:
            pattern = r"-(\D+).sqla"
            model = search(pattern, path.name).group(1)
            if contents:
                is_pickled = load.pickle(contents)
                if not isinstance(is_pickled, list):
                    contents = is_pickled
                loaded = self.parse_data(contents)
                if "app" in path.stem:
                    loaded = [loaded[0]]
                if loaded:
                    for m in self.show():
                        m_name = m.__name__
                        if m_name == model:
                            self.async_session.query(m).delete()
                    await self.session.commit()
                    for row in loaded:
                        try:
                            with suppress(UnmappedInstanceError):
                                self.async_session.merge(row)
                            await self.session.commit()
                        except (IntegrityError, InvalidRequestError):
                            self.async_session.rollback()
                            fails.append(row)
                    status = "partially" if fails else "totally"
                    status = (
                        f"\t==> {path.name} {status} "
                        f"restored{':' if fails else '.'}"
                    )
                else:
                    status = f"\t!=> No or bad data for {model}."
            else:
                status = f"\t!=> File {path.name} does not exist."
        except Exception as err:
            status = err
        return status, fails

    async def restore_backup(self, timestamp: str) -> None:
        paths = [
            AsyncPath(b.name)
            async for b in self.storage.sql.list()
            if (timestamp in b.name)
        ]
        when = arrow.Arrow.fromtimestamp(timestamp).humanize()
        self.logger.info(f"Restoring backup from {when}.....")
        for path in paths:
            self.logger.debug(f"\tRestoring:  {path.name}")
            status, fails = await self.restore_rows(path)
            self.logger.info(status)
            for f in fails:
                self.logger.error(f"\t\tRestore of {f} failed!")

    def delete_backups(self, delete_list: list[str]) -> None:
        delete_me = self.storage.sql.delete(delete_list)
        if delete_me:
            for name in delete_list:
                self.logger.debug(f"Deleted {name}")

    async def clean(self) -> str | bool:
        """
        Remove a series of backup files based on the following rules:
        * Keeps all the backups from the last 7 days
        * Keeps the most recent backup from each week of the last month
        * Keeps the most recent backup from each month of the last year
        * Keeps the most recent backup from each year of the remaining years
        """

        # get black and white list
        cleaning = BackupDbDates(self.get_timestamps())
        white_list = cleaning.white_list
        black_list = cleaning.black_list
        if not black_list:
            self.logger.debug("==> No backup to be deleted.")
            return True

        self.logger.debug(f"==> {len(white_list)} backups will be kept:")
        for timestamp in white_list:
            date_formatted = arrow.Arrow.fromtimestamp(timestamp).humanize()
            self.logger.debug(f"ID: {timestamp} (from {date_formatted})")
            if self.config.debug.sql:
                async for f in self.by_timestamp(str(timestamp)):
                    self.logger.debug(f)

        delete_list = []
        self.logger.debug(f"==> {len(black_list)} backups will be deleted:")
        for timestamp in black_list:
            date_formatted = arrow.Arrow.fromtimestamp(timestamp).humanize()
            self.logger.debug(f"ID: {timestamp} (from {date_formatted})")
            async for f in self.by_timestamp(str(timestamp)):
                if self.config.debug.database:
                    self.logger.debug(f)
                delete_list.append(f)

        self.delete_backups(delete_list)
        return "cleandb"

    async def run(self) -> None:
        if not self.config.deployed:
            last_backup = self.get_last_backup()
            if self.config.debug.database and self.sure_delete:
                blobs = [b.name for b in self.storage.sql.list()]
                for b in blobs:
                    self.storage.sql.delete(b)
                # clear_resized_images()
                last_backup = None
            if not last_backup:
                await self.save()
            elif last_backup and self.config.debug.database and not self.sure_delete:
                self.logger.info(f"Restoring last backup - {last_backup}")
                await self.restore_backup(last_backup)
            await self.clean()
            self.logger.info("Backups complete.")


backup_db = BackupDb()
