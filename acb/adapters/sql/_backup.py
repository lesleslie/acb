import typing as t
from calendar import isleap
from calendar import monthrange
from datetime import date
from datetime import datetime
from datetime import timedelta
from itertools import chain
from pathlib import Path
from re import search

import arrow
from acb.actions.encode import load
from acb.adapters import import_adapter
from acb.config import Config
from acb.depends import depends
from aiopath import AsyncPath
from pydantic import BaseModel
from pydantic import create_model
from sqlmodel import select
from sqlmodel import SQLModel

# from contextlib import suppress
# from sqlalchemy.exc import IntegrityError
# from sqlalchemy.exc import InvalidRequestError
# from sqlalchemy.orm.exc import UnmappedInstanceError


Logger = import_adapter()
Sql = import_adapter()
Storage = import_adapter()


class SqlBackupUtils(BaseModel):
    storage: Storage = depends()  # type: ignore
    config: Config = depends()  # type: ignore
    backup_path: t.Optional[Path] = None

    @staticmethod
    def get_timestamp(name: str) -> str | None:
        pattern = r"(.*)(-)(?P<timestamp>[\d]{10})(-)(.*)"
        match = search(pattern, name)
        return match.group("timestamp") or None

    def get_files(self) -> t.Generator[t.Any, t.Any, t.Any]:
        blobs = self.storage.sql.list()
        for blob in blobs:
            if self.get_timestamp(blob.name):
                yield blob.name

    def get_timestamps(self) -> list[int]:
        if not self.files:
            self.files = tuple(self.get_files())
        different_timestamps = []
        for name in self.files:
            timestamp = self.get_timestamp(name)
            if timestamp and timestamp not in different_timestamps:
                different_timestamps.append(int(timestamp))
        return different_timestamps

    def by_timestamp(self, timestamp: str) -> t.Generator[t.Any, t.Any, t.Any]:
        if not self.files:
            self.files = tuple(self.get_files())
        for name in self.files:
            if timestamp == self.get_timestamp(name):
                yield name

    def valid(self, timestamp: int) -> bool:
        if timestamp in self.get_timestamps():
            return True
        # print('==> Invalid id. Use "history" to list existing downloads')
        return False

    def get_path(
        self,
        class_name: str = "",
        timestamp: t.Any = arrow.utcnow().timestamp,
    ) -> Path:
        self.backup_path = Path(
            f"{self.config.app.name}-{int(timestamp)}-{class_name}.json"
        )
        return self.backup_path


class SqlBackupDates(BaseModel, arbitrary_types_allowed=True):
    today: arrow.Arrow = arrow.utcnow()
    white_list: list[int] = []
    black_list: list[int] = []
    dates: list[int] = []

    def __init__(self, dates: t.Optional[list[int]] = None, **data: t.Any) -> None:
        super().__init__(**data)
        self.dates = sorted(dates, reverse=True) if dates else []
        self.process()  # feed self.white_list & self.black_list

    def get_last_month_length(self) -> int:
        return monthrange(self.today.year, self.today.shift(months=-1).month)[1]

    def get_last_year_length(self) -> int:
        first_day = date(self.today.year, 1, 1)  # current year
        last_day = first_day - timedelta(days=1)  # last year
        return 366 if isleap(last_day.year) else 365

    def filter_dates(
        self, dates: list[t.Any], period: str = "week"
    ) -> t.Generator[t.Any, t.Any, t.Any]:
        reference = self.today.int_timestamp
        method_mapping: dict[str, t.Any] = {
            "week": lambda obj: getattr(obj, "isocalendar")()[1],  # type: ignore
            "month": lambda obj: getattr(obj, "month"),  # type: ignore
            "year": lambda obj: getattr(obj, "year"),  # type: ignore
        }
        for dt in dates:
            comp_date = datetime.fromtimestamp(int(dt))
            comparison = method_mapping.get(period)(comp_date)
            ref_date = datetime.fromtimestamp(reference)
            if comparison != method_mapping.get(period)(ref_date):
                reference = dt
                yield dt

    def process(self) -> None:
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


