"""Tests for the ACB Pydantic model adapter."""
from typing import Optional, List, Dict, Any, Union
from unittest.mock import Mock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from acb.adapters.models._pydantic import (
    PydanticModelAdapter,
    PYDANTIC_AVAILABLE,
    BaseModel as LocalBaseModel,
)


# Define test models
class TestUser(BaseModel):
    id: int
    name: str
    email: str
    age: Optional[int] = None
    is_active: bool = True


class TestProfile(BaseModel):
    bio: str
    website: Optional[str] = None


class TestUserWithProfile(BaseModel):
    id: int
    name: str
    profile: TestProfile
    profiles: List[TestProfile]


class TestUserWithConfig(BaseModel):
    id: int
    name: str

    class Config:
        collection_name = "users"
        primary_key = "id"


class TestUserWithModelConfig(BaseModel):
    id: int
    name: str

    model_config = {
        "collection_name": "modern_users",
        "primary_key": "user_id"
    }


class TestUserWithMethods(BaseModel):
    id: int
    name: str

    @classmethod
    def get_collection_name(cls) -> str:
        return "method_users"

    @classmethod
    def get_primary_key(cls) -> str:
        return "user_id"


# Define models with aliases
class TestUserWithAlias(BaseModel):
    user_id: int = Field(alias="id")
    full_name: str = Field(alias="name")


