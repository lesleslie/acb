import typing as t
from calendar import isleap, monthrange
from datetime import date, datetime, timedelta
from itertools import chain
from pathlib import Path
from re import search

import arrow
from anyio import Path as AsyncPath
from pydantic import BaseModel, ConfigDict, create_model
from sqlmodel import SQLModel, select
from acb.actions.encode import load
from acb.adapters import import_adapter
from acb.config import Config
from acb.depends import depends
from acb.logger import Logger

Sql, Storage = import_adapter()


class SqlBackupUtils(BaseModel):
    storage: Storage = depends()
    config: Config = depends()
    backup_path: Path | None = None

    @staticmethod
    def get_timestamp(name: str) -> str | None:
        pattern = "(.*)(-)(?P<timestamp>[\\d]{10})(-)(.*)"
        match = search(pattern, name)
        return match.group("timestamp") or None

    def get_files(self) -> t.Generator[t.Any, t.Any, t.Any]:
        blobs = self.storage.sql.list()
        if blobs is not None:
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
        return timestamp in self.get_timestamps()

    def get_path(
        self,
        class_name: str = "",
        timestamp: t.Any = arrow.utcnow().timestamp,
    ) -> Path:
        self.backup_path = Path(
            f"{self.config.app.name}-{int(timestamp)}-{class_name}.json",
        )
        return self.backup_path


class SqlBackupDates(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    today: arrow.Arrow = arrow.utcnow()
    white_list: list[int] = []
    black_list: list[int] = []
    dates: list[int] = []

    def __init__(self, dates: list[int] | None = None, **data: t.Any) -> None:
        super().__init__(**data)
        self.dates = sorted(dates, reverse=True) if dates else []
        self.process()

    def get_last_month_length(self) -> int:
        return monthrange(self.today.year, self.today.shift(months=-1).month)[1]

    def get_last_year_length(self) -> int:
        first_day = date(self.today.year, 1, 1)
        last_day = first_day - timedelta(days=1)
        return 366 if isleap(last_day.year) else 365

    def filter_dates(
        self,
        dates: list[t.Any],
        period: str = "week",
    ) -> t.Generator[t.Any, t.Any, t.Any]:
        reference = self.today.int_timestamp
        method_mapping: dict[str, t.Any] = {
            "week": lambda obj: obj.isocalendar()[1],
            "month": lambda obj: obj.month,
            "year": lambda obj: obj.year,
        }
        for dt in dates:
            comp_date = datetime.fromtimestamp(int(dt))
            method = method_mapping.get(period)
            if method is not None:
                comparison = method(comp_date)
                ref_date = datetime.fromtimestamp(reference)
                if comparison != method(ref_date):
                    reference = dt
                    yield dt

    def process(self) -> None:
        last_w = self.today.shift(days=-7).int_timestamp
        last_m = self.today.shift(days=-self.get_last_month_length()).int_timestamp
        last_y = self.today.shift(days=-self.get_last_year_length()).int_timestamp
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
            ),
        )
        diff_as_list = [d for d in self.dates if d not in self.white_list]
        self.black_list.extend(sorted(diff_as_list, reverse=True))


class SqlBackup(SqlBackupDates, SqlBackupUtils):
    sql: Sql = depends()
    logger: Logger = depends()
    do_not_backup: list[str] = []
    models: list[t.Any] = []
    sure_delete: bool = False

    @staticmethod
    def show() -> list[t.Any]:
        schema = getattr(SQLModel.metadata, "schema", None) or []
        return [m for m in schema if isinstance(m, type) and issubclass(m, SQLModel)]

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

    async def backup(self, class_name: str, data: t.Any, timestamp: int) -> None:
        path = self.get_path(class_name=class_name, timestamp=timestamp)
        await self.storage.sql.save(data, path)

    async def save(self) -> None:
        data = await self.get_data()
        timestamp = arrow.utcnow().int_timestamp
        for class_name in data:
            path = self.get_path(class_name=class_name, timestamp=timestamp)
            self.logger.debug(f"Backing up - {path.name}")
            await self.backup(
                class_name=class_name,
                data=data[class_name],
                timestamp=timestamp,
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
        timestamp = max(timestamps)
        adate = arrow.Arrow.fromtimestamp(timestamp)
        self.logger.info(f"Last backup: {adate.format('MM-DD-YYYY HH:mm:ss ZZ')}")
        return timestamp

    async def restore_rows(self, path: AsyncPath) -> t.Any:
        contents = await self.storage.sql.read(path)
        pattern = "-(\\D+).json"
        model = search(pattern, path.name).group(1)
        if contents:
            loaded_model = create_model(
                model,
                __base__=SQLModel,
                __cls_kwargs__={"table": True},
                **t.cast("dict[str, t.Any]", load.json(contents)),
            )
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
            if timestamp in b.name
        ]
        when = arrow.Arrow.fromtimestamp(timestamp).humanize()
        self.logger.info(f"Restoring backup from {when}.....")
        for path in paths:
            self.logger.debug(f"\tRestoring:  {path.name}")
            await self.restore_rows(path)

    def delete_backups(self, delete_list: list[str]) -> None:
        delete_me = self.storage.sql.delete(delete_list)
        if delete_me:
            for name in delete_list:
                self.logger.debug(f"Deleted {name}")

    def clean(self) -> bool:
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
            if getattr(self.config.debug, "sql", False):
                for f in self.by_timestamp(str(timestamp)):
                    self.logger.debug(f)
        delete_list = []
        self.logger.debug(f"==> {len(black_list)} backups will be deleted:")
        for timestamp in black_list:
            date_formatted = arrow.Arrow.fromtimestamp(timestamp).humanize()
            self.logger.debug(f"ID: {timestamp} (from {date_formatted})")
            for f in self.by_timestamp(str(timestamp)):
                if getattr(self.config.debug, "database", False):
                    self.logger.debug(f)
                delete_list.append(f)
        self.delete_backups(delete_list)
        return True

    async def run(self) -> None:
        if not self.config.deployed:
            last_backup = self.get_last_backup()
            if getattr(self.config.debug, "database", False) and self.sure_delete:
                blobs = [b.name for b in self.storage.sql.list()]
                for b in blobs:
                    self.storage.sql.delete(b)
                last_backup = None
            if not last_backup:
                await self.save()
            elif (
                last_backup
                and getattr(self.config.debug, "database", False)
                and (not self.sure_delete)
            ):
                self.logger.info(f"Restoring last backup - {last_backup}")
                await self.restore_backup(last_backup)
            self.clean()
            self.logger.info("Backups complete.")


backup = SqlBackup()
