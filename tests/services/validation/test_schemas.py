"""Tests for validation schemas."""

from acb.services.validation._base import ValidationConfig
from acb.services.validation.schemas import (
    BasicValidationSchema,
    DictValidationSchema,
    EmailValidationSchema,
    ListValidationSchema,
    SchemaBuilder,
    StringValidationSchema,
)


class TestBasicValidationSchema:
    """Tests for BasicValidationSchema."""

    async def test_basic_validation_success(self) -> None:
        """Test basic validation with correct type."""
        schema = BasicValidationSchema(name="test", data_type=str, required=True)

        result = await schema.validate("hello")
        assert result.is_valid is True
        assert result.value == "hello"

    async def test_basic_validation_type_mismatch(self) -> None:
        """Test basic validation with type mismatch."""
        schema = BasicValidationSchema(
            name="test",
            data_type=str,
            required=True,
            config=ValidationConfig(enable_coercion=False),
        )

        result = await schema.validate(123)
        assert result.is_valid is False
        assert any("Expected str, got int" in error for error in result.errors)

    async def test_basic_validation_with_coercion(self) -> None:
        """Test basic validation with type coercion."""
        schema = BasicValidationSchema(
            name="test",
            data_type=str,
            required=True,
            config=ValidationConfig(enable_coercion=True),
        )

        result = await schema.validate(123)
        assert result.is_valid is True
        assert result.value == "123"
        assert len(result.warnings) > 0

    async def test_basic_validation_none_not_allowed(self) -> None:
        """Test basic validation with None when not allowed."""
        schema = BasicValidationSchema(
            name="test", data_type=str, required=True, allow_none=False
        )

        result = await schema.validate(None)
        assert result.is_valid is False
        assert any("cannot be None" in error for error in result.errors)

    async def test_basic_validation_none_allowed(self) -> None:
        """Test basic validation with None when allowed."""
        schema = BasicValidationSchema(
            name="test", data_type=str, required=True, allow_none=True
        )

        result = await schema.validate(None)
        assert result.is_valid is True

    async def test_basic_validation_required_missing(self) -> None:
        """Test required field validation."""
        schema = BasicValidationSchema(name="test", data_type=str, required=True)

        result = await schema.validate("")
        assert result.is_valid is False
        assert any("required" in error.lower() for error in result.errors)


class TestStringValidationSchema:
    """Tests for StringValidationSchema."""

    async def test_string_validation_success(self) -> None:
        """Test successful string validation."""
        schema = StringValidationSchema(name="test", min_length=2, max_length=10)

        result = await schema.validate("hello")
        assert result.is_valid is True
        assert result.value == "hello"

    async def test_string_validation_too_short(self) -> None:
        """Test string too short validation."""
        schema = StringValidationSchema(name="test", min_length=5)

        result = await schema.validate("hi")
        assert result.is_valid is False
        assert any("too short" in error.lower() for error in result.errors)

    async def test_string_validation_too_long(self) -> None:
        """Test string too long validation."""
        schema = StringValidationSchema(name="test", max_length=3)

        result = await schema.validate("hello world")
        assert result.is_valid is False
        assert any("too long" in error.lower() for error in result.errors)

    async def test_string_validation_pattern_match(self) -> None:
        """Test string pattern matching."""
        schema = StringValidationSchema(
            name="test",
            pattern=r"^[a-zA-Z]+$",  # Only letters
        )

        await schema.compile()  # Ensure pattern is compiled

        result = await schema.validate("HelloWorld")
        assert result.is_valid is True

    async def test_string_validation_pattern_no_match(self) -> None:
        """Test string pattern not matching."""
        schema = StringValidationSchema(
            name="test",
            pattern=r"^[a-zA-Z]+$",  # Only letters
        )

        await schema.compile()

        result = await schema.validate("Hello123")
        assert result.is_valid is False
        assert any("does not match pattern" in error for error in result.errors)

    async def test_string_validation_whitespace_stripping(self) -> None:
        """Test whitespace stripping."""
        schema = StringValidationSchema(name="test", strip_whitespace=True)

        result = await schema.validate("  hello  ")
        assert result.is_valid is True
        assert result.value == "hello"
        assert len(result.warnings) > 0

    async def test_string_validation_type_coercion(self) -> None:
        """Test type coercion to string."""
        schema = StringValidationSchema(
            name="test", config=ValidationConfig(enable_coercion=True)
        )

        result = await schema.validate(123)
        assert result.is_valid is True
        assert result.value == "123"
        assert len(result.warnings) > 0


