import re
import typing as t
from ast import literal_eval

from sqlmodel import Field
from sqlmodel import select
from sqlmodel import SQLModel

import ulid
from acb.adapters.sql import Sql
from acb.depends import depends
from inflection import underscore
from sqlalchemy import ScalarResult
from sqlalchemy.ext.declarative import declared_attr
from acb.adapters.models import Models


class SqlModel(SQLModel, arbitrary_types_allowed=True, extra="allow"):
    __table_args__ = {"extend_existing": True}
    __mapper_args__ = {"always_refresh": True}
    id: t.Optional[t.Any] = Field(
        default_factory=ulid.new, primary_key=True  # type: ignore
    )

    @declared_attr
    def __tablename__(self) -> t.Any:  # type: ignore
        return underscore(self.__name__)

    @depends.inject
    async def save(self, sql: Sql = depends()) -> None:  # type: ignore
        async with sql.get_session() as session:
            session.add(self)
            await session.commit()

    @depends.inject
    async def delete(self, sql: Sql = depends()) -> None:  # type: ignore
        async with sql.get_session() as session:
            session.delete(self)
            await session.commit()

    @depends.inject
    async def query(
        self,
        query: str,
        models: Models = depends(),  # type: ignore
        sql: Sql = depends(),  # type: ignore
    ) -> t.Coroutine[t.Any, t.Any, ScalarResult[t.Any]]:
        async with sql.get_session() as session:
            pattern = r"\s(\w)(\w+)\."
            models = [
                getattr(models, m[0] + m[1])
                for m in re.findall(pattern, query)
                if m[0].isupper()
            ]
            statement = select(self, *models).where(literal_eval(query))  # type: ignore
            results = session.exec(statement)
            return results
