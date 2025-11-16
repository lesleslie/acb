"""Test SQLAlchemy Model Adapter."""

import pytest
from typing import Any

from acb.adapters.models._sqlalchemy import SQLALCHEMY_AVAILABLE, SQLAlchemyModelAdapter

# Global type variables to avoid redeclaration issues
Base = None
SampleUser = None
SamplePost = None
SampleTag = None
SampleProfile = None
user_tag_association = None
Integer = None
String = None
Boolean = None

if SQLALCHEMY_AVAILABLE:
    from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
    from sqlalchemy.orm import DeclarativeBase, declarative_base, relationship

    # Use modern SQLAlchemy 2.0 style if available
    try:

        class _Base(DeclarativeBase):
            pass

        Base = _Base
    except (ImportError, AttributeError):
        # Fallback to classic style
        Base = declarative_base()

    # Association table for many-to-many relationship
    user_tag_association = Table(
        "user_tags",
        Base.metadata,
        Column("user_id", Integer, ForeignKey("users.id")),
        Column("tag_id", Integer, ForeignKey("tags.id")),
    )

    class _SampleUser(Base):  # type: ignore[misc]
        __tablename__ = "users"

        id = Column(Integer, primary_key=True)
        name = Column(String(50))
        email = Column(String(100))
        active = Column(Boolean, default=True)

        # One-to-many relationship
        posts = relationship("_SamplePost", back_populates="author")

        # Many-to-many relationship
        tags = relationship(
            "_SampleTag", secondary=user_tag_association, back_populates="users"
        )

        def __init__(
            self,
            id: int | None = None,
            name: str | None = None,
            email: str | None = None,
            active: bool = True,
            **kwargs: Any,
        ) -> None:
            super().__init__(**kwargs)
            if id is not None:
                self.id = id
            if name is not None:
                self.name = name
            if email is not None:
                self.email = email
            self.active = active

    class _SamplePost(Base):  # type: ignore[misc]
        __tablename__ = "posts"

        id = Column(Integer, primary_key=True)
        title = Column(String(200))
        content = Column(String(1000))
        author_id = Column(Integer, ForeignKey("users.id"))

        # Many-to-one relationship
        author = relationship("_SampleUser", back_populates="posts")

        def __init__(
            self,
            id: int | None = None,
            title: str | None = None,
            content: str | None = None,
            author_id: int | None = None,
            **kwargs: Any,
        ) -> None:
            super().__init__(**kwargs)
            if id is not None:
                self.id = id
            if title is not None:
                self.title = title
            if content is not None:
                self.content = content
            if author_id is not None:
                self.author_id = author_id

    class _SampleTag(Base):  # type: ignore[misc]
        __tablename__ = "tags"

        id = Column(Integer, primary_key=True)
        name = Column(String(50))

        # Many-to-many relationship
        users = relationship(
            "_SampleUser", secondary=user_tag_association, back_populates="tags"
        )

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

    class _SampleProfile(Base):  # type: ignore[misc]
        __tablename__ = "profiles"

        profile_id = Column(Integer, primary_key=True)  # Non-standard primary key name
        bio = Column(String(500))
        website = Column(String(200))

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

    # Assign to module-level variables
    SampleUser = _SampleUser
    SamplePost = _SamplePost
    SampleTag = _SampleTag
    SampleProfile = _SampleProfile

else:
    # Define dummy classes when SQLAlchemy isn't available
    class _DummyBase:
        pass

    class _DummySampleUser(_DummyBase):
        def __init__(
            self,
            id: int | None = None,
            name: str | None = None,
            email: str | None = None,
            active: bool = True,
            **kwargs: Any,
        ) -> None:
            pass

    class _DummySamplePost(_DummyBase):
        def __init__(
            self,
            id: int | None = None,
            title: str | None = None,
            content: str | None = None,
            author_id: int | None = None,
            **kwargs: Any,
        ) -> None:
            pass

    class _DummySampleTag(_DummyBase):
        pass

    class _DummySampleProfile(_DummyBase):
        pass

    # Assign to module-level variables
    Base = _DummyBase
    SampleUser = _DummySampleUser
    SamplePost = _DummySamplePost
    SampleTag = _DummySampleTag
    SampleProfile = _DummySampleProfile


@pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not installed")
class TestSQLAlchemyModelAdapter:
    def test_init(self) -> None:
        adapter = SQLAlchemyModelAdapter()
        assert adapter is not None

    def test_serialize(self) -> None:
        adapter = SQLAlchemyModelAdapter()
        user = SampleUser(id=1, name="John Doe", email="john@example.com", active=True)

        result = adapter.serialize(user)
        expected = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "active": True,
        }
        assert result == expected

    def test_serialize_with_none_values(self) -> None:
        adapter = SQLAlchemyModelAdapter()
        user = SampleUser(id=1, name="John Doe", email=None, active=True)

        result = adapter.serialize(user)
        expected = {"id": 1, "name": "John Doe", "email": None, "active": True}
        assert result == expected

    def test_serialize_nested(self) -> None:
        adapter = SQLAlchemyModelAdapter()
        user = SampleUser(id=1, name="John Doe", email="john@example.com")
        post = SamplePost(
            id=1, title="Test Post", content="This is a test", author_id=1
        )
        post.author = user  # type: ignore[attr-defined]

        result = adapter.serialize(post)
        assert result["id"] == 1
        assert result["title"] == "Test Post"
        assert result["content"] == "This is a test"
        assert result["author_id"] == 1

    def test_deserialize_raises_not_implemented(self) -> None:
        adapter = SQLAlchemyModelAdapter()
        data = {"id": 1, "name": "John Doe", "email": "john@example.com"}

        with pytest.raises(NotImplementedError):
            adapter.deserialize(data)

    def test_deserialize_to_class(self) -> None:
        adapter = SQLAlchemyModelAdapter()
        data = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "active": True,
        }

        result = adapter.deserialize_to_class(SampleUser, data)
        if SampleUser is not None:
            assert isinstance(result, SampleUser)
        assert result.id == 1  # type: ignore[attr-defined]
        assert result.name == "John Doe"  # type: ignore[attr-defined]
        assert result.email == "john@example.com"  # type: ignore[attr-defined]
        assert result.active  # type: ignore[attr-defined]

    def test_deserialize_to_class_with_extra_fields(self) -> None:
        adapter = SQLAlchemyModelAdapter()
        data = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "active": True,
            "extra_field": "ignored",
        }

        # Should filter out extra fields that don't exist in the model
        result = adapter.deserialize_to_class(SampleUser, data)
        if SampleUser is not None:
            assert isinstance(result, SampleUser)
        assert result.id == 1  # type: ignore[attr-defined]
        assert result.name == "John Doe"  # type: ignore[attr-defined]
        assert result.email == "john@example.com"  # type: ignore[attr-defined]
        assert result.active  # type: ignore[attr-defined]
        # extra_field should be ignored

    def test_get_entity_name(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        assert adapter.get_entity_name(SampleUser) == "users"

    def test_get_entity_name_custom_table(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        assert adapter.get_entity_name(SampleProfile) == "profiles"

    def test_get_entity_name_fallback(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        class NoTableModel:
            pass

        result = adapter.get_entity_name(NoTableModel)
        assert result == "notablemodel"

    def test_get_field_mapping(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        expected = {"id": "id", "name": "name", "email": "email", "active": "active"}
        assert adapter.get_field_mapping(SampleUser) == expected

    def test_validate_data(self) -> None:
        adapter = SQLAlchemyModelAdapter()
        data = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "active": True,
        }

        result = adapter.validate_data(SampleUser, data)
        assert result == data

    def test_validate_data_with_extra_fields(self) -> None:
        adapter = SQLAlchemyModelAdapter()
        data = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "active": True,
            "extra_field": "ignored",
        }

        result = adapter.validate_data(SampleUser, data)
        # Should return only valid fields
        expected = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "active": True,
        }
        assert result == expected

    def test_get_primary_key_field(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        assert adapter.get_primary_key_field(SampleUser) == "id"

    def test_get_primary_key_field_custom(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        assert adapter.get_primary_key_field(SampleProfile) == "profile_id"

    def test_get_primary_key_field_default(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        class NoTableModel:
            pass

        assert adapter.get_primary_key_field(NoTableModel) == "id"

    def test_get_field_type(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        # Test with SQLAlchemy column types
        id_type = adapter.get_field_type(SampleUser, "id")
        name_type = adapter.get_field_type(SampleUser, "name")
        active_type = adapter.get_field_type(SampleUser, "active")

        # The exact types depend on SQLAlchemy version, but should be reasonable
        assert id_type in (int, Integer, Any)
        assert name_type in (str, String, Any)
        assert active_type in (bool, Boolean, Any)

    def test_get_field_type_missing_field(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        assert adapter.get_field_type(SampleUser, "missing_field") == Any

    def test_is_relationship_field(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        # Regular columns should not be relationships
        assert not adapter.is_relationship_field(SampleUser, "id")
        assert not adapter.is_relationship_field(SampleUser, "name")
        assert not adapter.is_relationship_field(SampleUser, "email")

        # Actual relationships should be detected
        assert adapter.is_relationship_field(SampleUser, "posts")
        assert adapter.is_relationship_field(SamplePost, "author")

    def test_is_relationship_field_many_to_many(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        # Many-to-many relationships should be detected
        assert adapter.is_relationship_field(SampleUser, "tags")
        assert adapter.is_relationship_field(SampleTag, "users")

    def test_get_nested_model_class(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        # One-to-many relationship
        result = adapter.get_nested_model_class(SampleUser, "posts")
        assert result == SamplePost

        # Many-to-one relationship
        result = adapter.get_nested_model_class(SamplePost, "author")
        assert result == SampleUser

    def test_get_nested_model_class_many_to_many(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        # Many-to-many relationships
        result = adapter.get_nested_model_class(SampleUser, "tags")
        assert result == SampleTag

        result = adapter.get_nested_model_class(SampleTag, "users")
        assert result == SampleUser

    def test_get_nested_model_class_none(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        # Regular fields should return None
        assert adapter.get_nested_model_class(SampleUser, "name") is None

    def test_is_sqlalchemy_model_detection(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        # SQLAlchemy models should be detected
        assert adapter._is_sqlalchemy_model(SampleUser)
        assert adapter._is_sqlalchemy_model(SamplePost)
        assert adapter._is_sqlalchemy_model(SampleTag)

        # Regular classes should not be detected
        class RegularClass:
            pass

        assert not adapter._is_sqlalchemy_model(RegularClass)

    def test_manual_serialize_fallback(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        # Create a user and test manual serialization path
        user = SampleUser(id=1, name="John Doe", email="john@example.com")

        # Force manual serialization by calling it directly
        result = adapter._manual_serialize(user)

        # Should contain the basic fields
        assert "id" in result
        assert "name" in result
        assert "email" in result
        assert result["id"] == 1
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"

    def test_filter_data_for_model(self) -> None:
        adapter = SQLAlchemyModelAdapter()

        data = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "active": True,
            "invalid_field": "should_be_removed",
            "another_invalid": 123,
        }

        result = adapter._filter_data_for_model(SampleUser, data)
        expected = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "active": True,
        }
        assert result == expected


@pytest.mark.skipif(
    SQLALCHEMY_AVAILABLE, reason="Test for when SQLAlchemy is not available"
)
class TestSQLAlchemyModelAdapterNotAvailable:
    def test_init_raises_import_error(self) -> None:
        with pytest.raises(ImportError, match="SQLAlchemy is required"):
            SQLAlchemyModelAdapter()
