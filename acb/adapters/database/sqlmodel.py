import typing as t

from adapters.firebase import current_user

import arrow
from acb.actions import dump
from acb.actions import load
from acb.adapters.database.sqlalchemy import db
from inflection import underscore
from sqlalchemy import Column
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declared_attr
from sqlalchemy_utils import ArrowType
from sqlmodel import Field
from sqlmodel import SQLModel
from ulid import ULID


class AppBaseModel(SQLModel):
    __table_args__ = {"extend_existing": True}
    __mapper_args__ = {"always_refresh": True}
    id: t.Optional[ULID] = Field(default_factory=ULID, primary_key=True)
    # date_created: t.Optional[arrow.Arrow] = Field(
    #     default_factory=arrow.utcnow, alias="created_at", sa_column=Column(ArrowType)
    # )
    date_created: t.Optional[arrow.Arrow] = hybrid_property(arrow.get(id.timestamp))
    # alias="created_at")
    # https://github.com/van51/sqlmodel.git#93509eb

    maintainer: t.Optional[str] = Field(
        default_factory=lambda: current_user.name, alias="created_by"
    )
    date_modified: t.Optional[arrow.Arrow] = Field(
        default_factory=arrow.utcnow,
        alias="last_edited_at",
        sa_column=Column(ArrowType, onupdate=arrow.utcnow),
    )
    editor: t.Optional[str] = Field(
        default_factory=lambda: current_user.name,
        sa_column_kwargs=dict(onupdate=lambda: current_user.name),
        alias="last_edited_by",
    )

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
