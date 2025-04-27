"""Simplified tests for the Models adapters."""

import pytest
from tests.test_interfaces import MockModels, ModelsTestInterface


@pytest.fixture
async def models() -> MockModels:
    models = MockModels()
    await models.init()
    return models


class TestModels(ModelsTestInterface):
    pass
