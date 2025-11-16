"""Tests for attrs model adapter."""

from unittest.mock import MagicMock, patch

import pytest
from typing import Any

from acb.adapters.models._attrs import ATTRS_AVAILABLE, AttrsModelAdapter


class TestAttrsModelAdapter:
    @pytest.fixture
    def mock_attrs(self) -> MagicMock:
        mock = MagicMock()
        mock.has.return_value = True
        mock.asdict.return_value = {"id": 1, "name": "test"}
        mock.fields.return_value = [
            MagicMock(name="id", type=int),
            MagicMock(name="name", type=str),
        ]
        return mock

    def test_init_with_attrs_available(self) -> None:
        if ATTRS_AVAILABLE:
            adapter = AttrsModelAdapter[Any]()  # type: ignore[no-untyped-call]
            assert adapter is not None
        else:
            pytest.skip("attrs not available")

    def test_init_without_attrs_available(self) -> None:
        with patch("acb.adapters.models._attrs.ATTRS_AVAILABLE", False):
            with pytest.raises(
                ImportError, match="attrs is required for AttrsModelAdapter"
            ):
                AttrsModelAdapter[Any]()  # type: ignore[no-untyped-call]

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_serialize_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = True
            mock_attrs.asdict.return_value = {"id": 1, "name": "test"}

            adapter = AttrsModelAdapter[Any]()
            instance = MagicMock()

            result = adapter.serialize(instance)

            assert result == {"id": 1, "name": "test"}
            mock_attrs.has.assert_called_once_with(instance.__class__)
            mock_attrs.asdict.assert_called_once_with(instance)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_serialize_non_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()
            instance = MagicMock()

            with patch.object(
                adapter, "_manual_serialize", return_value={"manual": "data"}
            ) as mock_manual:
                result = adapter.serialize(instance)

                assert result == {"manual": "data"}
                mock_manual.assert_called_once_with(instance)

    def test_attrs_fallback_class_methods(self) -> None:
        # Test the fallback attrs class when real attrs is not available
        if not ATTRS_AVAILABLE:
            from acb.adapters.models._attrs import attrs

            test_class = type("TestClass", (), {})
            assert attrs.has(test_class) is False
            assert attrs.fields(test_class) == []
            assert attrs.asdict(MagicMock()) == {}

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_names_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field1 = MagicMock()
            mock_field1.name = "id"
            mock_field2 = MagicMock()
            mock_field2.name = "name"

            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field1, mock_field2]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            result = adapter.get_field_names(test_class)

            assert result == ["id", "name"]
            mock_attrs.has.assert_called_once_with(test_class)
            mock_attrs.fields.assert_called_once_with(test_class)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_names_non_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            with patch.object(
                adapter,
                "_get_field_names_from_annotations",
                return_value=["manual_field"],
            ) as mock_manual:
                result = adapter.get_field_names(test_class)

                assert result == ["manual_field"]
                mock_manual.assert_called_once_with(test_class)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_types_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field1 = MagicMock()
            mock_field1.name = "id"
            mock_field1.type = int
            mock_field2 = MagicMock()
            mock_field2.name = "name"
            mock_field2.type = str

            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field1, mock_field2]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            result = adapter.get_field_types(test_class)

            assert result == {"id": int, "name": str}
            mock_attrs.has.assert_called_once_with(test_class)
            mock_attrs.fields.assert_called_once_with(test_class)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_types_non_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            with patch.object(
                adapter,
                "_get_field_types_from_annotations",
                return_value={"manual_field": str},
            ) as mock_manual:
                result = adapter.get_field_types(test_class)

                assert result == {"manual_field": str}
                mock_manual.assert_called_once_with(test_class)

    def test_attrs_available_flag(self) -> None:
        # Test that the ATTRS_AVAILABLE flag is properly set
        try:
            import attrs

            _ = attrs  # Use the import to avoid unused import warning

            assert ATTRS_AVAILABLE
        except ImportError:
            assert not ATTRS_AVAILABLE

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_manual_serialize_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field1 = MagicMock()
            mock_field1.name = "id"
            mock_field2 = MagicMock()
            mock_field2.name = "name"
            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field1, mock_field2]

            adapter = AttrsModelAdapter[Any]()
            instance = MagicMock()
            instance.id = 1
            instance.name = "test"

            with patch.object(
                adapter, "_serialize_value", side_effect=lambda x: x
            ) as mock_serialize:
                result = adapter._manual_serialize(instance)

                assert "id" in result
                assert "name" in result
                mock_serialize.assert_called()

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_manual_serialize_non_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()

            # Create a simple test class instead of complex mocking
            class TestInstance:
                def __init__(self):
                    self.id = 1
                    self.name = "test"
                    self._private = "hidden"

                def method(self):
                    return "callable"

            instance = TestInstance()

            with patch.object(adapter, "_serialize_value", side_effect=lambda x: x):
                result = adapter._manual_serialize(instance)

                # Should include non-private, non-callable attributes
                assert "id" in result
                assert "name" in result
                assert "_private" not in result  # private attribute excluded
                assert "method" not in result  # callable excluded

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_serialize_value_nested_attrs(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            adapter = AttrsModelAdapter[Any]()

            # Test nested attrs object
            nested_obj = MagicMock()
            mock_attrs.has.return_value = True

            with patch.object(
                adapter, "serialize", return_value={"nested": "data"}
            ) as mock_serialize:
                result = adapter._serialize_value(nested_obj)

                assert result == {"nested": "data"}
                mock_serialize.assert_called_once_with(nested_obj)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_serialize_value_list(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        test_list = [1, "test", {"key": "value"}]

        with patch.object(adapter, "_serialize_value", wraps=adapter._serialize_value):
            result = adapter._serialize_value(test_list)

            assert isinstance(result, list)
            assert len(result) == 3

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_serialize_value_dict(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        test_dict = {"key1": "value1", "key2": 2}

        with patch.object(adapter, "_serialize_value", wraps=adapter._serialize_value):
            result = adapter._serialize_value(test_dict)

            assert isinstance(result, dict)
            assert "key1" in result
            assert "key2" in result

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_deserialize_not_implemented(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        with pytest.raises(
            NotImplementedError,
            match="Deserialize requires specific model class context",
        ):
            adapter.deserialize({"test": "data"})

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_deserialize_to_class_success(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        # Mock a simple class that can be instantiated
        class TestModel:
            def __init__(self, name: str, age: int):
                self.name = name
                self.age = age

        data = {"name": "test", "age": 25}
        result = adapter.deserialize_to_class(TestModel, data)

        assert isinstance(result, TestModel)
        assert result.name == "test"
        assert result.age == 25

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_deserialize_to_class_with_filtering(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        class TestModel:
            def __init__(self, name: str):
                self.name = name

        # Data with extra fields that should be filtered
        data = {"name": "test", "extra_field": "ignored"}

        with patch.object(
            adapter, "_filter_data_for_model", return_value={"name": "test"}
        ) as mock_filter:
            result = adapter.deserialize_to_class(TestModel, data)

            assert isinstance(result, TestModel)
            assert result.name == "test"
            mock_filter.assert_called_once_with(TestModel, data)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_filter_data_for_model_attrs(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field1 = MagicMock()
            mock_field1.name = "name"
            mock_field2 = MagicMock()
            mock_field2.name = "age"

            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field1, mock_field2]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})
            data = {"name": "test", "age": 25, "extra": "ignored"}

            result = adapter._filter_data_for_model(test_class, data)

            assert result == {"name": "test", "age": 25}
            assert "extra" not in result

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_filter_data_for_model_annotations(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()

            class TestClass:
                name: str
                age: int

            data = {"name": "test", "age": 25, "extra": "ignored"}

            result = adapter._filter_data_for_model(TestClass, data)

            assert result == {"name": "test", "age": 25}
            assert "extra" not in result

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_filter_data_for_model_fallback(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()

            # Create a class with no annotations explicitly
            class TestClass:
                pass

            # Remove annotations if they exist
            if hasattr(TestClass, "__annotations__"):
                delattr(TestClass, "__annotations__")

            data = {"name": "test", "age": 25}

            result = adapter._filter_data_for_model(TestClass, data)

            assert result == {}  # Returns empty dict when no attrs and no annotations

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_entity_name_tablename(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        class TestClass:
            __tablename__ = "test_table"

        result = adapter.get_entity_name(TestClass)
        assert result == "test_table"

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_entity_name_collection_name(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        class TestClass:
            __collection_name__ = "test_collection"

        result = adapter.get_entity_name(TestClass)
        assert result == "test_collection"

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_entity_name_attrs_metadata(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field = MagicMock()
            mock_field.metadata = {"table_name": "attrs_table"}

            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            result = adapter.get_entity_name(test_class)
            assert result == "attrs_table"

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_entity_name_default(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()
            test_class = type("MyTestClass", (), {})

            result = adapter.get_entity_name(test_class)
            assert result == "mytestclass"  # Lowercased class name

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_mapping_attrs(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field1 = MagicMock()
            mock_field1.name = "field1"
            mock_field1.metadata = {"alias": "field_one"}

            mock_field2 = MagicMock()
            mock_field2.name = "field2"
            mock_field2.metadata = {}

            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field1, mock_field2]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            result = adapter.get_field_mapping(test_class)

            assert result == {"field1": "field_one", "field2": "field2"}

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_mapping_annotations(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()

            class TestClass:
                name: str
                age: int

            result = adapter.get_field_mapping(TestClass)

            assert result == {"name": "name", "age": "age"}

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_validate_data_success(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        class TestModel:
            def __init__(self, name: str):
                self.name = name

        data = {"name": "test"}

        with (
            patch.object(
                adapter, "deserialize_to_class", return_value=TestModel("test")
            ) as mock_deserialize,
            patch.object(
                adapter, "serialize", return_value={"name": "test"}
            ) as mock_serialize,
        ):
            result = adapter.validate_data(TestModel, data)

            assert result == {"name": "test"}
            mock_deserialize.assert_called_once_with(TestModel, data)
            mock_serialize.assert_called_once()

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_validate_data_with_filtering(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        class TestModel:
            def __init__(self, name: str):
                self.name = name

        data = {"name": "test", "extra": "ignored"}

        with (
            patch.object(
                adapter,
                "deserialize_to_class",
                side_effect=[Exception("First try fails"), TestModel("test")],
            ) as mock_deserialize,
            patch.object(
                adapter, "_filter_data_for_model", return_value={"name": "test"}
            ) as mock_filter,
            patch.object(adapter, "serialize", return_value={"name": "test"}),
        ):
            result = adapter.validate_data(TestModel, data)

            assert result == {"name": "test"}
            assert mock_deserialize.call_count == 2
            mock_filter.assert_called_once_with(TestModel, data)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_primary_key_field_attrs(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = True

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            with patch.object(
                adapter, "_get_attrs_primary_key", return_value="custom_id"
            ) as mock_get_pk:
                result = adapter.get_primary_key_field(test_class)

                assert result == "custom_id"
                mock_get_pk.assert_called_once_with(test_class)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_primary_key_field_annotations(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()

            class TestClass:
                pk: int
                name: str

            with patch.object(
                adapter, "_get_annotation_primary_key", return_value="pk"
            ) as mock_get_pk:
                result = adapter.get_primary_key_field(TestClass)

                assert result == "pk"
                mock_get_pk.assert_called_once_with(TestClass)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_attrs_primary_key_metadata(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field1 = MagicMock()
            mock_field1.name = "custom_pk"
            mock_field1.metadata = {"primary_key": True}

            mock_field2 = MagicMock()
            mock_field2.name = "name"
            mock_field2.metadata = {}

            mock_attrs.fields.return_value = [mock_field1, mock_field2]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            result = adapter._get_attrs_primary_key(test_class)
            assert result == "custom_pk"

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_attrs_primary_key_common_names(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field1 = MagicMock()
            mock_field1.name = "pk"
            mock_field1.metadata = {}

            mock_field2 = MagicMock()
            mock_field2.name = "name"
            mock_field2.metadata = {}

            mock_attrs.fields.return_value = [mock_field1, mock_field2]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            result = adapter._get_attrs_primary_key(test_class)
            assert result == "pk"

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_attrs_primary_key_default(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field = MagicMock()
            mock_field.name = "name"
            mock_field.metadata = {}

            mock_attrs.fields.return_value = [mock_field]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            result = adapter._get_attrs_primary_key(test_class)
            assert result == "id"  # Default fallback

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_annotation_primary_key(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        class TestClass:
            primary_key: int
            name: str

        result = adapter._get_annotation_primary_key(TestClass)
        assert result == "primary_key"

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_annotation_primary_key_default(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        class TestClass:
            name: str
            age: int

        result = adapter._get_annotation_primary_key(TestClass)
        assert result == "id"  # Default fallback

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_names_from_annotations(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        class TestClass:
            name: str
            age: int

        result = adapter._get_field_names_from_annotations(TestClass)
        assert result == ["name", "age"]

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_names_from_annotations_no_annotations(self) -> None:
        adapter = AttrsModelAdapter[Any]()
        test_class = type("TestClass", (), {})  # No annotations

        result = adapter._get_field_names_from_annotations(test_class)
        assert result == []

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_types_from_annotations(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        class TestClass:
            name: str
            age: int

        result = adapter._get_field_types_from_annotations(TestClass)
        assert result == {"name": str, "age": int}

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_types_from_annotations_no_annotations(self) -> None:
        adapter = AttrsModelAdapter[Any]()
        test_class = type("TestClass", (), {})  # No annotations

        result = adapter._get_field_types_from_annotations(test_class)
        assert result == {}

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_type_attrs(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field = MagicMock()
            mock_field.name = "test_field"
            mock_field.type = str

            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            result = adapter.get_field_type(test_class, "test_field")
            assert result is str

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_type_attrs_none_type(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_field = MagicMock()
            mock_field.name = "test_field"
            mock_field.type = None

            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field]

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})

            result = adapter.get_field_type(test_class, "test_field")
            assert result is type(Any)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_type_annotations(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()

            class TestClass:
                name: str
                age: int

            result = adapter.get_field_type(TestClass, "name")
            assert result is str

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_type_default(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter[Any]()
            test_class = type("TestClass", (), {})  # No annotations

            result = adapter.get_field_type(test_class, "nonexistent")
            assert result is type(Any)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_is_relationship_field_list_of_attrs(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:
            # Mock a nested attrs class
            class NestedModel:
                pass

            mock_attrs.has.side_effect = lambda cls: cls == NestedModel

            adapter = AttrsModelAdapter[Any]()

            with patch.object(
                adapter, "get_field_type", return_value=list[NestedModel]
            ):
                result = adapter.is_relationship_field(
                    type("TestClass", (), {}), "field"
                )
                assert result is True

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_is_relationship_field_single_attrs(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:

            class NestedModel:
                pass

            mock_attrs.has.side_effect = lambda cls: cls == NestedModel

            adapter = AttrsModelAdapter[Any]()

            with patch.object(adapter, "get_field_type", return_value=NestedModel):
                result = adapter.is_relationship_field(
                    type("TestClass", (), {}), "field"
                )
                assert result is True

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_is_relationship_field_false(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        with patch.object(adapter, "get_field_type", return_value=str):
            result = adapter.is_relationship_field(type("TestClass", (), {}), "field")
            assert result is False

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_nested_model_class_list(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:

            class NestedModel:
                pass

            mock_attrs.has.side_effect = lambda cls: cls == NestedModel

            adapter = AttrsModelAdapter[Any]()

            with patch.object(
                adapter, "get_field_type", return_value=list[NestedModel]
            ):
                result = adapter.get_nested_model_class(
                    type("TestClass", (), {}), "field"
                )
                assert result == NestedModel

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_nested_model_class_single(self) -> None:
        with patch("acb.adapters.models._attrs.attrs_lib") as mock_attrs:

            class NestedModel:
                pass

            mock_attrs.has.side_effect = lambda cls: cls == NestedModel

            adapter = AttrsModelAdapter[Any]()

            with patch.object(adapter, "get_field_type", return_value=NestedModel):
                result = adapter.get_nested_model_class(
                    type("TestClass", (), {}), "field"
                )
                assert result == NestedModel

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_nested_model_class_none(self) -> None:
        adapter = AttrsModelAdapter[Any]()

        with patch.object(adapter, "get_field_type", return_value=str):
            result = adapter.get_nested_model_class(type("TestClass", (), {}), "field")
            assert result is None
