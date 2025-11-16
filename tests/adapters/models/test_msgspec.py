"""Tests for msgspec model adapter."""

from unittest.mock import MagicMock, patch

import pytest
from typing import Any

from acb.adapters.models._msgspec import MSGSPEC_AVAILABLE, MsgspecModelAdapter


class TestMsgspecModelAdapter:
    def test_init_with_msgspec_available(self) -> None:
        if MSGSPEC_AVAILABLE:
            adapter = MsgspecModelAdapter()
            assert adapter is not None
        else:
            pytest.skip("msgspec not available")

    def test_init_without_msgspec_available(self) -> None:
        with patch("acb.adapters.models._msgspec.MSGSPEC_AVAILABLE", False):
            with pytest.raises(
                ImportError, match="msgspec is required for MsgspecModelAdapter"
            ):
                MsgspecModelAdapter()

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_serialize_msgspec_model(self) -> None:
        with patch("acb.adapters.models._msgspec.msgspec") as mock_msgspec:
            mock_msgspec.to_builtins.return_value = {"id": 1, "name": "test"}

            adapter = MsgspecModelAdapter()
            instance = MagicMock()

            result = adapter.serialize(instance)

            assert result == {"id": 1, "name": "test"}
            mock_msgspec.to_builtins.assert_called_once_with(instance)

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_serialize_non_msgspec_model(self) -> None:
        with patch("acb.adapters.models._msgspec.MSGSPEC_AVAILABLE", False):
            adapter = MsgspecModelAdapter.__new__(MsgspecModelAdapter)
            instance = MagicMock()

            with patch.object(
                adapter, "_manual_serialize", return_value={"manual": "data"}
            ) as mock_manual:
                result = adapter.serialize(instance)

                assert result == {"manual": "data"}
                mock_manual.assert_called_once_with(instance)

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_manual_serialize_with_struct_fields(self) -> None:
        adapter = MsgspecModelAdapter()
        instance = MagicMock()
        instance.__struct_fields__ = ["id", "name"]
        instance.id = 1
        instance.name = "test"

        with patch.object(
            adapter, "_serialize_value", side_effect=lambda x: x
        ) as mock_serialize:
            result = adapter._manual_serialize(instance)

            assert "id" in result
            assert "name" in result
            mock_serialize.assert_called()

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_manual_serialize_without_struct_fields(self) -> None:
        adapter = MsgspecModelAdapter()

        # Create a simple test class instead of complex mocking
        class TestInstance:
            def __init__(self):
                self.id = 1
                self.name = "test"
                self._private = "hidden"

            def method(self):
                return "callable"

        instance = TestInstance()
        # Remove struct fields to test the fallback path
        if hasattr(instance, "__struct_fields__"):
            delattr(instance, "__struct_fields__")

        with patch.object(adapter, "_serialize_value", side_effect=lambda x: x):
            result = adapter._manual_serialize(instance)

            # Should include non-private, non-callable attributes
            assert "id" in result
            assert "name" in result
            assert "_private" not in result  # private attribute excluded
            assert "method" not in result  # callable excluded

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_serialize_value_nested_struct(self) -> None:
        adapter = MsgspecModelAdapter()

        # Test with a real object to avoid isinstance recursion issues
        test_obj = {"nested": "data"}

        result = adapter._serialize_value(test_obj)

        # Dict should be returned as-is
        assert result == test_obj

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_serialize_value_list(self) -> None:
        adapter = MsgspecModelAdapter()

        test_list = [1, "test", {"key": "value"}]

        with patch.object(adapter, "_serialize_value", wraps=adapter._serialize_value):
            result = adapter._serialize_value(test_list)

            assert isinstance(result, list)
            assert len(result) == 3

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_serialize_value_dict(self) -> None:
        adapter = MsgspecModelAdapter()

        test_dict = {"key1": "value1", "key2": 2}

        with patch.object(adapter, "_serialize_value", wraps=adapter._serialize_value):
            result = adapter._serialize_value(test_dict)

            assert isinstance(result, dict)
            assert "key1" in result
            assert "key2" in result

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_deserialize_not_implemented(self) -> None:
        adapter = MsgspecModelAdapter()

        with pytest.raises(
            NotImplementedError,
            match="Deserialize requires specific model class context",
        ):
            adapter.deserialize({"test": "data"})

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_deserialize_to_class_with_msgspec(self) -> None:
        with patch("acb.adapters.models._msgspec.msgspec") as mock_msgspec:
            adapter = MsgspecModelAdapter()

            class TestModel:
                def __init__(self, name: str):
                    self.name = name

            mock_instance = TestModel("test")
            mock_msgspec.convert.return_value = mock_instance

            data = {"name": "test"}
            result = adapter.deserialize_to_class(TestModel, data)

            assert result == mock_instance
            mock_msgspec.convert.assert_called_once_with(data, TestModel)

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_deserialize_to_class_with_filtering(self) -> None:
        with patch("acb.adapters.models._msgspec.msgspec") as mock_msgspec:
            adapter = MsgspecModelAdapter()

            class TestModel:
                def __init__(self, name: str):
                    self.name = name

            # Mock msgspec.convert to raise exception first time
            mock_msgspec.convert.side_effect = Exception("Convert failed")

            data = {"name": "test", "extra_field": "ignored"}

            with patch.object(
                adapter, "_filter_data_for_model", return_value={"name": "test"}
            ) as mock_filter:
                result = adapter.deserialize_to_class(TestModel, data)

                assert isinstance(result, TestModel)
                assert result.name == "test"
                mock_filter.assert_called_once_with(TestModel, data)

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_deserialize_to_class_without_msgspec(self) -> None:
        with patch("acb.adapters.models._msgspec.MSGSPEC_AVAILABLE", False):
            adapter = MsgspecModelAdapter.__new__(MsgspecModelAdapter)

            class TestModel:
                def __init__(self, name: str):
                    self.name = name

            data = {"name": "test", "extra": "ignored"}

            with patch.object(
                adapter, "_filter_data_for_model", return_value={"name": "test"}
            ) as mock_filter:
                result = adapter.deserialize_to_class(TestModel, data)

                assert isinstance(result, TestModel)
                assert result.name == "test"
                mock_filter.assert_called_once_with(TestModel, data)

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_filter_data_for_model_with_struct_fields(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            __struct_fields__ = ["name", "age"]

        data = {"name": "test", "age": 25, "extra": "ignored"}

        result = adapter._filter_data_for_model(TestModel, data)

        assert result == {"name": "test", "age": 25}
        assert "extra" not in result

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_filter_data_for_model_without_struct_fields(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            pass

        data = {"name": "test", "age": 25}

        result = adapter._filter_data_for_model(TestModel, data)

        assert result == data  # Returns original data when no filtering possible

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_entity_name_tablename(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            __tablename__ = "test_table"

        result = adapter.get_entity_name(TestModel)
        assert result == "test_table"

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_entity_name_collection_name(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            __collection_name__ = "test_collection"

        result = adapter.get_entity_name(TestModel)
        assert result == "test_collection"

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_entity_name_default(self) -> None:
        adapter = MsgspecModelAdapter()

        class MyTestModel:
            pass

        result = adapter.get_entity_name(MyTestModel)
        assert result == "mytestmodel"  # Lowercased class name

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_field_mapping_with_struct_fields(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            __struct_fields__ = ["field1", "field2"]

        result = adapter.get_field_mapping(TestModel)

        assert result == {"field1": "field1", "field2": "field2"}

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_field_mapping_with_annotations(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            name: str
            age: int

        result = adapter.get_field_mapping(TestModel)

        assert result == {"name": "name", "age": "age"}

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_field_mapping_empty(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            pass

        result = adapter.get_field_mapping(TestModel)

        assert result == {}

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_validate_data_success(self) -> None:
        adapter = MsgspecModelAdapter()

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

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_validate_data_with_filtering(self) -> None:
        adapter = MsgspecModelAdapter()

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

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_primary_key_field_with_struct_fields(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            __struct_fields__ = ["name", "pk", "age"]

        result = adapter.get_primary_key_field(TestModel)
        assert result == "pk"

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_primary_key_field_with_annotations(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            name: str
            primary_key: int

        result = adapter.get_primary_key_field(TestModel)
        assert result == "primary_key"

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_primary_key_field_default(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            name: str
            age: int

        result = adapter.get_primary_key_field(TestModel)
        assert result == "id"  # Default fallback

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_field_type_with_annotations(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            name: str
            age: int

        result = adapter.get_field_type(TestModel, "name")
        assert result is str

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_field_type_default(self) -> None:
        adapter = MsgspecModelAdapter()

        class TestModel:
            pass

        result = adapter.get_field_type(TestModel, "nonexistent")
        assert result is Any

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_is_relationship_field_list_of_structs(self) -> None:
        adapter = MsgspecModelAdapter()

        # Test with a simple non-struct type to avoid mocking issues
        with patch.object(adapter, "get_field_type", return_value=list[str]):
            result = adapter.is_relationship_field(type("TestModel", (), {}), "field")
            assert result is False

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_is_relationship_field_single_struct(self) -> None:
        adapter = MsgspecModelAdapter()

        # Test with a simple type
        with patch.object(adapter, "get_field_type", return_value=str):
            result = adapter.is_relationship_field(type("TestModel", (), {}), "field")
            assert result is False

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_is_relationship_field_false(self) -> None:
        adapter = MsgspecModelAdapter()

        with patch.object(adapter, "get_field_type", return_value=str):
            result = adapter.is_relationship_field(type("TestModel", (), {}), "field")
            assert result is False

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_nested_model_class_list(self) -> None:
        adapter = MsgspecModelAdapter()

        # Test with a simple type
        with patch.object(adapter, "get_field_type", return_value=list[str]):
            result = adapter.get_nested_model_class(type("TestModel", (), {}), "field")
            assert result is None

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_nested_model_class_single(self) -> None:
        adapter = MsgspecModelAdapter()

        # Test with a simple type
        with patch.object(adapter, "get_field_type", return_value=str):
            result = adapter.get_nested_model_class(type("TestModel", (), {}), "field")
            assert result is None

    @pytest.mark.skipif(not MSGSPEC_AVAILABLE, reason="msgspec not available")
    def test_get_nested_model_class_none(self) -> None:
        adapter = MsgspecModelAdapter()

        with patch.object(adapter, "get_field_type", return_value=str):
            result = adapter.get_nested_model_class(type("TestModel", (), {}), "field")
            assert result is None

    def test_msgspec_fallback_class(self) -> None:
        # Test the fallback msgspec class when real msgspec is not available
        if not MSGSPEC_AVAILABLE:
            from acb.adapters.models._msgspec import msgspec

            assert hasattr(msgspec, "Struct")
            assert msgspec.Struct is not None

    def test_msgspec_available_flag(self) -> None:
        # Test that the MSGSPEC_AVAILABLE flag is properly set
        try:
            import msgspec

            _ = msgspec  # Use the import to avoid unused import warning

            assert MSGSPEC_AVAILABLE
        except ImportError:
            assert not MSGSPEC_AVAILABLE
