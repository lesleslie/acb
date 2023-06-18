import typing as t

import arrow
from acb.actions import dump
from acb.actions import load
from acb.adapters.database.sqlalchemy import db
from inflection import underscore

# from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declared_attr
from sqlmodel import Field
from sqlmodel import SQLModel
from ulid import ULID


class AppBaseModel(SQLModel):
    __table_args__ = {"extend_existing": True}
    __mapper_args__ = {"always_refresh": True}
    id: t.Optional[ULID] = Field(default_factory=ULID, primary_key=True)

    @property
    def date_created(self):
        return arrow.get(ULID(self.id).timestamp)

    @declared_attr
    def __tablename__(cls):
        return underscore(cls.__name__)

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"
        json_loads = load.json
        json_dumps = dump.json

    async def save(self) -> None:
        async with db.async_session() as session:
            session.add(self)
            await session.commit()