class SqlBackup(SqlBackupDates, SqlBackupUtils):
    sql: Sql = depends()  # type: ignore
    logger: Logger = depends()  # type: ignore
    do_not_backup: list[str] = []
    models: list[t.Any] = []
    sure_delete: bool = False

    @staticmethod
    def show() -> list[t.Any]:
        return [
            m
            for m in SQLModel.metadata.schema  # type: ignore
            if isinstance(m, type) and issubclass(m, SQLModel)
        ]

    def get_mapped_classes(self) -> list[t.Any]:
        self.add_subclasses(SQLModel)
        return self.models

    def add_subclasses(self, model: t.Any) -> None:
        if model.__subclasses__():
            for submodel in model.__subclasses__():
                self.add_subclasses(submodel)
        else:
            self.models.append(model)

    async def get_data(self) -> dict[str, t.Any]:
        data = {}
        async with self.sql.session() as session:
            for model in self.get_mapped_classes():
                query = select(model)
                results = session.exec(query)
                data[model.__name__] = results.model_dump_to_json()
        return data

    async def backup(self, class_name: str, data: t.Any, timestamp: int) -> t.NoReturn:
        path = self.get_path(class_name=class_name, timestamp=timestamp)
        await self.storage.sql.save(data, path)

    async def save(self) -> t.NoReturn:
        data = await self.get_data()
        timestamp = arrow.utcnow().int_timestamp

        for class_name in data.keys():
            path = self.get_path(class_name=class_name, timestamp=timestamp)
            self.logger.debug(f"Backing up - {path.name}")
            await self.backup(
                class_name=class_name, data=data[class_name], timestamp=timestamp
            )

    async def get_backups(self) -> list[int]:
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

    def get_last_backup(self) -> bool | int:
        timestamps = self.get_timestamps()
        if not timestamps:
            return False
        timestamp = sorted(timestamps, reverse=True)[0]
        adate = arrow.Arrow.fromtimestamp(timestamp)
        self.logger.info(f"Last backup: {adate.format('MM-DD-YYYY HH:mm:ss ZZ')}")
        return timestamp

    async def restore_rows(self, path: AsyncPath) -> t.Any:
        contents = await self.storage.sql.read(path)
        pattern = r"-(\D+).json"
        model = search(pattern, path.name).group(1)
        if contents:
            loaded_model = create_model(
                model,
                __base__=SQLModel,
                __cls_kwargs__={"table": True},
                **load.json(contents),
            ).save()  # type: ignore
            if loaded_model:
                async with self.sql.session() as session:
                    for m in self.show():
                        m_name = m.__name__
                        if m_name == model:
                            await session.query(m).delete()
                    await session.commit()

    async def restore_backup(self, timestamp: int) -> None:
        paths = [
            AsyncPath(b.name)
            async for b in self.storage.sql.list()
            if (timestamp in b.name)
        ]
        when = arrow.Arrow.fromtimestamp(timestamp).humanize()
        self.logger.info(f"Restoring backup from {when}.....")
        for path in paths:
            self.logger.debug(f"\tRestoring:  {path.name}")
            await self.restore_rows(path)
            # status, fails = await self.restore_rows(path)
            # self.logger.info(status)
            # for f in fails:
            #     self.logger.error(f"\t\tRestore of {f} failed!")

    def delete_backups(self, delete_list: list[str]) -> None:
        delete_me = self.storage.sql.delete(delete_list)
        if delete_me:
            for name in delete_list:
                self.logger.debug(f"Deleted {name}")

    def clean(self) -> bool:
        """
        Remove a series of backup files based on the following rules:
        * Keeps all the backups from the last 7 days
        * Keeps the most recent backup from each week of the last month
        * Keeps the most recent backup from each month of the last year
        * Keeps the most recent backup from each year of the remaining years
        """

        # get black and white list
        cleaning = SqlBackupDates(self.get_timestamps())
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
                for f in self.by_timestamp(str(timestamp)):
                    self.logger.debug(f)

        delete_list = []
        self.logger.debug(f"==> {len(black_list)} backups will be deleted:")
        for timestamp in black_list:
            date_formatted = arrow.Arrow.fromtimestamp(timestamp).humanize()
            self.logger.debug(f"ID: {timestamp} (from {date_formatted})")
            for f in self.by_timestamp(str(timestamp)):
                if self.config.debug.database:
                    self.logger.debug(f)
                delete_list.append(f)

        self.delete_backups(delete_list)
        return True

    async def run(self) -> t.NoReturn:
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
            self.clean()
            self.logger.info("Backups complete.")


depends.set(SqlBackup)
