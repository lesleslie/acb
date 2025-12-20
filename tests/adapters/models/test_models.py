"""Tests for the Models adapter with auto-detection."""

from unittest.mock import Mock

import pytest

from acb.adapters.models import ModelsAdapter, _cached_auto_detect_model_type
from acb.adapters.models._redis_om import REDIS_OM_AVAILABLE


class ModelClass:
    """Mock model class for testing."""

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockSQLModel:
    """Mock SQLModel class for testing."""

    pass


class MockBaseModel:
    """Mock Pydantic BaseModel class for testing."""

    pass


class MockHashModel:
    """Mock Redis-OM HashModel class for testing."""

    pass


class MockStruct:
    """Mock msgspec Struct class for testing."""

    pass


class MockSQLAlchemyModel:
    """Mock SQLAlchemy model class for testing."""

    __table__ = True  # Simulate SQLAlchemy table attribute

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # Ensure it's not confused with SQLModel by not inheriting from anything SQLModel-like


class TestModelsAdapter:
    def setup_method(self) -> None:
        """Clear the cache before each test to ensure isolation."""
        _cached_auto_detect_model_type.cache_clear()

    def test_init(self) -> None:
        adapter = ModelsAdapter()
        assert adapter is not None
        assert adapter._pydantic_adapter is None
        assert adapter._sqlmodel_adapter is None
        assert adapter._sqlalchemy_adapter is None
        assert adapter._redis_om_adapter is None
        assert adapter._msgspec_adapter is None
        assert adapter._attrs_adapter is None

    def test_auto_detect_model_type_sqlmodel(self) -> None:
        adapter = ModelsAdapter()

        # Create a mock class that inherits from MockSQLModel
        class TestSQLModel(MockSQLModel):
            pass

        # Mock SQLModel import and class
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("sqlmodel.SQLModel", MockSQLModel)

            # Test with a class that appears to be SQLModel
            result = adapter.auto_detect_model_type(TestSQLModel)
            assert result == "sqlmodel"

    def test_auto_detect_model_type_sqlalchemy(self) -> None:
        adapter = ModelsAdapter()

        # Create a mock class that inherits from MockSQLAlchemyModel
        class TestSQLAlchemyModel(MockSQLAlchemyModel):
            pass

        # Test without any mocking - our TestSQLAlchemyModel has __table__ = True
        # which should trigger SQLAlchemy detection before it gets to SQLModel or Pydantic
        # Since the auto_detect_model_type method has try/except blocks,
        # having __table__ attribute should be enough
        result = adapter.auto_detect_model_type(TestSQLAlchemyModel)
        assert result == "sqlalchemy"

    def test_auto_detect_model_type_pydantic(self) -> None:
        adapter = ModelsAdapter()

        # Create a mock class that inherits from MockBaseModel
        class TestPydanticModel(MockBaseModel):
            pass

        # Mock Pydantic import and class
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("pydantic.BaseModel", MockBaseModel)

            # Test with a class that appears to be Pydantic
            result = adapter.auto_detect_model_type(TestPydanticModel)
            assert result == "pydantic"

    def test_auto_detect_model_type_redis_om(self) -> None:
        adapter = ModelsAdapter()

        # Create a mock class that inherits from MockHashModel
        class TestRedisModel(MockHashModel):
            pass

        # Mock Redis-OM import and class
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("redis_om.HashModel", MockHashModel)

            # Test with a class that appears to be Redis-OM
            result = adapter.auto_detect_model_type(TestRedisModel)
            assert result == "redis_om"

    def test_auto_detect_model_type_msgspec(self) -> None:
        adapter = ModelsAdapter()

        # Create a mock class that inherits from MockStruct
        class TestMsgspecModel(MockStruct):
            pass

        # Mock msgspec import and class
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr("msgspec.Struct", MockStruct)

            # Test with a class that appears to be msgspec
            result = adapter.auto_detect_model_type(TestMsgspecModel)
            assert result == "msgspec"

    def test_auto_detect_model_type_attrs(self) -> None:
        adapter = ModelsAdapter()

        # Mock attrs import and function
        with pytest.MonkeyPatch().context() as mp:
            mock_attrs = Mock()
            mock_attrs.has = Mock(return_value=True)
            mp.setattr("attrs.has", mock_attrs.has)

            # Test with a class that appears to be attrs
            result = adapter.auto_detect_model_type(ModelClass)
            assert result == "attrs"

    def test_auto_detect_model_type_fallback(self) -> None:
        # Test with an unknown class type
        result = (_adapter := ModelsAdapter()).auto_detect_model_type(ModelClass)
        assert result == "pydantic"

    def test_get_adapter_for_model_sqlmodel(self) -> None:
        adapter = ModelsAdapter()

        # Mock the auto-detection to return sqlmodel
        adapter.auto_detect_model_type = Mock(return_value="sqlmodel")
        adapter._get_sqlmodel_adapter = Mock(return_value="sqlmodel_adapter")

        result = adapter.get_adapter_for_model(ModelClass)
        assert result == "sqlmodel_adapter"

    def test_get_adapter_for_model_sqlalchemy(self) -> None:
        adapter = ModelsAdapter()

        # Mock the auto-detection to return sqlalchemy
        adapter.auto_detect_model_type = Mock(return_value="sqlalchemy")
        adapter._get_sqlalchemy_adapter = Mock(return_value="sqlalchemy_adapter")

        result = adapter.get_adapter_for_model(ModelClass)
        assert result == "sqlalchemy_adapter"

    def test_get_adapter_for_model_pydantic(self) -> None:
        adapter = ModelsAdapter()

        # Mock the auto-detection to return pydantic
        adapter.auto_detect_model_type = Mock(return_value="pydantic")
        adapter._get_pydantic_adapter = Mock(return_value="pydantic_adapter")

        result = adapter.get_adapter_for_model(ModelClass)
        assert result == "pydantic_adapter"

    def test_get_adapter_for_model_redis_om(self) -> None:
        adapter = ModelsAdapter()

        # Mock the auto-detection to return redis_om
        adapter.auto_detect_model_type = Mock(return_value="redis_om")
        adapter._get_redis_om_adapter = Mock(return_value="redis_om_adapter")

        result = adapter.get_adapter_for_model(ModelClass)
        assert result == "redis_om_adapter"

    def test_get_adapter_for_model_msgspec(self) -> None:
        adapter = ModelsAdapter()

        # Mock the auto-detection to return msgspec
        adapter.auto_detect_model_type = Mock(return_value="msgspec")
        adapter._get_msgspec_adapter = Mock(return_value="msgspec_adapter")

        result = adapter.get_adapter_for_model(ModelClass)
        assert result == "msgspec_adapter"

    def test_get_adapter_for_model_attrs(self) -> None:
        adapter = ModelsAdapter()

        # Mock the auto-detection to return attrs
        adapter.auto_detect_model_type = Mock(return_value="attrs")
        adapter._get_attrs_adapter = Mock(return_value="attrs_adapter")

        result = adapter.get_adapter_for_model(ModelClass)
        assert result == "attrs_adapter"

    def test_get_adapter_for_model_fallback(self) -> None:
        adapter = ModelsAdapter()

        # Mock the auto-detection to return unknown type
        adapter.auto_detect_model_type = Mock(return_value="unknown")
        adapter._get_pydantic_adapter = Mock(return_value="pydantic_adapter")

        result = adapter.get_adapter_for_model(ModelClass)
        assert result == "pydantic_adapter"

    def test_lazy_adapter_creation(self) -> None:
        adapter = ModelsAdapter()

        # Test that adapters are created lazily
        assert adapter._pydantic_adapter is None
        pydantic_adapter = adapter._get_pydantic_adapter()
        assert adapter._pydantic_adapter is not None
        assert adapter._get_pydantic_adapter() is pydantic_adapter  # Same instance

        assert adapter._sqlmodel_adapter is None
        sqlmodel_adapter = adapter._get_sqlmodel_adapter()
        assert adapter._sqlmodel_adapter is not None
        assert adapter._get_sqlmodel_adapter() is sqlmodel_adapter  # Same instance

        assert adapter._sqlalchemy_adapter is None
        sqlalchemy_adapter = adapter._get_sqlalchemy_adapter()
        assert adapter._sqlalchemy_adapter is not None
        assert adapter._get_sqlalchemy_adapter() is sqlalchemy_adapter  # Same instance

        assert adapter._msgspec_adapter is None
        msgspec_adapter = adapter._get_msgspec_adapter()
        assert adapter._msgspec_adapter is not None
        assert adapter._get_msgspec_adapter() is msgspec_adapter  # Same instance

        assert adapter._attrs_adapter is None
        attrs_adapter = adapter._get_attrs_adapter()
        assert adapter._attrs_adapter is not None
        assert adapter._get_attrs_adapter() is attrs_adapter  # Same instance

        # Only test redis-om if it's available
        if REDIS_OM_AVAILABLE:
            assert adapter._redis_om_adapter is None
            redis_om_adapter = adapter._get_redis_om_adapter()
            assert adapter._redis_om_adapter is not None
            assert adapter._get_redis_om_adapter() is redis_om_adapter  # Same instance
