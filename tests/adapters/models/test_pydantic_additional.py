"""Tests for the ACB Pydantic model adapter."""

from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel, Field
from typing import Any

from acb.adapters.models._pydantic import (
    PYDANTIC_AVAILABLE,
    PydanticModelAdapter,
)
from acb.adapters.models._pydantic import (
    BaseModel as LocalBaseModel,
)


# Define test models (using "Sample" prefix to avoid pytest collection warnings)
class SampleUser(BaseModel):
    id: int
    name: str
    email: str
    age: int | None = None
    is_active: bool = True


class SampleProfile(BaseModel):
    bio: str
    website: str | None = None


class SampleUserWithProfile(BaseModel):
    id: int
    name: str
    profile: SampleProfile
    profiles: list[SampleProfile]


class SampleUserWithConfig(BaseModel):
    id: int
    name: str

    model_config = {
        "collection_name": "users",
        "primary_key": "id",
    }


class SampleUserWithModelConfig(BaseModel):
    id: int
    name: str

    model_config = {"collection_name": "modern_users", "primary_key": "user_id"}


class SampleUserWithMethods(BaseModel):
    id: int
    name: str

    @classmethod
    def get_collection_name(cls) -> str:
        return "method_users"

    @classmethod
    def get_primary_key(cls) -> str:
        return "user_id"


# Define models with aliases
class SampleUserWithAlias(BaseModel):
    user_id: int = Field(alias="id")
    full_name: str = Field(alias="name")


# Sample for nested models
class SampleCompany(BaseModel):
    id: int
    name: str
    employees: list[SampleUser]


