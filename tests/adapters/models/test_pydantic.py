"""Tests for the Pydantic Model Adapter."""

from typing import TYPE_CHECKING, Any

import pytest

_pydantic_available = False
try:
    from pydantic import BaseModel as PydanticBaseModel
    from pydantic import Field as PydanticField

    _pydantic_available = True
    BaseModel = PydanticBaseModel
    Field = PydanticField
except ImportError:

    class _FallbackBaseModel:
        def __init__(self, **kwargs: Any) -> None:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def _fallback_field(*args: Any, **kwargs: Any) -> Any:
        return None

    BaseModel = _FallbackBaseModel
    Field = _fallback_field

PYDANTIC_AVAILABLE = _pydantic_available

if TYPE_CHECKING:
    from pydantic import BaseModel as PydanticBaseModel
    from pydantic import Field as PydanticField

    BaseModel = PydanticBaseModel
    Field = PydanticField


from acb.adapters.models._pydantic import PydanticModelAdapter


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not available")
class TestPydanticModelAdapter:
    """Test suite for PydanticModelAdapter."""

    @pytest.fixture
    def adapter(self) -> PydanticModelAdapter:
        """Create a PydanticModelAdapter instance."""
        return PydanticModelAdapter()

    @pytest.fixture
    def sample_model_class(self) -> type[Any]:
        """Create a sample Pydantic model for testing."""
        if PYDANTIC_AVAILABLE:

            class TestSampleUser(BaseModel):  # type: ignore[misc]
                id: int | None = Field(default=None)
                name: str
                email: str
                age: int | None = Field(default=None)
                is_active: bool = Field(default=True)

                class Config:
                    collection_name = "users"
        else:

            class TestSampleUser(BaseModel):  # type: ignore[misc]
                def __init__(self, **kwargs: Any) -> None:
                    super().__init__(**kwargs)
                    self.id = kwargs.get("id")
                    self.name = kwargs.get("name", "")
                    self.email = kwargs.get("email", "")
                    self.age = kwargs.get("age")
                    self.is_active = kwargs.get("is_active", True)

        return TestSampleUser

    @pytest.fixture
    def sample_model_instance(self, sample_model_class: type[Any]) -> Any:
        """Create a sample model instance."""
        return sample_model_class(
            id=1, name="John Doe", email="john@example.com", age=30, is_active=True
        )

    def test_init_with_pydantic_available(self, adapter: PydanticModelAdapter) -> None:
        """Test adapter initialization when Pydantic is available."""
        assert adapter is not None

    def test_init_without_pydantic(self) -> None:
        """Test adapter initialization when Pydantic is not available."""
        with pytest.raises(ImportError, match="Pydantic is required"):
            # Mock unavailable Pydantic
            import acb.adapters.models._pydantic

            original_available = acb.adapters.models._pydantic.PYDANTIC_AVAILABLE
            acb.adapters.models._pydantic.PYDANTIC_AVAILABLE = False
            try:
                PydanticModelAdapter()
            finally:
                acb.adapters.models._pydantic.PYDANTIC_AVAILABLE = original_available

    def test_serialize_with_model_dump(
        self, adapter: PydanticModelAdapter, sample_model_instance: BaseModel
    ) -> None:
        """Test serialization using model_dump method."""
        result = adapter.serialize(sample_model_instance)

        expected = {
            "id": 1,
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
            "is_active": True,
        }
        assert result == expected

    def test_serialize_nested_model(self, adapter: PydanticModelAdapter) -> None:
        """Test serialization of nested models."""

        class Address(BaseModel):  # type: ignore[misc]
            street: str
            city: str

        class UserWithAddress(BaseModel):  # type: ignore[misc]
            name: str
            address: Address

        address = Address(street="123 Main St", city="Anytown")
        user = UserWithAddress(name="Jane Doe", address=address)

        result = adapter.serialize(user)
        expected = {
            "name": "Jane Doe",
            "address": {"street": "123 Main St", "city": "Anytown"},
        }
        assert result == expected

    def test_deserialize_raises_not_implemented(
        self, adapter: PydanticModelAdapter
    ) -> None:
        """Test that deserialize method raises NotImplementedError."""
        with pytest.raises(
            NotImplementedError,
            match="Deserialize requires specific model class context",
        ):
            adapter.deserialize({"name": "test"})

    def test_deserialize_to_class(
        self, adapter: PydanticModelAdapter, sample_model_class: type[BaseModel]
    ) -> None:
        """Test deserialization to specific model class."""
        data = {
            "id": 2,
            "name": "Jane Doe",
            "email": "jane@example.com",
            "age": 25,
            "is_active": False,
        }

        result = adapter.deserialize_to_class(sample_model_class, data)

        assert isinstance(result, sample_model_class)
        assert result.id == 2
        assert result.name == "Jane Doe"
        assert result.email == "jane@example.com"
        assert result.age == 25
        assert not result.is_active

    def test_deserialize_to_class_with_extra_fields(
        self, adapter: PydanticModelAdapter, sample_model_class: type[BaseModel]
    ) -> None:
        """Test deserialization with extra fields that should be filtered."""
        data = {
            "id": 3,
            "name": "Bob Smith",
            "email": "bob@example.com",
            "age": 40,
            "is_active": True,
            "extra_field": "should be ignored",  # This should be filtered out
        }

        result = adapter.deserialize_to_class(sample_model_class, data)

        assert isinstance(result, sample_model_class)
        assert result.id == 3
        assert result.name == "Bob Smith"

    def test_get_entity_name_with_config(
        self, adapter: PydanticModelAdapter, sample_model_class: type[BaseModel]
    ) -> None:
        """Test entity name extraction from model config."""
        result = adapter.get_entity_name(sample_model_class)
        assert result == "users"

    def test_get_entity_name_fallback(self, adapter: PydanticModelAdapter) -> None:
        """Test entity name fallback to lowercase class name."""

        class SimpleModel(BaseModel):  # type: ignore[misc]
            value: str

        result = adapter.get_entity_name(SimpleModel)
        assert result == "simplemodel"

    def test_get_field_mapping(
        self, adapter: PydanticModelAdapter, sample_model_class: type[BaseModel]
    ) -> None:
        """Test field mapping extraction."""
        result = adapter.get_field_mapping(sample_model_class)

        expected = {
            "id": "id",
            "name": "name",
            "email": "email",
            "age": "age",
            "is_active": "is_active",
        }
        assert result == expected

    def test_get_field_mapping_with_aliases(
        self, adapter: PydanticModelAdapter
    ) -> None:
        """Test field mapping with field aliases."""
        if PYDANTIC_AVAILABLE:

            class AliasTestModel(BaseModel):  # type: ignore[misc]
                user_id: int = Field(alias="id")
                full_name: str = Field(alias="name")
                email_address: str = Field(alias="email")
        else:

            class AliasTestModel(BaseModel):  # type: ignore[misc]
                def __init__(self, **kwargs: Any) -> None:
                    super().__init__(**kwargs)

        result = adapter.get_field_mapping(AliasTestModel)

        expected = {"user_id": "id", "full_name": "name", "email_address": "email"}
        assert result == expected

    def test_validate_data(
        self, adapter: PydanticModelAdapter, sample_model_class: type[BaseModel]
    ) -> None:
        """Test data validation through temporary instance creation."""
        data = {
            "id": 4,
            "name": "Alice Johnson",
            "email": "alice@example.com",
            "age": 35,
        }

        result = adapter.validate_data(sample_model_class, data)

        # Should return serialized version of validated data
        expected = {
            "id": 4,
            "name": "Alice Johnson",
            "email": "alice@example.com",
            "age": 35,
            "is_active": True,  # Default value
        }
        assert result == expected

    def test_validate_data_with_invalid_data(
        self, adapter: PydanticModelAdapter, sample_model_class: type[BaseModel]
    ) -> None:
        """Test data validation with invalid data that gets filtered."""
        data = {
            "id": 5,
            "name": "Charlie Brown",
            "email": "charlie@example.com",
            "invalid_field": "should be removed",
        }

        result = adapter.validate_data(sample_model_class, data)

        # Should filter invalid fields and use defaults
        expected = {
            "id": 5,
            "name": "Charlie Brown",
            "email": "charlie@example.com",
            "age": None,  # Default
            "is_active": True,  # Default
        }
        assert result == expected

    def test_get_primary_key_field_default(
        self, adapter: PydanticModelAdapter, sample_model_class: type[BaseModel]
    ) -> None:
        """Test primary key field detection."""
        result = adapter.get_primary_key_field(sample_model_class)
        assert result == "id"

    def test_get_primary_key_field_from_config(
        self, adapter: PydanticModelAdapter
    ) -> None:
        """Test primary key field from model config."""

        class ModelWithCustomPK(BaseModel):  # type: ignore[misc]
            user_id: int
            name: str

            class Config:
                primary_key = "user_id"

        result = adapter.get_primary_key_field(ModelWithCustomPK)
        assert result == "user_id"

    def test_get_field_type(
        self, adapter: PydanticModelAdapter, sample_model_class: type[BaseModel]
    ) -> None:
        """Test field type extraction."""
        # Test various field types
        assert adapter.get_field_type(sample_model_class, "id") is int
        assert adapter.get_field_type(sample_model_class, "name") is str
        assert adapter.get_field_type(sample_model_class, "is_active") is bool

    def test_is_relationship_field(self, adapter: PydanticModelAdapter) -> None:
        """Test relationship field detection."""

        class Profile(BaseModel):  # type: ignore[misc]
            bio: str

        class UserWithProfile(BaseModel):  # type: ignore[misc]
            name: str
            profile: Profile
            profiles: list[Profile]

        # Single model relationship
        assert adapter.is_relationship_field(UserWithProfile, "profile")
        # List of models relationship
        assert adapter.is_relationship_field(UserWithProfile, "profiles")
        # Regular field
        assert not adapter.is_relationship_field(UserWithProfile, "name")

    def test_get_nested_model_class(self, adapter: PydanticModelAdapter) -> None:
        """Test nested model class extraction."""

        class Profile(BaseModel):  # type: ignore[misc]
            bio: str

        class UserWithProfile(BaseModel):  # type: ignore[misc]
            name: str
            profile: Profile
            profiles: list[Profile]

        # Single model relationship
        result = adapter.get_nested_model_class(UserWithProfile, "profile")
        assert result == Profile

        # List of models relationship
        result = adapter.get_nested_model_class(UserWithProfile, "profiles")
        assert result == Profile

        # Non-relationship field
        result = adapter.get_nested_model_class(UserWithProfile, "name")
        assert result is None


class TestPydanticModelAdapterWithoutPydantic:
    """Test adapter behavior when Pydantic is not available."""

    def test_import_error_handling(self) -> None:
        """Test that appropriate error is raised when Pydantic is unavailable."""
        # This test simulates the case where Pydantic is not installed
        import acb.adapters.models._pydantic as pydantic_module

        # Temporarily set PYDANTIC_AVAILABLE to False
        original_available = pydantic_module.PYDANTIC_AVAILABLE
        pydantic_module.PYDANTIC_AVAILABLE = False

        try:
            with pytest.raises(
                ImportError, match="Pydantic is required for PydanticModelAdapter"
            ):
                PydanticModelAdapter()
        finally:
            # Restore original state
            pydantic_module.PYDANTIC_AVAILABLE = original_available