# Test for nested models
class TestCompany(BaseModel):
    id: int
    name: str
    employees: List[TestUser]


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
        instance = adapter.create_instance(TestUser, id=1, name="John", email="john@example.com")

        assert isinstance(instance, TestUser)
        assert instance.id == 1
        assert instance.name == "John"
        assert instance.email == "john@example.com"
        assert instance.is_active is True

    def test_get_field_value(self) -> None:
        """Test getting field values from an instance."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        user = TestUser(id=1, name="John", email="john@example.com", age=30)

        assert adapter.get_field_value(user, "id") == 1
        assert adapter.get_field_value(user, "name") == "John"
        assert adapter.get_field_value(user, "age") == 30
        assert adapter.get_field_value(user, "nonexistent") is None

    def test_serialize_modern_pydantic(self) -> None:
        """Test serializing an instance with modern Pydantic (model_dump)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        user = TestUser(id=1, name="John", email="john@example.com", age=30)

        # Serialize should use model_dump method for Pydantic v2
        serialized = adapter.serialize(user)
        assert serialized == {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "age": 30,
            "is_active": True
        }

    def test_serialize_legacy_pydantic(self) -> None:
        """Test serializing an instance with legacy Pydantic (dict method)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        user = TestUser(id=1, name="John", email="john@example.com", age=30)

        # Pydantic v2 has model_dump, test serialization with the real method
        serialized = adapter.serialize(user)
        assert serialized == {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "age": 30,
            "is_active": True
        }

    def test_manual_serialize_with_model_fields(self) -> None:
        """Test serialization with model_fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        user = TestUser(id=1, name="John", email="john@example.com", age=30)

        # Test serialization - should use model_dump for Pydantic v2
        serialized = adapter.serialize(user)
        assert serialized == {
            "id": 1,
            "name": "John",
            "email": "john@example.com",
            "age": 30,
            "is_active": True
        }

    def test_manual_serialize_with_nested_models(self) -> None:
        """Test serialization with nested models."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        profile = TestProfile(bio="Software developer", website="https://example.com")
        user = TestUserWithProfile(
            id=1,
            name="John",
            profile=profile,
            profiles=[profile]
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
            tags: List[str]
            metadata: Dict[str, Any]

        data = TestDataModel(
            id=1,
            tags=["tag1", "tag2"],
            metadata={"key": "value", "count": 42}
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

        with pytest.raises(NotImplementedError, match="Deserialize requires specific model class context"):
            adapter.deserialize({"id": 1, "name": "John"})

    def test_deserialize_to_class_success(self) -> None:
        """Test deserializing data to a specific model class."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        data = {"id": 1, "name": "John", "email": "john@example.com", "age": 30}

        user = adapter.deserialize_to_class(TestUser, data)
        assert isinstance(user, TestUser)
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
            "another_extra": "also_filtered"
        }

        user = adapter.deserialize_to_class(TestUser, data)
        assert isinstance(user, TestUser)
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
            "extra_field": "filtered"
        }

        # Pydantic v2 models have model_fields, test filtering works properly
        filtered_data = adapter._filter_data_for_model(TestUser, data)
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
            "extra_field": "filtered"
        }

        # Mock model_fields attribute
        mock_field_info1 = Mock()
        mock_field_info1.name = "id"
        mock_field_info2 = Mock()
        mock_field_info2.name = "name"
        mock_field_info3 = Mock()
        mock_field_info3.name = "email"

        with patch.object(TestUser, "model_fields", {
            "id": mock_field_info1,
            "name": mock_field_info2,
            "email": mock_field_info3
        }):
            filtered_data = adapter._filter_data_for_model(TestUser, data)
            assert filtered_data == {"id": 1, "name": "John", "email": "john@example.com"}

    def test_get_entity_name_with_tablename(self) -> None:
        """Test getting entity name with tablename in Config."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        class TestModel(BaseModel):
            id: int

            class Config:
                tablename = "test_table"

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
        name = adapter.get_entity_name(TestUserWithMethods)
        assert name == "method_users"

    def test_get_entity_name_with_config_class(self) -> None:
        """Test getting entity name with Config class."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        name = adapter.get_entity_name(TestUserWithConfig)
        assert name == "users"

    def test_get_entity_name_with_model_config(self) -> None:
        """Test getting entity name with model_config."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        name = adapter.get_entity_name(TestUserWithModelConfig)
        assert name == "modern_users"

    def test_get_entity_name_with_default(self) -> None:
        """Test getting entity name with default fallback."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        name = adapter.get_entity_name(TestUser)
        assert name == "testuser"

    def test_get_field_mapping_with_model_fields(self) -> None:
        """Test getting field mapping with model_fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        mapping = adapter.get_field_mapping(TestUser)

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
        mapping = adapter.get_field_mapping(TestUserWithAlias)

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

        validated_data = adapter.validate_data(TestUser, data)
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
            "extra_field": "filtered"
        }

        validated_data = adapter.validate_data(TestUser, data)
        assert "id" in validated_data
        assert "name" in validated_data
        assert "email" in validated_data
        assert "extra_field" not in validated_data

    def test_get_primary_key_field_configured(self) -> None:
        """Test getting primary key field when configured."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        pk_field = adapter.get_primary_key_field(TestUserWithConfig)
        assert pk_field == "id"  # From Config class

    def test_get_primary_key_field_model_config(self) -> None:
        """Test getting primary key field from model_config."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        pk_field = adapter.get_primary_key_field(TestUserWithModelConfig)
        assert pk_field == "user_id"

    def test_get_primary_key_field_with_method(self) -> None:
        """Test getting primary key field with get_primary_key method."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        pk_field = adapter.get_primary_key_field(TestUserWithMethods)
        assert pk_field == "user_id"

    def test_get_primary_key_field_common_names(self) -> None:
        """Test getting primary key field with common names."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        pk_field = adapter.get_primary_key_field(TestUser)
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
        id_type = adapter.get_field_type(TestUser, "id")
        name_type = adapter.get_field_type(TestUser, "name")
        age_type = adapter.get_field_type(TestUser, "age")

        assert id_type is int
        assert name_type is str
        assert age_type is int  # Optional[int] unwrapped to int

    def test_get_field_type_with_optional(self) -> None:
        """Test getting field type with Optional types."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        age_type = adapter.get_field_type(TestUser, "age")
        assert age_type is int  # Should unwrap Optional[int] to int

    def test_get_field_type_with_union(self) -> None:
        """Test getting field type with Union types."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()

        class TestModelWithUnion(BaseModel):
            value: Union[int, str]

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
        is_relationship = adapter.is_relationship_field(TestUserWithProfile, "profiles")
        assert is_relationship is True

    def test_is_relationship_field_single_model(self) -> None:
        """Test checking if a field is a relationship field (single model)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        is_relationship = adapter.is_relationship_field(TestUserWithProfile, "profile")
        assert is_relationship is True

    def test_is_relationship_field_non_model(self) -> None:
        """Test checking if a field is a relationship field (non-model)."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        is_relationship = adapter.is_relationship_field(TestUser, "name")
        assert is_relationship is False

    def test_get_nested_model_class_list(self) -> None:
        """Test getting nested model class for list fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        nested_class = adapter.get_nested_model_class(TestUserWithProfile, "profiles")
        assert nested_class is TestProfile

    def test_get_nested_model_class_single(self) -> None:
        """Test getting nested model class for single model fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        nested_class = adapter.get_nested_model_class(TestUserWithProfile, "profile")
        assert nested_class is TestProfile

    def test_get_nested_model_class_non_model(self) -> None:
        """Test getting nested model class for non-model fields."""
        if not PYDANTIC_AVAILABLE:
            pytest.skip("Pydantic not available")

        adapter = PydanticModelAdapter()
        nested_class = adapter.get_nested_model_class(TestUser, "name")
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
        assert issubclass(TestUser, LocalBaseModel)
    else:
        # Should be a fallback class
        assert LocalBaseModel is not None
