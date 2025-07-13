"""Tests for attrs model adapter."""

from unittest.mock import MagicMock, patch

import pytest
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
            adapter = AttrsModelAdapter()
            assert adapter is not None
        else:
            pytest.skip("attrs not available")

    def test_init_without_attrs_available(self) -> None:
        with patch("acb.adapters.models._attrs.ATTRS_AVAILABLE", False):
            with pytest.raises(
                ImportError, match="attrs is required for AttrsModelAdapter"
            ):
                AttrsModelAdapter()

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_serialize_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs") as mock_attrs:
            mock_attrs.has.return_value = True
            mock_attrs.asdict.return_value = {"id": 1, "name": "test"}

            adapter = AttrsModelAdapter()
            instance = MagicMock()

            result = adapter.serialize(instance)

            assert result == {"id": 1, "name": "test"}
            mock_attrs.has.assert_called_once_with(instance.__class__)
            mock_attrs.asdict.assert_called_once_with(instance)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_serialize_non_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter()
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
        with patch("acb.adapters.models._attrs.attrs") as mock_attrs:
            mock_field1 = MagicMock()
            mock_field1.name = "id"
            mock_field2 = MagicMock()
            mock_field2.name = "name"

            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field1, mock_field2]

            adapter = AttrsModelAdapter()
            test_class = type("TestClass", (), {})

            result = adapter.get_field_names(test_class)

            assert result == ["id", "name"]
            mock_attrs.has.assert_called_once_with(test_class)
            mock_attrs.fields.assert_called_once_with(test_class)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_names_non_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter()
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
        with patch("acb.adapters.models._attrs.attrs") as mock_attrs:
            mock_field1 = MagicMock()
            mock_field1.name = "id"
            mock_field1.type = int
            mock_field2 = MagicMock()
            mock_field2.name = "name"
            mock_field2.type = str

            mock_attrs.has.return_value = True
            mock_attrs.fields.return_value = [mock_field1, mock_field2]

            adapter = AttrsModelAdapter()
            test_class = type("TestClass", (), {})

            result = adapter.get_field_types(test_class)

            assert result == {"id": int, "name": str}
            mock_attrs.has.assert_called_once_with(test_class)
            mock_attrs.fields.assert_called_once_with(test_class)

    @pytest.mark.skipif(not ATTRS_AVAILABLE, reason="attrs not available")
    def test_get_field_types_non_attrs_model(self) -> None:
        with patch("acb.adapters.models._attrs.attrs") as mock_attrs:
            mock_attrs.has.return_value = False

            adapter = AttrsModelAdapter()
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
