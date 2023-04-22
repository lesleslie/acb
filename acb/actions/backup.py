import asyncio
from calendar import isleap
from calendar import monthrange
from concurrent.futures import as_completed
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import date
from datetime import datetime
from datetime import timedelta
from itertools import chain
from pathlib import Path
from re import search
from typing import Any

# from actions.load import load
from adapters.database import async_session
# from re import sub
# from adapters.database_ import async_session
from adapters.database import db_engine
from config import ac
from config import debug
from models import AppModelBase
from resize import clear_resized_images
# from sqlalchemy.exc import IntegrityError
# from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.serializer import dumps as sdumps
from sqlalchemy.ext.serializer import loads as sloads
from sqlmodel import select
from sqlmodel import SQLModel
# from sqlalchemy.orm.exc import UnmappedInstanceError
from storage import stor

import arrow
# from plugins import plugin_source
from pydantic import BaseModel

logger = asyncio.run(get_app_logger(__file__))(debug)

sure_delete = False


class BackupDbUtils(BaseModel):
    @staticmethod
    def get_timestamp(name):
        pattern = r"(.*)(-)(?P<timestamp>[\d]{10})(-)(.*)"
        match = search(pattern, name)
        return match.group("timestamp") if match else False

    def get_files(self):
        blobs = stor.db.list()
        for blob in blobs:
            if self.get_timestamp(blob.name):
                yield blob.name

    def get_timestamps(self):
        if not self.files:
            self.files = tuple(self.get_files())

        different_timestamps = list()
        for name in self.files:
            timestamp = self.get_timestamp(name)
            if timestamp and timestamp not in different_timestamps:
                different_timestamps.append(timestamp)
        return different_timestamps

    def by_timestamp(self, timestamp):
        if not self.files:
            self.files = tuple(self.get_files())

        for name in self.files:
            if timestamp == self.get_timestamp(name):
                yield name

    def valid(self, timestamp):
        if timestamp and timestamp in self.get_timestamps():
            return True
        # print('==> Invalid id. Use "history" to list existing downloads')
        return False

    def get_path(self, class_name, timestamp=None):
        timestamp = timestamp or arrow.utcnow().int_timestamp
        self.backup_path = Path(f"{ac.app.name}-{timestamp}-{class_name}.sqla")
        return self.backup_path


class BackupDbDates(BaseModel):
    today = arrow.utcnow()
    white_list = []
    black_list = []
    dates = list()

    def __init__(self, dates=None, **data: Any):
        super().__init__(**data)
        self.dates = sorted(dates, reverse=True) if dates else []
        self.run()  # feed self.white_list & self.black_list

    def get_last_month_length(self):
        return monthrange(self.today.year, self.today.shift(months=-1).month)[1]

    def get_last_year_length(self):
        first_day = date(self.today.year, 1, 1)  # current year
        last_day = first_day - timedelta(days=1)  # last year
        return 366 if isleap(last_day.year) else 365

    def filter_dates(self, dates, period):
        reference = self.today.int_timestamp
        method_mapping = {
            "week": lambda obj: getattr(obj, "isocalendar")()[1],
            "month": lambda obj: getattr(obj, "month"),
            "year": lambda obj: getattr(obj, "year"),
        }
        for date in dates:
            comp_date = datetime.fromtimestamp(int(date))
            comparison = method_mapping.get(period)(comp_date)
            ref_date = datetime.fromtimestamp(int(reference))
            if comparison != method_mapping.get(period)(ref_date):
                reference = date
                yield date

    def run(self):
        last_w = self.today.shift(days=-7).int_timestamp
        last_m = self.today.shift(days=-(self.get_last_month_length())).int_timestamp
        last_y = self.today.shift(days=-(self.get_last_year_length())).int_timestamp
        backups_week = []
        backups_month = []
        backups_year = []
        backups_older = []
        for timestamp in self.dates:
            if int(timestamp) >= last_w:
                backups_week.append(timestamp)
            elif int(timestamp) >= last_m:
                backups_month.append(timestamp)
            elif int(timestamp) >= last_y:
                backups_year.append(timestamp)
            else:
                backups_older.append(timestamp)
        self.white_list.extend(
            chain(
                backups_week,
                self.filter_dates(backups_month, "week"),
                self.filter_dates(backups_year, "month"),
                self.filter_dates(backups_older, "year"),
            )
        )
        diff_as_list = [d for d in self.dates if d not in self.white_list]
        self.black_list.extend(sorted(diff_as_list, reverse=True))