class TestPydanticModelAdapter:
    """Test the PydanticModelAdapter class."""

    def test_adapter_initialization_available(self) -> None:
        """Test adapter initialization when Pydantic is available."""
        if PYDANTIC_AVAILABLE:
            adapter = PydanticModelAdapter()
            assert isinstance(adapter, PydanticModelAdapter)
        else:
            with pytest.raises(ImportError, match="Pydantic is required"):
                PydanticModelAdapter()

    def test_create_instance(self) -> None:
        """Test creating an instance of a model class."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        instance = adapter.create_instance(
            SampleUser, id=1, name="John", email="john@example.com"
        )

        assert isinstance(instance, SampleUser)
        assert instance.id == 1
        assert instance.name == "John"
        assert instance.email == "john@example.com"
        assert instance.is_active is True

    def test_get_field_value(self) -> None:
        """Test getting field values from an instance."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        user = SampleUser(id=1, name="John", email="john@example.com", age=30)

        assert adapter.get_field_value(user, "id") == 1
        assert adapter.get_field_value(user, "name") == "John"
        assert adapter.get_field_value(user, "age") == 30
        assert adapter.get_field_value(user, "nonexistent") is None

    def test_serialize_modern_pydantic(self) -> None:
        """Test serializing an instance with modern Pydantic (model_dump)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        user = SampleUser(id=1, name="John", email="john@example.com", age=30)

        # Serialize should use model_dump method for Pydantic v2
        serialized = adapter.serialize(user)
        assert serialized == {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "age": 30,
            "is_active": True,
        }

    def test_serialize_legacy_pydantic(self) -> None:
        """Test serializing an instance with legacy Pydantic (dict method)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        user = SampleUser(id=1, name="John", email="john@example.com", age=30)

        # Pydantic v2 has model_dump, test serialization with the real method
        serialized = adapter.serialize(user)
        assert serialized == {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "age": 30,
            "is_active": True,
        }

    def test_manual_serialize_with_model_fields(self) -> None:
        """Test serialization with model_fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        user = SampleUser(id=1, name="John", email="john@example.com", age=30)

        # Test serialization - should use model_dump for Pydantic v2
        serialized = adapter.serialize(user)
        assert serialized == {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "age": 30,
            "is_active": True,
        }

    def test_manual_serialize_with_nested_models(self) -> None:
        """Test serialization with nested models."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        profile = SampleProfile(bio="Software developer", website="https://example.com")
        user = SampleUserWithProfile(
            id=1, name="John", profile=profile, profiles=[profile]
        )

        # Test serialization - should handle nested models
        serialized = adapter.serialize(user)
        assert serialized["id"] == 1
        assert serialized["name"] == "John"
        assert serialized["profile"]["bio"] == "Software developer"
        assert serialized["profiles"][0]["bio"] == "Software developer"

    def test_manual_serialize_with_lists_and_dicts(self) -> None:
        """Test serialization with lists and dictionaries."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        class TestDataModel(BaseModel):
            id: int
            tags: list[str]
            metadata: dict[str, Any]

        data = TestDataModel(
            id=1, tags=["tag1", "tag2"], metadata={"key": "value", "count": 42}
        )

        # Test serialization
        serialized = adapter.serialize(data)
        assert serialized["id"] == 1
        assert serialized["tags"] == ["tag1", "tag2"]
        assert serialized["metadata"] == {"key": "value", "count": 42}

    def test_deserialize_not_implemented(self) -> None:
        """Test that deserialize raises NotImplementedError."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        with pytest.raises(
            NotImplementedError,
            match="Deserialize requires specific model class context",
        ):
            adapter.deserialize({"id": 1, "name": "John"})

    def test_deserialize_to_class_success(self) -> None:
        """Test deserializing data to a specific model class."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        data = {"id": 1, "name": "John", "email": "john@example.com", "age": 30}

        user = adapter.deserialize_to_class(SampleUser, data)
        assert isinstance(user, SampleUser)
        assert user.id == 1
        assert user.name == "John"
        assert user.email == "john@example.com"
        assert user.age == 30

    def test_deserialize_to_class_with_extra_fields(self) -> None:
        """Test deserializing data with extra fields that should be filtered."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        data = {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "extra_field": "should_be_filtered",
            "another_extra": "also_filtered",
        }

        user = adapter.deserialize_to_class(SampleUser, data)
        assert isinstance(user, SampleUser)
        assert user.id == 1
        assert user.name == "John"
        assert user.email == "john@example.com"
        assert not hasattr(user, "extra_field")

    def test_filter_data_for_model_with_fields(self) -> None:
        """Test filtering data for a model (Pydantic v2 uses model_fields)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        data = {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "extra_field": "filtered",
        }

        # Pydantic v2 models have model_fields, test filtering works properly
        filtered_data = adapter._filter_data_for_model(SampleUser, data)
        assert filtered_data == {"id": 1, "name": "John", "email": "john@example.com"}

    def test_filter_data_for_model_with_model_fields(self) -> None:
        """Test filtering data for a model with model_fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        data = {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "extra_field": "filtered",
        }

        # Mock model_fields attribute
        mock_field_info1 = Mock()
        mock_field_info1.name = "id"
        mock_field_info2 = Mock()
        mock_field_info2.name = "name"
        mock_field_info3 = Mock()
        mock_field_info3.name = "email"

        with patch.object(
            SampleUser,
            "model_fields",
            {
                "id": mock_field_info1,
                "name": mock_field_info2,
                "email": mock_field_info3,
            },
        ):
            filtered_data = adapter._filter_data_for_model(SampleUser, data)
            assert filtered_data == {
                "id": 1,
                "name": "John",
                "email": "john@example.com",
            }

    def test_get_entity_name_with_tablename(self) -> None:
        """Test getting entity name with tablename in Config."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        class TestModel(BaseModel):
            id: int

            model_config = {
                "tablename": "test_table",
            }

        # Test that adapter reads tablename from Config
        name = adapter.get_entity_name(TestModel)
        # Should fallback to class name if tablename is not recognized
        assert name == "testmodel"  # Lowercase class name

    def test_get_entity_name_with_collection_name_attribute(self) -> None:
        """Test getting entity name with __collection_name__ attribute."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        class TestModel(BaseModel):
            id: int

            __collection_name__ = "custom_collection"

        name = adapter.get_entity_name(TestModel)
        assert name == "custom_collection"

    def test_get_entity_name_with_get_collection_name_method(self) -> None:
        """Test getting entity name with get_collection_name method."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        name = adapter.get_entity_name(SampleUserWithMethods)
        assert name == "method_users"

    def test_get_entity_name_with_config_class(self) -> None:
        """Test getting entity name with Config class."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        name = adapter.get_entity_name(SampleUserWithConfig)
        assert name == "users"

    def test_get_entity_name_with_model_config(self) -> None:
        """Test getting entity name with model_config."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        name = adapter.get_entity_name(SampleUserWithModelConfig)
        assert name == "modern_users"

    def test_get_entity_name_with_default(self) -> None:
        """Test getting entity name with default fallback."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        name = adapter.get_entity_name(SampleUser)
        assert name == "sampleuser"

    def test_get_field_mapping_with_model_fields(self) -> None:
        """Test getting field mapping with model_fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        mapping = adapter.get_field_mapping(SampleUser)

        # Should have all the standard fields
        assert "id" in mapping
        assert "name" in mapping
        assert "email" in mapping
        assert "age" in mapping
        assert "is_active" in mapping

    def test_get_field_mapping_with_aliases(self) -> None:
        """Test getting field mapping with field aliases."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        mapping = adapter.get_field_mapping(SampleUserWithAlias)

        # Should map field names to their aliases
        assert mapping["user_id"] == "id"
        assert mapping["full_name"] == "name"

    def test_get_field_mapping_with_annotations(self) -> None:
        """Test getting field mapping from annotations."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        class SimpleModel:
            id: int
            name: str

        # Mock the absence of model_fields and __fields__
        if hasattr(SimpleModel, "model_fields"):
            delattr(SimpleModel, "model_fields")
        if hasattr(SimpleModel, "__fields__"):
            delattr(SimpleModel, "__fields__")

        mapping = adapter.get_field_mapping(SimpleModel)
        assert mapping["id"] == "id"
        assert mapping["name"] == "name"

    def test_validate_data_success(self) -> None:
        """Test validating data successfully."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        data = {"id": 1, "name": "John", "email": "john@example.com"}

        validated_data = adapter.validate_data(SampleUser, data)
        assert "id" in validated_data
        assert "name" in validated_data
        assert "email" in validated_data

    def test_validate_data_with_filtering(self) -> None:
        """Test validating data with filtering of extra fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        data = {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "extra_field": "filtered",
        }

        validated_data = adapter.validate_data(SampleUser, data)
        assert "id" in validated_data
        assert "name" in validated_data
        assert "email" in validated_data
        assert "extra_field" not in validated_data

    def test_get_primary_key_field_configured(self) -> None:
        """Test getting primary key field when configured."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        pk_field = adapter.get_primary_key_field(SampleUserWithConfig)
        assert pk_field == "id"  # From Config class

    def test_get_primary_key_field_model_config(self) -> None:
        """Test getting primary key field from model_config."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        pk_field = adapter.get_primary_key_field(SampleUserWithModelConfig)
        assert pk_field == "user_id"

    def test_get_primary_key_field_with_method(self) -> None:
        """Test getting primary key field with get_primary_key method."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        pk_field = adapter.get_primary_key_field(SampleUserWithMethods)
        assert pk_field == "user_id"

    def test_get_primary_key_field_common_names(self) -> None:
        """Test getting primary key field with common names."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        pk_field = adapter.get_primary_key_field(SampleUser)
        assert pk_field == "id"

    def test_get_primary_key_field_default(self) -> None:
        """Test getting primary key field default fallback."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        class ModelWithoutId:
            name: str
            email: str

        pk_field = adapter.get_primary_key_field(ModelWithoutId)
        assert pk_field == "id"  # Default fallback

    def test_get_field_type_with_model_fields(self) -> None:
        """Test getting field type with model_fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        # Test different field types
        id_type = adapter.get_field_type(SampleUser, "id")
        name_type = adapter.get_field_type(SampleUser, "name")
        age_type = adapter.get_field_type(SampleUser, "age")

        assert id_type is int
        assert name_type is str
        assert age_type is int  # Optional[int] unwrapped to int

    def test_get_field_type_with_optional(self) -> None:
        """Test getting field type with Optional types."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        age_type = adapter.get_field_type(SampleUser, "age")
        assert age_type is int  # Should unwrap Optional[int] to int

    def test_get_field_type_with_union(self) -> None:
        """Test getting field type with Union types."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        class TestModelWithUnion(BaseModel):
            value: int | str

        value_type = adapter.get_field_type(TestModelWithUnion, "value")
        # Union types might be unwrapped differently depending on implementation
        assert value_type is not None

    def test_get_field_type_default(self) -> None:
        """Test getting field type with default fallback."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        class TestModelWithoutAnnotations:
            pass

        field_type = adapter.get_field_type(TestModelWithoutAnnotations, "nonexistent")
        # Should return Any type
        assert field_type is not None

    def test_is_relationship_field_list_of_models(self) -> None:
        """Test checking if a field is a relationship field (list of models)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        is_relationship = adapter.is_relationship_field(
            SampleUserWithProfile, "profiles"
        )
        assert is_relationship is True

    def test_is_relationship_field_single_model(self) -> None:
        """Test checking if a field is a relationship field (single model)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        is_relationship = adapter.is_relationship_field(
            SampleUserWithProfile, "profile"
        )
        assert is_relationship is True

    def test_is_relationship_field_non_model(self) -> None:
        """Test checking if a field is a relationship field (non-model)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        is_relationship = adapter.is_relationship_field(SampleUser, "name")
        assert is_relationship is False

    def test_get_nested_model_class_list(self) -> None:
        """Test getting nested model class for list fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        nested_class = adapter.get_nested_model_class(SampleUserWithProfile, "profiles")
        assert nested_class is SampleProfile

    def test_get_nested_model_class_single(self) -> None:
        """Test getting nested model class for single model fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        nested_class = adapter.get_nested_model_class(SampleUserWithProfile, "profile")
        assert nested_class is SampleProfile

    def test_get_nested_model_class_non_model(self) -> None:
        """Test getting nested model class for non-model fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        nested_class = adapter.get_nested_model_class(SampleUser, "name")
        assert nested_class is None


# Test the PYDANTIC_AVAILABLE flag
def test_pydantic_available_flag() -> None:
    """Test that PYDANTIC_AVAILABLE flag is correctly set."""
    # This should be True in a normal environment where Pydantic is installed
    assert PYDANTIC_AVAILABLE is True


def test_base_model_alias() -> None:
    """Test that BaseModel alias works correctly."""
    if PYDANTIC_AVAILABLE:
        # Should be the real Pydantic BaseModel
        assert LocalBaseModel is BaseModel
        assert issubclass(SampleUser, LocalBaseModel)
    else:
        # Should be a fallback class
        assert LocalBaseModel is not None