class TestEmailValidationSchema:
    """Tests for EmailValidationSchema."""

    async def test_valid_email(self) -> None:
        """Test valid email validation."""
        schema = EmailValidationSchema()

        result = await schema.validate("test@example.com")
        assert result.is_valid is True
        assert result.value == "test@example.com"

    async def test_invalid_email_format(self) -> None:
        """Test invalid email format."""
        schema = EmailValidationSchema()

        result = await schema.validate("invalid-email")
        assert result.is_valid is False
        assert any("invalid email format" in error.lower() for error in result.errors)

    async def test_email_normalization(self) -> None:
        """Test email normalization."""
        schema = EmailValidationSchema()

        result = await schema.validate("  Test@Example.COM  ")
        assert result.is_valid is True
        assert result.value == "test@example.com"
        assert len(result.warnings) > 0

    async def test_email_too_long(self) -> None:
        """Test email too long validation."""
        schema = EmailValidationSchema()

        long_email = "a" * 250 + "@example.com"
        result = await schema.validate(long_email)
        assert result.is_valid is False
        assert any("too long" in error.lower() for error in result.errors)

    async def test_email_non_string(self) -> None:
        """Test email validation with non-string input."""
        schema = EmailValidationSchema()

        result = await schema.validate(123)
        assert result.is_valid is False
        assert any("must be string" in error for error in result.errors)


class TestListValidationSchema:
    """Tests for ListValidationSchema."""

    async def test_list_validation_success(self) -> None:
        """Test successful list validation."""
        schema = ListValidationSchema(name="test", min_items=1, max_items=5)

        result = await schema.validate([1, 2, 3])
        assert result.is_valid is True
        assert result.value == [1, 2, 3]

    async def test_list_validation_too_short(self) -> None:
        """Test list too short validation."""
        schema = ListValidationSchema(name="test", min_items=3)

        result = await schema.validate([1, 2])
        assert result.is_valid is False
        assert any("too short" in error.lower() for error in result.errors)

    async def test_list_validation_too_long(self) -> None:
        """Test list too long validation."""
        schema = ListValidationSchema(name="test", max_items=2)

        result = await schema.validate([1, 2, 3, 4])
        assert result.is_valid is False
        assert any("too long" in error.lower() for error in result.errors)

    async def test_list_validation_unique_items(self) -> None:
        """Test unique items validation."""
        schema = ListValidationSchema(name="test", unique_items=True)

        # Test with unique items
        result1 = await schema.validate([1, 2, 3])
        assert result1.is_valid is True

        # Test with duplicate items
        result2 = await schema.validate([1, 2, 2, 3])
        assert result2.is_valid is False
        assert any("must be unique" in error.lower() for error in result2.errors)

    async def test_list_validation_with_item_schema(self) -> None:
        """Test list validation with item schema."""
        item_schema = StringValidationSchema(name="item", min_length=2)

        schema = ListValidationSchema(name="test", item_schema=item_schema)

        # Test with valid items
        result1 = await schema.validate(["hello", "world"])
        assert result1.is_valid is True

        # Test with invalid item
        result2 = await schema.validate(["hello", "x"])  # "x" is too short
        assert result2.is_valid is False
        assert any("Item 1:" in error for error in result2.errors)

    async def test_list_validation_type_coercion(self) -> None:
        """Test list type coercion."""
        schema = ListValidationSchema(
            name="test", config=ValidationConfig(enable_coercion=True)
        )

        result = await schema.validate("hello")
        assert result.is_valid is True
        assert result.value == ["hello"]
        assert len(result.warnings) > 0