class BackupDb(BackupDbDates, BackupDbUtils):
    do_not_backup = list()
    models = list()

    def show(self):
        return [
            m
            for m in SQLModel.metadata.schema
            if isinstance(m, type) and issubclass(m, AppModelBase)
        ]

    def get_mapped_classes(self):
        self.add_subclasses(AppModelBase)
        return self.models

    def add_subclasses(self, model):
        if model.__subclasses__():
            for submodel in model.__subclasses__():
                self.add_subclasses(submodel)
        else:
            self.models.append(model)

    def get_data(self):
        data = dict()
        async with async_session() as session:
            for model in self.get_mapped_classes():
                query = select(model)
                results = session.exec(query)
                data[model.__name__] = sdumps(results)
        return data

    def parse_data(self, contents):
        with suppress(AttributeError):
            contents = sloads(
                contents,
                metadata=SQLModel.metadata,
                engine=db_engine,
                scoped_session=async_session(),
            )
        return contents

    async def backup(self, class_name, data, now):
        path = self.get_path(class_name, now)
        await stor.db.save(data, path)

    async def save(self):
        data = self.get_data()
        now = arrow.utcnow().int_timestamp

        for class_name in data.keys():
            path = self.get_path(class_name, now)
            logger.debug(f"Backing up - {path.name}")
            await self.backup(class_name, data[class_name], now)

    def get_backups(self):
        timestamps = self.get_timestamps()
        backups = dict()
        for timestamp in timestamps:
            adate = arrow.Arrow.fromtimestamp(timestamp)
            date_formatted = adate.humanize()
            backups[timestamp] = []
            fps = [Path(b) for b in stor.db.list() if timestamp in b.name]
            for fp in fps:
                if stor.db.exists(fp):
                    backups[timestamp].append(fp.name)
            adate_formatted = adate.format("MM-DD-YYYY HH:mm:ss ZZ")
            logger.debug(f"{date_formatted} ==> {adate_formatted}:")
        return sorted(backups, reverse=True)

    def get_last_backup(self):
        timestamps = self.get_timestamps()
        if not len(timestamps):
            return False
        timestamp = sorted(timestamps, reverse=True)[0]
        adate = arrow.Arrow.fromtimestamp(timestamp)
        logger.info(f"Last backup: {adate.format('MM-DD-YYYY HH:mm:ss ZZ')}")
        return timestamp

    def restore_rows(self, path: Path):
        stor.db.get(path)
        # try:
        #     model = search("-(\D+).sqla", path.name).group(1)
        #     if contents:
        #         contents = sub(
        #             b"_sp.{31,32}\.",
        #             bytes(f"{plugin_source.spaceid}.", encoding="utf8"),
        #             contents,
        #         )
        #         is_pickled = load.pickle(contents)
        #         if not isinstance(is_pickled, list):
        #             contents = is_pickled
        #         loaded = self.parse_data(contents)
        #         if "app" in path.stem:
        #             loaded = [loaded[0]]
        #         if loaded != []:
        #             for m in self.show():
        #                 m_name = m.__name__
        #                 if m_name == model:
        #                     self.async_session.query(m).delete()
        #             self.async_session.commit()
        #             for row in loaded:
        #                 try:
        #                     with suppress(UnmappedInstanceError):
        #                         self.async_session.merge(row)
        #                     self.async_session.commit()
        #                 except (IntegrityError, InvalidRequestError) as err:
        #                     self.async_session.rollback()
        #                     fails.append(row)
        #             status = "partially" if len(fails) else "totally"
        #             status = f"\t==> {path.name} {status} restored{':' if len(fails) else '.'}"
        #         else:
        #             status = f"\t!=> No or bad data for {model}."
        #     else:
        #         status = f"\t!=> File {path.name} does not exist."
        # except Exception as err:
        #     status = err
        # return status, fails

    def restore_backup(self, timestamp):
        paths = [Path(b.name) for b in stor.db.list() if timestamp in b.name]
        when = arrow.Arrow.fromtimestamp(timestamp).humanize()
        logger.info(f"Restoring backup from {when}.....")
        with ThreadPoolExecutor(max_workers=5) as executor:
            all_tasks = []
            for path in paths:
                logger.debug(f"\tRestoring:  {path.name}")
                all_tasks.append(executor.submit(self.restore_rows, path))

            for future in as_completed(all_tasks):
                status, fails = future.result()
                for f in fails:
                    logger.error(f"\t\tRestore of {f} failed!")

    def delete_backups(self, delete_list):
        delete_me = stor.db.delete(delete_list)
        if delete_me:
            for name in delete_list:
                logger.debug(f"Deleted {name}")

    def clean(self):
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
            logger.debug("==> No backup to be deleted.")
            return True

        logger.debug(f"==> {len(white_list)} backups will be kept:")
        for timestamp in white_list:
            date_formatted = arrow.Arrow.fromtimestamp(timestamp).humanize()
            logger.debug(f"ID: {timestamp} (from {date_formatted})")
            if debug.database:
                for f in self.by_timestamp(timestamp):
                    logger.debug(f)

        delete_list = list()
        logger.debug(f"==> {len(black_list)} backups will be deleted:")
        for timestamp in black_list:
            date_formatted = arrow.Arrow.fromtimestamp(timestamp).humanize()
            logger.debug(f"ID: {timestamp} (from {date_formatted})")
            for f in self.by_timestamp(timestamp):
                if debug.database:
                    logger.debug(f)
                delete_list.append(f)

        self.delete_backups(delete_list)
        return "cleandb"

    def run(self):
        if not ac.app.is_deployed:
            last_backup = self.get_last_backup()
            if debug.database and sure_delete:
                blobs = [b.name for b in stor.db.list()]
                for b in blobs:
                    stor.db.delete(b)
                clear_resized_images()
                last_backup = None
            if not last_backup:
                self.save()
            elif last_backup and debug.database and not sure_delete:
                logger.info(f"Restoring last backup - {last_backup}")
                self.restore_backup(last_backup)
            self.clean()
            logger.info("Backups complete.")


backup_db = BackupDb()

if __name__ == "__main__":
    backup_db.run()
