import typing as t

from sqlmodel import Field

# from sqlmodel import select
from sqlmodel import SQLModel

from acb.config import import_adapter
from acb.depends import depends
from inflection import underscore
from sqlalchemy.ext.declarative import declared_attr
from ulid import ULID

Sql, SqlSettings = import_adapter()


class SqlModel(SQLModel):
    __table_args__ = {"extend_existing": True}
    __mapper_args__ = {"always_refresh": True}
    id: t.Optional[ULID] = Field(default_factory=ULID, primary_key=True)

    # @property  # hybrid
    # def date_created(self) -> arrow.Arrow:
    #     return arrow.get(ULID(self.id).timestamp)

    @declared_attr
    def __tablename__(cls) -> t.Any:  # type: ignore
        return underscore(cls.__name__)

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    @depends.inject
    async def save(self, sql: Sql = depends()) -> None:  # type: ignore
        async with sql.get_session() as session:
            session.add(self)
            await session.commit()
