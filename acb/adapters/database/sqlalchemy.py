import typing as t
from contextlib import asynccontextmanager

from actions.log import logger
from actions.log import pf
from aioconsole import ainput
from aioconsole import aprint
from config import ac
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_utils import create_database
from sqlalchemy_utils import database_exists
from sqlalchemy_utils import drop_database
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from addict import Dict as adict
from sqlalchemy import inspect
from sqlalchemy import text


class DatabaseSettings(AppSettings):
    host: str = ac.secrets.database_host if deployed else "127.0.0.1"
    user: str = ac.secrets.database_user
    port = 3306
    async_url: t.Optional[URL]
    url: t.Optional[URL]
    engine_kwargs = dict(poolclass=NullPool, pool_pre_ping=True)

    def __init__(self, **data: t.Any):
        super().__init__(**data)
        self.async_url_kwargs = adict(
            drivername="mysql+asyncmy",
            username=ac.secrets.database_user,
            password=ac.secrets.database_password,
            port=self.port,
            host=self.host,
            database=ac.app.name,
        )
        self.async_url = URL.create(**self.async_url_kwargs)
        self.url_kwargs = adict(drivername="mysql+mysqldb")
        self.url = URL.create(**{**self.async_url_kwargs, **self.url_kwargs})


class Database:
    engine: t.Any = None
    async_session: t.Any = None

    async def create(self, demo=False):
        exists = database_exists(ac.db.url)
        if exists:
            logger.debug("Database exists.")

        if (
            (debug.database or debug.models)
            and not (ac.app.is_deployed or debug.production)
            and exists
        ):
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
            delete_db = await ainput("Would you like to reset the database? (Y/N) ")
            if delete_db:
                drop_database(ac.db.url)
                logger.warning("Database dropped.")
                exists = database_exists(ac.db.url)

        if not exists:
            create_database(ac.db.url)
            logger.info("Database created.")

    async def get_async_session(self) -> AsyncSession:
        async_session = AsyncSession(self.engine, expire_on_commit=False)
        async with async_session as session:
            yield session

    @staticmethod
    def get_table_names(conn):
        inspector = inspect(conn)
        return inspector.get_table_names()

    async def init(self, demo=False):
        self.engine = create_async_engine(ac.db.async_url, **ac.db.engine_kwargs)
        self.async_session = asynccontextmanager(self.get_async_session)
        # print(debug.database)
        # print(type(debug.database))
        await self.create(demo)
        async with self.engine.connect() as conn:
            if debug.database:
                sql = text("DROP TABLE IF EXISTS alembic_version")
                await conn.execute(sql)
            logger.info("Creating database tables...")
            await conn.run_sync(SQLModel.metadata.create_all)
            if debug.models:
                table_names = await conn.run_sync(self.get_table_names)
                await pf(table_names)
            logger.info("Database initialized.")


db = Database()