class TestDictValidationSchema:
    """Tests for DictValidationSchema."""

    async def test_dict_validation_success(self) -> None:
        """Test successful dict validation."""
        field_schemas = {
            "name": StringValidationSchema("name", min_length=1),
            "age": BasicValidationSchema("age", data_type=int),
        }

        schema = DictValidationSchema(
            name="test", field_schemas=field_schemas, required_fields=["name"]
        )

        data = {"name": "John", "age": 30}
        result = await schema.validate(data)
        assert result.is_valid is True
        assert result.value["name"] == "John"
        assert result.value["age"] == 30

    async def test_dict_validation_missing_required(self) -> None:
        """Test dict validation with missing required field."""
        schema = DictValidationSchema(name="test", required_fields=["name", "email"])

        data = {"name": "John"}
        result = await schema.validate(data)
        assert result.is_valid is False
        assert any(
            "Required field 'email' is missing" in error for error in result.errors
        )

    async def test_dict_validation_field_validation_error(self) -> None:
        """Test dict validation with field validation error."""
        field_schemas = {"name": StringValidationSchema("name", min_length=5)}

        schema = DictValidationSchema(name="test", field_schemas=field_schemas)

        data = {"name": "Jo"}  # Too short
        result = await schema.validate(data)
        assert result.is_valid is False
        assert any("Field 'name':" in error for error in result.errors)

    async def test_dict_validation_extra_fields_allowed(self) -> None:
        """Test dict validation with extra fields allowed."""
        schema = DictValidationSchema(name="test", allow_extra_fields=True)

        data = {"name": "John", "extra": "value"}
        result = await schema.validate(data)
        assert result.is_valid is True
        assert "extra" in result.value

    async def test_dict_validation_extra_fields_not_allowed(self) -> None:
        """Test dict validation with extra fields not allowed."""
        schema = DictValidationSchema(
            name="test", required_fields=["name"], allow_extra_fields=False
        )

        data = {"name": "John", "extra": "value"}
        result = await schema.validate(data)
        assert result.is_valid is False
        assert any("Unexpected field 'extra'" in error for error in result.errors)

    async def test_dict_validation_non_dict_input(self) -> None:
        """Test dict validation with non-dict input."""
        schema = DictValidationSchema(name="test")

        result = await schema.validate("not a dict")
        assert result.is_valid is False
        assert any("Expected dict" in error for error in result.errors)


class TestSchemaBuilder:
    """Tests for SchemaBuilder."""

    def test_schema_builder_basic(self) -> None:
        """Test basic schema building."""
        builder = SchemaBuilder()

        builder.add_basic("name", data_type=str, required=True)
        builder.add_string("email", min_length=5, max_length=50)

        schemas = builder.build()

        assert "name" in schemas
        assert "email" in schemas
        assert isinstance(schemas["name"], BasicValidationSchema)
        assert isinstance(schemas["email"], StringValidationSchema)

    def test_schema_builder_email(self) -> None:
        """Test email schema building."""
        builder = SchemaBuilder()
        builder.add_email("user_email")

        schemas = builder.build()
        assert "user_email" in schemas
        assert isinstance(schemas["user_email"], EmailValidationSchema)

    def test_schema_builder_list(self) -> None:
        """Test list schema building."""
        builder = SchemaBuilder()
        item_schema = StringValidationSchema("item", min_length=1)

        builder.add_list("items", item_schema=item_schema, min_items=1, max_items=10)

        schemas = builder.build()
        assert "items" in schemas
        assert isinstance(schemas["items"], ListValidationSchema)

    def test_schema_builder_dict(self) -> None:
        """Test dict schema building."""
        builder = SchemaBuilder()

        field_schemas = {"name": StringValidationSchema("name", min_length=1)}

        builder.add_dict("user", field_schemas=field_schemas, required_fields=["name"])

        schemas = builder.build()
        assert "user" in schemas
        assert isinstance(schemas["user"], DictValidationSchema)

    def test_schema_builder_get_schema(self) -> None:
        """Test getting individual schemas from builder."""
        builder = SchemaBuilder()
        builder.add_basic("test", data_type=str)

        schema = builder.get_schema("test")
        assert schema is not None
        assert isinstance(schema, BasicValidationSchema)

        # Test non-existent schema
        assert builder.get_schema("nonexistent") is None
